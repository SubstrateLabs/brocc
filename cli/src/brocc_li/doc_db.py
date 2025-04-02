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
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import polars as pl
from platformdirs import user_data_dir

from brocc_li.types.doc import Doc
from brocc_li.utils.pydantic_to_sql import generate_create_table_sql

# Define app information for appdirs
APP_NAME = "brocc"
APP_AUTHOR = "substratelabs"

# Database constants
DEFAULT_DB_FILENAME = "documents.duckdb"
DOCUMENTS_TABLE = "documents"


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
            # Generate the CREATE TABLE statement dynamically
            create_table_sql = generate_create_table_sql(Doc, DOCUMENTS_TABLE)
            print(
                f"Generated Schema:\n{create_table_sql}"
            )  # Optional: print generated schema for debugging
            conn.execute(create_table_sql)

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
            df: pl.DataFrame | pl.Series = pl.from_arrow(
                conn.execute(
                    f"SELECT * FROM {DOCUMENTS_TABLE} WHERE url = ? ORDER BY ingested_at DESC",
                    [url],
                ).arrow()
            )

            if df.is_empty():
                return []

            # Convert to list of dicts and handle special fields
            documents = []
            if isinstance(df, pl.DataFrame):
                for row in df.to_dicts():
                    # Convert None arrays to empty lists for consistency with the Document model
                    if row.get("participant_names") is None:
                        row["participant_names"] = []

                    if row.get("participant_identifiers") is None:
                        row["participant_identifiers"] = []

                    if row.get("keywords") is None:
                        row["keywords"] = []

                    # Convert string representation of arrays to actual arrays if needed
                    for array_field in ["participant_names", "participant_identifiers", "keywords"]:
                        if isinstance(row.get(array_field), str) and row[array_field].startswith(
                            "["
                        ):
                            try:
                                row[array_field] = json.loads(row[array_field].replace("'", '"'))
                            except json.JSONDecodeError:
                                # If JSON parsing fails, keep the original string
                                pass

                    # Parse JSON fields
                    for json_field in ["metadata", "contact_metadata", "participant_metadatas"]:
                        if json_field in row and row[json_field]:
                            if isinstance(row[json_field], str):
                                try:
                                    row[json_field] = json.loads(row[json_field])
                                except json.JSONDecodeError:
                                    row[json_field] = (
                                        {} if json_field != "participant_metadatas" else []
                                    )
                        elif json_field == "metadata" or json_field == "contact_metadata":
                            row[json_field] = {}
                        elif json_field == "participant_metadatas":
                            row[json_field] = []

                    documents.append(row)
            else:
                # Handle Series case
                row = df.item()
                if isinstance(row, dict):
                    # Apply the same conversions as above
                    if row.get("participant_names") is None:
                        row["participant_names"] = []
                    if row.get("participant_identifiers") is None:
                        row["participant_identifiers"] = []
                    if row.get("keywords") is None:
                        row["keywords"] = []

                    # Process arrays and JSON fields
                    for array_field in ["participant_names", "participant_identifiers", "keywords"]:
                        if isinstance(row.get(array_field), str) and row[array_field].startswith(
                            "["
                        ):
                            try:
                                row[array_field] = json.loads(row[array_field].replace("'", '"'))
                            except json.JSONDecodeError:
                                # If JSON parsing fails, keep the original string
                                pass

                    for json_field in ["metadata", "contact_metadata", "participant_metadatas"]:
                        if json_field in row and row[json_field]:
                            if isinstance(row[json_field], str):
                                try:
                                    row[json_field] = json.loads(row[json_field])
                                except json.JSONDecodeError:
                                    row[json_field] = (
                                        {} if json_field != "participant_metadatas" else []
                                    )
                        elif json_field == "metadata" or json_field == "contact_metadata":
                            row[json_field] = {}
                        elif json_field == "participant_metadatas":
                            row[json_field] = []
                documents.append(row)

            return documents

    def _prepare_document_for_storage(self, document: dict[str, Any]) -> dict[str, Any]:
        """Validate, format, and prepare a document dictionary for database storage."""
        # Create a copy to avoid modifying the original input dict
        doc_data = document.copy()

        # Ensure ingested_at is set *before* validation if not provided
        if "ingested_at" not in doc_data or not doc_data["ingested_at"]:
            doc_data["ingested_at"] = Doc.format_date(datetime.now())

        # Validate against the Pydantic model
        try:
            doc = Doc(**doc_data)
            prepared_doc = doc.model_dump()
        except Exception as e:
            # Consider logging the actual error and invalid data here
            print(f"Validation Error: {e}\nData: {doc_data}")  # Temp print
            raise ValueError(f"Invalid document structure: {str(e)}") from e

        # Add/Update timestamps *after* validation
        prepared_doc["last_updated"] = Doc.format_date(datetime.now())

        # Convert enum values to strings
        for key, value in prepared_doc.items():
            # Check if it has a 'value' attribute common to Enums
            if hasattr(value, "value") and isinstance(value.value, (str, int, float)):
                prepared_doc[key] = value.value

        # Ensure array fields are None for empty lists if the column type is ARRAY
        # This helps DuckDB store them properly as VARCHAR[] types
        if prepared_doc.get("participant_names") == []:
            prepared_doc["participant_names"] = None  # For VARCHAR[]
        if prepared_doc.get("participant_identifiers") == []:
            prepared_doc["participant_identifiers"] = None  # For VARCHAR[]
        if prepared_doc.get("keywords") == []:
            prepared_doc["keywords"] = None  # For VARCHAR[]

        # Initialize keywords if it doesn't exist
        if "keywords" not in prepared_doc:
            prepared_doc["keywords"] = None

        # Convert metadata fields to JSON strings
        prepared_doc["metadata"] = json.dumps(prepared_doc.get("metadata") or {})
        prepared_doc["contact_metadata"] = json.dumps(prepared_doc.get("contact_metadata") or {})
        prepared_doc["participant_metadatas"] = json.dumps(
            prepared_doc.get("participant_metadatas") or []
        )

        # Remove fields from prepared_doc that are not actual table columns
        # Get table columns dynamically (excluding computed fields if any, though Doc doesn't have them)
        # For now, use model_fields + last_updated
        valid_db_keys = set(Doc.model_fields.keys()) | {"last_updated"}
        final_db_doc = {k: v for k, v in prepared_doc.items() if k in valid_db_keys}

        return final_db_doc

    def _find_id_for_update(
        self, document: dict[str, Any], db_document: dict[str, Any]
    ) -> str | None:
        """Determine if an existing document should be updated, returning its ID if found."""
        # First priority: check by ID
        doc_id = document.get("id")
        if doc_id and self.get_document_by_id(doc_id):
            return doc_id

        # Second priority: check by URL
        url = document.get("url")
        if url:
            matching_docs = self.get_documents_by_url(url)
            if matching_docs:
                # If multiple matches, use the most recent one's ID
                update_id = matching_docs[0]["id"]
                # Update the document's ID if it wasn't set originally
                if not document.get("id"):
                    # Need to update both original dict (for return?) and db_dict (for storage)
                    document["id"] = update_id
                    db_document["id"] = update_id
                return update_id

        return None  # No existing document found for update

    def _update_document(self, conn, db_document: dict[str, Any], doc_id: str) -> None:
        """Execute the UPDATE statement for a given document ID."""
        set_clauses = []
        params = []
        # Get columns from the actual table to handle potential schema mismatches
        # However, for simplicity now, assume db_document keys match table columns derived from Doc + last_updated
        table_columns = list(Doc.model_fields.keys()) + ["last_updated"]

        for key, value in db_document.items():
            if (
                key != "id" and key in table_columns
            ):  # Ensure key is in expected columns and not 'id'
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
        filtered_db_doc = {k: v for k, v in db_document.items() if k in table_columns}

        columns = ", ".join(filtered_db_doc.keys())
        placeholders = ", ".join(["?"] * len(filtered_db_doc))
        insert_query = f"INSERT INTO {DOCUMENTS_TABLE} ({columns}) VALUES ({placeholders})"
        conn.execute(insert_query, list(filtered_db_doc.values()))

    def store_document(self, document: dict[str, Any]) -> bool:
        """Store a document in the database, updating if it already exists."""
        # Prepare the document data (validation, formatting, etc.)
        db_document = self._prepare_document_for_storage(document)

        # Check if an existing document needs to be updated
        id_to_update = self._find_id_for_update(document, db_document)

        with duckdb.connect(self.db_path) as conn:
            if id_to_update:
                # Update existing document
                self._update_document(conn, db_document, id_to_update)
            else:
                # Insert new document
                self._insert_document(conn, db_document)

        return True

    def get_document_by_id(self, doc_id: str) -> dict[str, Any] | None:
        """Retrieve a document by its ID."""
        if not doc_id:
            return None

        with duckdb.connect(self.db_path) as conn:
            df: pl.DataFrame | pl.Series = pl.from_arrow(
                conn.execute(f"SELECT * FROM {DOCUMENTS_TABLE} WHERE id = ?", [doc_id]).arrow()
            )

            if df.is_empty():
                return None

            # Convert to dict and handle special fields
            if isinstance(df, pl.DataFrame):
                document = df.to_dicts()[0]
            else:
                document = df.item()

            # Convert None arrays to empty lists for consistency with the Document model
            if document.get("participant_names") is None:
                document["participant_names"] = []

            if document.get("participant_identifiers") is None:
                document["participant_identifiers"] = []

            if document.get("keywords") is None:
                document["keywords"] = []

            # Convert string representation of arrays to actual arrays if needed
            # This is a fallback in case arrays are stored as strings
            for array_field in ["participant_names", "participant_identifiers", "keywords"]:
                if isinstance(document.get(array_field), str) and document[array_field].startswith(
                    "["
                ):
                    try:
                        document[array_field] = json.loads(document[array_field].replace("'", '"'))
                    except json.JSONDecodeError:
                        # If JSON parsing fails, keep the original string
                        pass

            # Parse JSON fields
            for json_field in ["metadata", "contact_metadata", "participant_metadatas"]:
                if json_field in document and document[json_field]:
                    if isinstance(document[json_field], str):
                        try:
                            document[json_field] = json.loads(document[json_field])
                        except json.JSONDecodeError:
                            document[json_field] = (
                                {} if json_field != "participant_metadatas" else []
                            )
                elif json_field == "metadata":
                    document[json_field] = {}
                elif json_field == "contact_metadata":
                    document[json_field] = {}
                elif json_field == "participant_metadatas":
                    document[json_field] = []

            return document

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

            df: pl.DataFrame | pl.Series = pl.from_arrow(conn.execute(query, params).arrow())

            # Convert to list of dicts and handle special fields
            documents = []
            if isinstance(df, pl.DataFrame):
                for row in df.to_dicts():
                    # Convert None arrays to empty lists for consistency with the Document model
                    if row.get("participant_names") is None:
                        row["participant_names"] = []

                    if row.get("participant_identifiers") is None:
                        row["participant_identifiers"] = []

                    if row.get("keywords") is None:
                        row["keywords"] = []

                    # Convert string representation of arrays to actual arrays if needed
                    for array_field in ["participant_names", "participant_identifiers", "keywords"]:
                        if isinstance(row.get(array_field), str) and row[array_field].startswith(
                            "["
                        ):
                            try:
                                row[array_field] = json.loads(row[array_field].replace("'", '"'))
                            except json.JSONDecodeError:
                                # If JSON parsing fails, keep the original string
                                pass

                    # Parse JSON fields
                    for json_field in ["metadata", "contact_metadata", "participant_metadatas"]:
                        if json_field in row and row[json_field]:
                            if isinstance(row[json_field], str):
                                try:
                                    row[json_field] = json.loads(row[json_field])
                                except json.JSONDecodeError:
                                    row[json_field] = (
                                        {} if json_field != "participant_metadatas" else []
                                    )
                        elif json_field == "metadata" or json_field == "contact_metadata":
                            row[json_field] = {}
                        elif json_field == "participant_metadatas":
                            row[json_field] = []

                    documents.append(row)
            else:
                # Handle Series case
                row = df.item()
                # Apply the same conversions as above
                if isinstance(row, dict):
                    if row.get("participant_names") is None:
                        row["participant_names"] = []
                    if row.get("participant_identifiers") is None:
                        row["participant_identifiers"] = []
                    if row.get("keywords") is None:
                        row["keywords"] = []

                    # Process arrays and JSON fields as above
                    for array_field in ["participant_names", "participant_identifiers", "keywords"]:
                        if isinstance(row.get(array_field), str) and row[array_field].startswith(
                            "["
                        ):
                            try:
                                row[array_field] = json.loads(row[array_field].replace("'", '"'))
                            except json.JSONDecodeError:
                                # If JSON parsing fails, keep the original string
                                pass

                    for json_field in ["metadata", "contact_metadata", "participant_metadatas"]:
                        if json_field in row and row[json_field]:
                            if isinstance(row[json_field], str):
                                try:
                                    row[json_field] = json.loads(row[json_field])
                                except json.JSONDecodeError:
                                    row[json_field] = (
                                        {} if json_field != "participant_metadatas" else []
                                    )
                        elif json_field == "metadata" or json_field == "contact_metadata":
                            row[json_field] = {}
                        elif json_field == "participant_metadatas":
                            row[json_field] = []
                documents.append(row)

            return documents

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
