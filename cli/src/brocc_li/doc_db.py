"""
Document database using DuckDB + Polars + PyArrow
- Zero-copy Arrow format: Direct memory sharing between DuckDB and Polars without serialization/deserialization
- Columnar storage: Data stored in columns rather than rows, enabling vectorized operations and better cache utilization
- polars vs. pandas:
  * Rust backend for memory safety and performance
  * Lazy evaluation for query optimization
  * Native Arrow integration
  * Better memory efficiency with zero-copy operations
  * Type-safe operations with strict typing

Document update/versioning behavior:
- Goal is to track document history while avoiding needless duplication
- When storing a document, the we check for existing versions by ID or URL:
  * Docs with identical content but different metadata will be updated in place
  * Docs with different content (even with same URL or ID) will create new versions
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import polars as pl
from platformdirs import user_data_dir

from brocc_li.embed.chunk_markdown import chunk_markdown
from brocc_li.types.doc import Chunk, Doc
from brocc_li.utils.pydantic_to_sql import generate_create_table_sql
from brocc_li.utils.serde import polars_to_dicts, process_array_field, process_json_field

# Define app information for appdirs
APP_NAME = "brocc"
APP_AUTHOR = "substratelabs"

# Database constants
DEFAULT_DB_FILENAME = "documents.duckdb"
DOCUMENTS_TABLE = "documents"
CHUNKS_TABLE = "chunks"

# Document field constants
ARRAY_FIELDS = ["participant_names", "participant_identifiers", "keywords"]
JSON_FIELDS = {"metadata": {}, "contact_metadata": {}, "participant_metadatas": []}
# Fields to exclude from database schema (processed separately)
EXCLUDED_FIELDS = {"text_content"}


def get_default_db_path() -> str:
    """Get the default database path in the user's data directory."""
    data_dir = user_data_dir(APP_NAME, APP_AUTHOR)
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, DEFAULT_DB_FILENAME)


class DocDB:
    """Handles storage and retrieval of documents using DuckDB."""

    def __init__(self, db_path: str | None = None):
        """Initialize the storage with the given database path or the default."""
        self.db_path = db_path or get_default_db_path()
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Set up the database and create tables if they don't exist."""
        # Create the parent directory if it doesn't exist
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with duckdb.connect(self.db_path) as conn:
            # Generate the CREATE TABLE statement dynamically for documents
            create_documents_sql = generate_create_table_sql(Doc, DOCUMENTS_TABLE)
            print(f"Generated Documents Schema:\n{create_documents_sql}")
            conn.execute(create_documents_sql)

            # Generate the CREATE TABLE statement for chunks
            create_chunks_sql = generate_create_table_sql(Chunk, CHUNKS_TABLE)
            print(f"Generated Chunks Schema:\n{create_chunks_sql}")
            conn.execute(create_chunks_sql)

    def url_exists(self, url: str) -> bool:
        """Check if a document with the given URL already exists."""
        if not url:
            return False

        with duckdb.connect(self.db_path) as conn:
            result = conn.execute(
                f"SELECT COUNT(*) FROM {DOCUMENTS_TABLE} WHERE url = ?", [url]
            ).fetchone()
            return result is not None and result[0] > 0

    def get_seen_urls(self, source: str | None = None) -> set[str]:
        """Get a set of URLs that have already been seen."""
        with duckdb.connect(self.db_path) as conn:
            query = f"SELECT url FROM {DOCUMENTS_TABLE}"
            params = []

            if source:
                query += " WHERE source = ?"
                params.append(source)

            df: pl.DataFrame | pl.Series = pl.from_arrow(conn.execute(query, params).arrow())
            if isinstance(df, pl.DataFrame):
                return set(df["url"].drop_nulls().to_list())
            else:
                return set() if df.is_empty() else {df.item()}

    def get_documents_by_url(self, url: str) -> list[dict[str, Any]]:
        """Retrieve all documents with the given URL."""
        if not url:
            return []

        with duckdb.connect(self.db_path) as conn:
            df = pl.from_arrow(
                conn.execute(
                    f"SELECT * FROM {DOCUMENTS_TABLE} WHERE url = ? ORDER BY ingested_at DESC",
                    [url],
                ).arrow()
            )

            if df.is_empty():
                return []

            # Convert to list of native Python dictionaries
            raw_dicts = polars_to_dicts(df)
            return [self._process_document_fields(doc) for doc in raw_dicts]

    def _process_document_fields(self, document: dict[str, Any]) -> dict[str, Any]:
        """Process document fields for consistent formatting."""
        doc = document.copy()

        # Convert None arrays to empty lists
        for field in ARRAY_FIELDS:
            if field in doc:
                doc[field] = process_array_field(doc[field])
            else:
                doc[field] = []

        # Parse JSON fields
        for field, default in JSON_FIELDS.items():
            if field in doc:
                doc[field] = process_json_field(doc[field], default)
            else:
                doc[field] = default

        return doc

    def _prepare_document_for_storage(self, document: dict[str, Any]) -> dict[str, Any]:
        """Validate, format, and prepare a document dictionary for database storage."""
        # Create a copy to avoid modifying the original input dict
        doc_data = document.copy()

        # Ensure ingested_at is set *before* validation if not provided
        if "ingested_at" not in doc_data or not doc_data["ingested_at"]:
            doc_data["ingested_at"] = Doc.format_date(datetime.now())

        # text_content will be handled separately in store_document, no need to validate it here
        text_content = doc_data.pop("text_content", None)

        # Validate against the Pydantic model
        try:
            # Create a new doc without text_content for validation
            doc = Doc(**doc_data)
            prepared_doc = doc.model_dump()
        except Exception as e:
            # Consider logging the actual error and invalid data here
            print(f"Validation Error: {e}\nData: {doc_data}")  # Temp print
            raise ValueError(f"Invalid document structure: {str(e)}") from e

        # Add/Update timestamps *after* validation
        prepared_doc["last_updated"] = Doc.format_date(datetime.now())

        # Add back text_content if it was provided (will be removed later during insert/update)
        if text_content is not None:
            prepared_doc["text_content"] = text_content

        # Convert enum values to strings
        for key, value in prepared_doc.items():
            # Check if it has a 'value' attribute common to Enums
            if hasattr(value, "value") and isinstance(value.value, (str, int, float)):
                prepared_doc[key] = value.value

        # Ensure array fields are None for empty lists if the column type is ARRAY
        # This helps DuckDB store them properly as VARCHAR[] types
        for field in ARRAY_FIELDS:
            if prepared_doc.get(field) == []:
                prepared_doc[field] = None  # For VARCHAR[]

        # Initialize keywords if it doesn't exist
        if "keywords" not in prepared_doc:
            prepared_doc["keywords"] = None

        # Convert metadata fields to JSON strings
        for field in JSON_FIELDS:
            prepared_doc[field] = json.dumps(prepared_doc.get(field) or JSON_FIELDS[field])

        # Remove fields from prepared_doc that are not actual table columns
        # Get table columns dynamically (excluding computed fields if any, though Doc doesn't have them)
        # For now, use model_fields + last_updated
        valid_db_keys = set(Doc.model_fields.keys()) | {"last_updated"}
        final_db_doc = {k: v for k, v in prepared_doc.items() if k in valid_db_keys}

        return final_db_doc

    def _prepare_chunk_for_storage(self, chunk: Chunk) -> dict[str, Any]:
        """Prepare a Chunk object for database storage."""
        # Convert to dictionary
        prepared_chunk = chunk.model_dump()

        # Convert content to JSON string if it's not already
        if prepared_chunk.get("content"):
            prepared_chunk["content"] = json.dumps(prepared_chunk["content"])
        else:
            prepared_chunk["content"] = "[]"

        return prepared_chunk

    def _chunks_are_identical(self, doc_id: str, new_chunks: list[Chunk]) -> bool:
        """
        Check if the new chunks are identical to the existing ones.

        Args:
            doc_id: The ID of the document to check against
            new_chunks: The new chunks to compare

        Returns:
            bool: True if the chunks are identical, False otherwise
        """
        # Get existing chunks
        existing_chunks = self.get_chunks_by_doc_id(doc_id)

        # Quick check - if the number of chunks differs, they're not identical
        if len(existing_chunks) != len(new_chunks):
            return False

        # Create dictionaries of processed chunks for comparison
        existing_processed = {}
        for chunk in existing_chunks:
            idx = (
                int(chunk["chunk_index"])
                if isinstance(chunk["chunk_index"], str)
                else chunk["chunk_index"]
            )
            existing_processed[idx] = chunk["content"]

        # Compare chunks by content
        for chunk in new_chunks:
            chunk_dict = self._prepare_chunk_for_storage(chunk)
            idx = chunk.chunk_index

            # If the chunk index doesn't exist in existing chunks, they're not identical
            if idx not in existing_processed:
                return False

            # Parse existing content back into a list if it's a string
            existing_content = existing_processed[idx]
            if isinstance(existing_content, str):
                try:
                    existing_content = json.loads(existing_content)
                except json.JSONDecodeError:
                    existing_content = []

            # Parse new content back into a list if it's a string
            new_content = chunk_dict["content"]
            if isinstance(new_content, str):
                try:
                    new_content = json.loads(new_content)
                except json.JSONDecodeError:
                    new_content = []

            # Compare the content - if not equal, chunks aren't identical
            if existing_content != new_content:
                return False

        # All checks passed, chunks are identical
        return True

    def _find_id_for_update(
        self, document: dict[str, Any], db_document: dict[str, Any], new_chunks: list[Chunk]
    ) -> tuple[str | None, bool]:
        """
        Determine if an existing document should be updated, returning its ID if found.

        Returns:
            tuple: (doc_id, update_chunks)
            - doc_id: ID of document to update, or None if no match
            - update_chunks: Whether chunks should be updated (False if content identical)
        """
        # First priority: check by ID
        doc_id = document.get("id")
        if doc_id and self.get_document_by_id(doc_id):
            # Check if chunks are identical
            if self._chunks_are_identical(doc_id, new_chunks):
                return doc_id, False
            # Content differs, do not update - will create new
            return None, True

        # Second priority: check by URL
        url = document.get("url")
        if url:
            matching_docs = self.get_documents_by_url(url)
            if matching_docs:
                # If multiple matches, use the most recent one's ID
                update_id = matching_docs[0]["id"]

                # Check if chunks are identical
                if self._chunks_are_identical(update_id, new_chunks):
                    # Update the document's ID if it wasn't set originally
                    if not document.get("id"):
                        document["id"] = update_id
                        db_document["id"] = update_id
                    return update_id, False

                # Content differs, do not update - will create new
                return None, True

        # No existing document found or content differs, insert new
        return None, True

    def _update_document(self, conn, db_document: dict[str, Any], doc_id: str) -> None:
        """Execute the UPDATE statement for a given document ID."""
        set_clauses = []
        params = []
        # Get columns from the actual table to handle potential schema mismatches
        # However, for simplicity now, assume db_document keys match table columns derived from Doc + last_updated
        table_columns = list(Doc.model_fields.keys()) + ["last_updated"]

        for key, value in db_document.items():
            if (
                key != "id" and key in table_columns and key not in EXCLUDED_FIELDS
            ):  # Ensure key is in expected columns, not 'id', and not excluded
                set_clauses.append(f"{key} = ?")
                params.append(value)

        if not set_clauses:
            print(f"Warning: No fields to update for document ID {doc_id}")
            return

        params.append(doc_id)  # Add the ID for the WHERE clause
        update_query = f"UPDATE {DOCUMENTS_TABLE} SET {', '.join(set_clauses)} WHERE id = ?"
        conn.execute(update_query, params)

    def _insert_document(self, conn, db_document: dict[str, Any]) -> None:
        """Execute the INSERT statement for a new document."""
        # Ensure document has an ID
        if not db_document.get("id"):
            db_document["id"] = Doc.generate_id()

        # Filter db_document to only include keys corresponding to table columns
        table_columns = list(Doc.model_fields.keys()) + ["last_updated"]

        # Filter out fields that should not be stored directly
        filtered_db_doc = {
            k: v for k, v in db_document.items() if k in table_columns and k not in EXCLUDED_FIELDS
        }

        columns = ", ".join(filtered_db_doc.keys())
        placeholders = ", ".join(["?"] * len(filtered_db_doc))
        insert_query = f"INSERT INTO {DOCUMENTS_TABLE} ({columns}) VALUES ({placeholders})"
        conn.execute(insert_query, list(filtered_db_doc.values()))

    def _store_chunks(self, conn, chunks: list[Chunk]) -> None:
        """Store multiple chunks in the database."""
        for chunk in chunks:
            db_chunk = self._prepare_chunk_for_storage(chunk)
            columns = ", ".join(db_chunk.keys())
            placeholders = ", ".join(["?"] * len(db_chunk))
            insert_query = f"INSERT INTO {CHUNKS_TABLE} ({columns}) VALUES ({placeholders})"
            conn.execute(insert_query, list(db_chunk.values()))

    def _delete_chunks(self, conn, doc_id: str) -> None:
        """Delete all chunks associated with a document ID."""
        conn.execute(f"DELETE FROM {CHUNKS_TABLE} WHERE doc_id = ?", [doc_id])

    def store_document_with_chunks(self, document_data: dict[str, Any], text_content: str) -> str:
        """
        Store a document and its chunks in the database.
        Returns str ID of the stored document.

        Logic:
        - If a document with same ID/URL exists AND has identical content, update metadata only
        - If content differs, create a new document regardless of ID/URL match
        """
        # Create a copy of the document data to avoid modifying the original
        doc_data = document_data.copy()
        original_id = doc_data.get("id")

        # Get chunks from text content
        chunked_content = chunk_markdown(text_content)

        # Create a Doc object to pass to create_chunks_for_doc
        doc_obj = Doc(**doc_data)

        # Create chunk objects
        chunks = Doc.create_chunks_for_doc(doc_obj, chunked_content)

        with duckdb.connect(self.db_path) as conn:
            # Check if an existing document needs to be updated
            id_to_update, update_chunks = self._find_id_for_update(doc_data, doc_data, chunks)

            if id_to_update and not update_chunks:
                # Content is identical, only update document metadata
                db_document = self._prepare_document_for_storage(doc_data)
                self._update_document(conn, db_document, id_to_update)
                return id_to_update
            else:
                # Either no matching document found or content differs
                # In both cases, create a new document with new chunks

                # If original had an ID that matched an existing doc but content differs,
                # or we're matching by URL but content differs, we need a new ID
                if original_id and (
                    self.get_document_by_id(original_id)
                    or (doc_data.get("url") and self.url_exists(doc_data.get("url") or ""))
                ):
                    # Generate a new ID
                    new_id = Doc.generate_id()
                    doc_data["id"] = new_id

                    # Update doc_id in all chunks
                    for chunk in chunks:
                        chunk.doc_id = new_id

                # Prepare document for storage (after potential ID change)
                db_document = self._prepare_document_for_storage(doc_data)

                # Insert new document
                self._insert_document(conn, db_document)

                # Store new chunks
                self._store_chunks(conn, chunks)

            return doc_data["id"]

    def store_document(self, document: Doc) -> bool:
        """
        Store a document in the database, updating if it already exists.

        Args:
            document: A Doc object that must contain text_content for chunking.

        Returns:
            bool: True if the document was stored successfully.

        Raises:
            ValueError: If document doesn't contain required text_content field.

        Implementation details:
        - The text_content is removed from the document and:
          1. Chunked according to markdown structure
          2. Stored separately in the chunks table
          3. The document will reference these chunks through the doc_id
        - The text_content field is not stored directly in the documents table
        """
        # Convert to dict for processing
        doc_dict = document.model_dump()

        # Require text_content - this is what makes the document valuable
        text_content = doc_dict.pop("text_content", None)
        if not text_content:
            raise ValueError("Document must contain text_content field for chunking")

        self.store_document_with_chunks(doc_dict, text_content)
        return True

    def get_document_by_id(self, doc_id: str) -> dict[str, Any] | None:
        """Retrieve a document by its ID."""
        if not doc_id:
            return None

        with duckdb.connect(self.db_path) as conn:
            df = pl.from_arrow(
                conn.execute(f"SELECT * FROM {DOCUMENTS_TABLE} WHERE id = ?", [doc_id]).arrow()
            )

            if df.is_empty():
                return None

            # Convert to a plain Python dictionary
            raw_dicts = polars_to_dicts(df)
            if raw_dicts:
                return self._process_document_fields(raw_dicts[0])
            return None

    def get_documents(
        self,
        source: str | None = None,
        source_location: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Retrieve documents with optional filtering."""
        with duckdb.connect(self.db_path) as conn:
            query = f"SELECT * FROM {DOCUMENTS_TABLE}"
            params = []

            # Add optional filters
            where_clauses = []
            if source:
                where_clauses.append("source = ?")
                params.append(source)
            if source_location:
                where_clauses.append("source_location_identifier = ?")
                params.append(source_location)

            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)

            # Add limit and offset
            query += f" ORDER BY ingested_at DESC LIMIT {limit} OFFSET {offset}"

            df = pl.from_arrow(conn.execute(query, params).arrow())

            if df.is_empty():
                return []

            # Convert to list of native Python dictionaries
            raw_dicts = polars_to_dicts(df)
            return [self._process_document_fields(doc) for doc in raw_dicts]

    def _process_chunk_fields(self, chunk: dict[str, Any]) -> dict[str, Any]:
        """Process chunk fields for consistent formatting."""
        processed = chunk.copy()

        # Parse JSON content field
        if "content" in processed and processed["content"]:
            if isinstance(processed["content"], str):
                try:
                    processed["content"] = json.loads(processed["content"])
                except json.JSONDecodeError:
                    processed["content"] = []
        else:
            processed["content"] = []

        return processed

    def get_chunks_by_doc_id(self, doc_id: str) -> list[dict[str, Any]]:
        """
        Retrieve all chunks for a document by its ID.
        Returns list of chunk dictionaries.
        """
        with duckdb.connect(self.db_path) as conn:
            df = pl.from_arrow(
                conn.execute(
                    f"SELECT * FROM {CHUNKS_TABLE} WHERE doc_id = ? ORDER BY chunk_index", [doc_id]
                ).arrow()
            )

            if df.is_empty():
                return []

            # Convert to list of native Python dictionaries
            raw_dicts = polars_to_dicts(df)
            return [self._process_chunk_fields(chunk) for chunk in raw_dicts]

    def launch_ui(self) -> None:
        """
        Launch the DuckDB UI for the documents database.
        https://duckdb.org/docs/stable/extensions/ui.html
        """
        import time
        import webbrowser

        import duckdb

        conn = duckdb.connect(self.db_path)
        conn.execute("INSTALL ui;")
        conn.execute("LOAD ui;")
        # Start the server first
        conn.execute("CALL start_ui_server();")
        # Give the server a moment to start
        time.sleep(1)
        # Open browser
        webbrowser.open("http://localhost:4213")
        # Keep the connection alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            conn.execute("CALL stop_ui_server();")
            conn.close()

    def get_chunks_for_document(self, doc_id: str) -> list[dict[str, Any]]:
        """
        Retrieve all chunks associated with a document ID.
        Returns list of chunk dictionaries.
        """
        return self.get_chunks_by_doc_id(doc_id)


def launch_ui() -> None:
    """Launch the DuckDB UI for the documents database."""
    storage = DocDB()
    storage.launch_ui()


def delete_db(db_path: str | None = None) -> bool:
    """Delete the database file at the given path or the default path."""
    path = db_path or get_default_db_path()
    print(f"Attempting to delete database at: {path}")
    if os.path.exists(path):
        try:
            os.remove(path)
            print("Successfully deleted database")
            return True
        except Exception as e:
            print(f"Failed to delete database: {e}")
            return False
    print("Database file not found")
    return False


def open_db_folder() -> None:
    """Open the application data directory in the system's file browser."""
    data_dir = user_data_dir(APP_NAME, APP_AUTHOR)
    os.makedirs(data_dir, exist_ok=True)

    # Use webbrowser module for cross-platform support
    try:
        import webbrowser

        url = f"file://{data_dir}"
        webbrowser.open(url)
        print(f"Opened data directory: {data_dir}")
    except Exception as e:
        print(f"Failed to open data directory: {e}")
        print(f"Data directory path: {data_dir}")
