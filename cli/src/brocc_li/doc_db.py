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

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

import duckdb
import lancedb
import polars as pl
from lancedb.embeddings import get_registry
from lancedb.pydantic import Vector
from platformdirs import user_data_dir

from brocc_li.embed.chunk_markdown import chunk_markdown
from brocc_li.merge_md import MergeResultType, merge_md
from brocc_li.types.doc import BaseDocFields, Chunk, Doc, LanceChunk
from brocc_li.utils.chunk_equality import chunks_are_identical
from brocc_li.utils.geolocation import (
    add_geolocation_fields_to_query,
    modify_schema_for_geometry,
)
from brocc_li.utils.logger import logger
from brocc_li.utils.prepare_storage import (
    ARRAY_FIELDS,
    EXCLUDED_FIELDS,
    JSON_FIELDS,
    prepare_chunk_for_storage,
    prepare_document_for_storage,
    prepare_lance_chunk_row,
)
from brocc_li.utils.pydantic_to_sql import generate_create_table_sql, generate_select_sql
from brocc_li.utils.serde import (
    polars_to_dicts,
    process_document_fields,
    process_duckdb_chunk,
)

# Define app information for appdirs
APP_NAME = "brocc"
APP_AUTHOR = "substratelabs"

# Database constants
DEFAULT_DB_FILENAME = "documents.duckdb"
DEFAULT_LANCE_DIRNAME = "vector_store"
DOCUMENTS_TABLE = "docs"
DUCKDB_CHUNKS_TABLE = "chunks"
LANCE_CHUNKS_TABLE = "chunks"


def get_duckdb_path() -> str:
    """Get the default database path in the user's data directory."""
    data_dir = user_data_dir(APP_NAME, APP_AUTHOR)
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, DEFAULT_DB_FILENAME)


def get_lancedb_path() -> str:
    """Get the default LanceDB path in the user's data directory."""
    data_dir = user_data_dir(APP_NAME, APP_AUTHOR)
    lance_dir = os.path.join(data_dir, DEFAULT_LANCE_DIRNAME)
    os.makedirs(lance_dir, exist_ok=True)
    return lance_dir


class DocDB:
    """Handles storage and retrieval of docs using DuckDB and LanceDB."""

    def __init__(self, db_path: str | None = None, lance_path: str | None = None):
        """
        Initialize the storage with the given database paths or the defaults.

        Args:
            db_path: Path to DuckDB database
            lance_path: Path to LanceDB storage
        """
        self.db_path = db_path or get_duckdb_path()
        self.lance_path = lance_path or get_lancedb_path()

        # Status tracking
        self.duckdb_status = {"initialized": False, "error": None, "path": self.db_path}
        self.lancedb_status = {
            "initialized": False,
            "embeddings_available": False,
            "error": None,
            "path": self.lance_path,
        }

        # Ensure parent directories exist before initialization
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.lance_path).mkdir(parents=True, exist_ok=True)

        # Initialize DuckDB
        self._initialize_duckdb()

        # Initialize LanceDB
        self._initialize_lancedb()

    def get_duckdb_status(self) -> dict:
        """Get the current status of DuckDB connection."""
        # Initialize status if it doesn't exist yet
        if not hasattr(self, "duckdb_status") or self.duckdb_status is None:
            self.duckdb_status = {"initialized": False, "error": None, "path": self.db_path}

        try:
            if not self.duckdb_status.get("initialized", False):
                return self.duckdb_status

            # Check if we can actually query the database
            with self._get_connection() as conn:
                # Add null checks for query results
                doc_result = conn.execute(f"SELECT COUNT(*) FROM {DOCUMENTS_TABLE}").fetchone()
                doc_count = doc_result[0] if doc_result is not None else 0

                chunk_result = conn.execute(
                    f"SELECT COUNT(*) FROM {DUCKDB_CHUNKS_TABLE}"
                ).fetchone()
                chunk_count = chunk_result[0] if chunk_result is not None else 0

                # Update status with additional info
                self.duckdb_status.update(
                    {"doc_count": doc_count, "chunk_count": chunk_count, "healthy": True}
                )

                return self.duckdb_status
        except Exception as e:
            self.duckdb_status["error"] = str(e)
            self.duckdb_status["healthy"] = False
            return self.duckdb_status

    def get_lancedb_status(self) -> dict:
        """Get the current status of LanceDB connection."""
        # Initialize status if it doesn't exist yet
        if not hasattr(self, "lancedb_status") or self.lancedb_status is None:
            self.lancedb_status = {
                "initialized": False,
                "embeddings_available": False,
                "error": None,
                "path": self.lance_path,
            }

        try:
            if not self.lancedb_status.get("initialized", False):
                return self.lancedb_status

            if self.lance_db is not None:
                # Check if we can actually access the table
                try:
                    table = self.lance_db.open_table(LANCE_CHUNKS_TABLE)

                    # Get chunk count using Polars by following the exact API pattern
                    try:
                        # Get Arrow table first (which is what to_polars() does internally)
                        arrow_table = table.to_arrow()

                        # Convert Arrow table to Polars DataFrame (identical to to_polars implementation)
                        df = pl.from_arrow(arrow_table)

                        # Now we have a Polars DataFrame to work with!
                        chunk_count = len(df)

                        # Update status with additional info
                        self.lancedb_status.update({"chunk_count": chunk_count, "healthy": True})
                        logger.debug(f"Got count from Polars: {chunk_count} chunks")
                    except Exception as e:
                        # If Arrow/Polars conversion fails, just update status
                        self.lancedb_status.update(
                            {"healthy": False, "error": f"Failed to convert to Polars: {str(e)}"}
                        )
                        logger.warning(f"Error with Arrow/Polars conversion: {e}")
                except Exception as e:
                    if self.lancedb_status is not None:  # Extra safety check
                        self.lancedb_status["error"] = f"Failed to access table: {str(e)}"
                        self.lancedb_status["healthy"] = False
            else:
                if self.lancedb_status is not None:  # Extra safety check
                    self.lancedb_status["healthy"] = False

            return self.lancedb_status
        except Exception as e:
            if self.lancedb_status is not None:  # Extra safety check
                self.lancedb_status["error"] = str(e)
                self.lancedb_status["healthy"] = False
            else:
                # Create new status dict if it somehow became None
                self.lancedb_status = {
                    "initialized": False,
                    "embeddings_available": False,
                    "error": str(e),
                    "healthy": False,
                    "path": self.lance_path,
                }
            return self.lancedb_status

    def _initialize_lancedb(self) -> None:
        """Initialize LanceDB connection and create table if it doesn't exist."""
        try:
            # Connect to LanceDB
            self.lance_db = lancedb.connect(self.lance_path)
            self.lancedb_status["initialized"] = True

            # Default embedding status
            self.lancedb_status["embeddings_available"] = False
            self.lancedb_status["embeddings_status"] = "Not configured"
            self.lancedb_status["embeddings_details"] = None

            # Setup VoyageAI embeddings first - regardless of table existence
            voyage_ai = None
            try:
                registry = get_registry()
                try:
                    voyage_ai = registry.get("voyageai").create()
                    logger.debug("Successfully loaded VoyageAI embedding function")
                    self.lancedb_status["embeddings_available"] = True
                    self.lancedb_status["embeddings_status"] = "Ready"
                    self.lancedb_status["embeddings_details"] = "VoyageAI loaded"
                except Exception as ve:
                    logger.error(f"Failed to create VoyageAI embedding function: {ve}")
                    self.lancedb_status["embeddings_status"] = "Error loading VoyageAI"
                    self.lancedb_status["embeddings_details"] = f"Error: {str(ve)}"
            except Exception as re:
                logger.error(f"Failed to get embeddings registry: {re}")
                self.lancedb_status["embeddings_status"] = "Error with registry"
                self.lancedb_status["embeddings_details"] = f"Error: {str(re)}"

            # Check if chunks table exists, if not create it
            tables = self.lance_db.table_names()

            if LANCE_CHUNKS_TABLE not in tables:
                # Create table with or without embeddings based on availability
                try:
                    if self.lancedb_status["embeddings_available"] and voyage_ai is not None:
                        # Create with embeddings
                        class ChunkModelWithEmbedding(LanceChunk):
                            # Override content to be a SourceField for embedding
                            # Make type match the base class (now non-optional)
                            content: str = voyage_ai.SourceField()
                            # Specify vector field with proper inline Vector factory function
                            # The string annotation allows this to work with __future__.annotations
                            vector: "Vector(voyage_ai.ndims())" = voyage_ai.VectorField()  # pyright: ignore[reportInvalidTypeForm]

                        # Create the table with the ChunkModel schema
                        self.lance_db.create_table(
                            LANCE_CHUNKS_TABLE, schema=ChunkModelWithEmbedding, mode="overwrite"
                        )
                        logger.debug(
                            f"Created LanceDB table with VoyageAI embeddings: {LANCE_CHUNKS_TABLE}"
                        )
                    else:
                        # Create without embeddings
                        logger.warning("Creating LanceDB table without embeddings capability")
                        self.lance_db.create_table(
                            LANCE_CHUNKS_TABLE, schema=LanceChunk, mode="overwrite"
                        )
                        logger.debug(
                            f"Created LanceDB table without embeddings: {LANCE_CHUNKS_TABLE}"
                        )
                except Exception as te:
                    logger.error(f"Failed to create LanceDB table: {te}")
                    self.lancedb_status["embeddings_status"] = "Table creation failed"
                    self.lancedb_status["embeddings_details"] = f"Error: {str(te)}"

            else:
                logger.debug(f"LanceDB table {LANCE_CHUNKS_TABLE} already exists")
                # Check if table has a vector field - for backward compatibility
                try:
                    table = self.lance_db.open_table(LANCE_CHUNKS_TABLE)
                    schema = table.schema
                    if "vector" in schema.names and not self.lancedb_status["embeddings_available"]:
                        # Vector field exists but VoyageAI failed to load - show warning
                        self.lancedb_status["embeddings_status"] = (
                            "Table has vector field but embedding model not available"
                        )
                        self.lancedb_status["embeddings_details"] = (
                            "Existing vectors can be searched but new ones can't be created"
                        )
                    elif (
                        "vector" not in schema.names and self.lancedb_status["embeddings_available"]
                    ):
                        # VoyageAI available but table has no vector field - show warning about recreation
                        self.lancedb_status["embeddings_status"] = (
                            "Embedding model available but table needs to be recreated"
                        )
                        self.lancedb_status["embeddings_details"] = (
                            "Consider backing up and recreating the database"
                        )
                except Exception as e:
                    logger.error(f"Failed to check table schema: {e}")
                    self.lancedb_status["embeddings_status"] = "Schema check failed"
                    self.lancedb_status["embeddings_details"] = f"Error: {str(e)}"

        except Exception as e:
            self.lancedb_status["error"] = str(e)
            self.lancedb_status["embeddings_status"] = "LanceDB initialization failed"
            self.lancedb_status["embeddings_details"] = f"Error: {str(e)}"
            logger.error(f"Failed to initialize LanceDB: {e}")
            # Continue without LanceDB
            self.lance_db = None

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get a DuckDB connection with the spatial extension loaded."""
        conn = duckdb.connect(self.db_path)
        try:
            # Attempt to load spatial extension
            conn.execute("LOAD spatial;")
        except Exception as e:
            # If loading fails, try installing first (might not be present)
            try:
                logger.debug("Spatial extension not loaded, attempting install...")
                conn.execute("INSTALL spatial;")
                conn.execute("LOAD spatial;")
                logger.success("Spatial extension installed and loaded successfully.")
            except Exception as install_e:
                logger.warning(
                    f"Could not install/load spatial extension. Location features may fail. Load error: {e}, Install error: {install_e}"
                )
        return conn

    def _initialize_duckdb(self) -> None:
        """Set up the database and create tables if they don't exist."""
        # Create the parent directory if it doesn't exist
        # Moved to __init__ to ensure it exists before any connection attempt

        try:
            with self._get_connection() as conn:  # Use the helper to ensure spatial is loaded
                # Generate the CREATE TABLE statement dynamically for documents
                # Generate SQL normally first
                create_documents_sql = generate_create_table_sql(Doc, DOCUMENTS_TABLE)
                # Modify the generated SQL to use GEOMETRY type for location
                create_documents_sql = modify_schema_for_geometry(create_documents_sql)

                conn.execute(create_documents_sql)

                # Generate the CREATE TABLE statement for chunks
                create_chunks_sql = generate_create_table_sql(Chunk, DUCKDB_CHUNKS_TABLE)
                conn.execute(create_chunks_sql)

            # If we get here without exception, DuckDB is initialized
            self.duckdb_status["initialized"] = True
        except Exception as e:
            self.duckdb_status["error"] = str(e)
            logger.error(f"Failed to initialize DuckDB: {e}")

    def url_exists(self, url: str) -> bool:
        """Check if a document with the given URL already exists."""
        if not url:
            return False

        with self._get_connection() as conn:
            result = conn.execute(
                f"SELECT COUNT(*) FROM {DOCUMENTS_TABLE} WHERE url = ?", [url]
            ).fetchone()
            return result is not None and result[0] > 0

    def get_seen_urls(self, source: str | None = None) -> set[str]:
        """Get a set of URLs that have already been seen."""
        with self._get_connection() as conn:
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

        # Generate the base SELECT statement dynamically
        base_select = generate_select_sql(
            Doc,
            DOCUMENTS_TABLE,
            # Exclude text_content (not stored) and geolocation (handled specially)
            exclude_fields=EXCLUDED_FIELDS | {"text_content", "geolocation"},
        )

        with self._get_connection() as conn:
            # Add WHERE and ORDER BY clauses
            query = f"{base_select} WHERE url = ? ORDER BY ingested_at DESC"
            # Add geolocation handling
            select_query = add_geolocation_fields_to_query(query)
            df = pl.from_arrow(conn.execute(select_query, [url]).arrow())

            if df.is_empty():
                return []

            # Convert to list of native Python dictionaries
            raw_dicts = polars_to_dicts(df)
            return [process_document_fields(doc, ARRAY_FIELDS, JSON_FIELDS) for doc in raw_dicts]

    def get_duckdb_chunks(self, doc_id: str) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            df = pl.from_arrow(
                conn.execute(
                    f"SELECT * FROM {DUCKDB_CHUNKS_TABLE} WHERE doc_id = ? ORDER BY chunk_index",
                    [doc_id],
                ).arrow()
            )

            if df.is_empty():
                return []

            # Convert to list of native Python dictionaries
            raw_dicts = polars_to_dicts(df)
            return [process_duckdb_chunk(chunk) for chunk in raw_dicts]

    def vector_search(
        self,
        query: str,
        limit: int = 10,
        filter_str: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.lance_db:
            logger.warning(
                "Vector search unavailable - LanceDB not properly initialized with embeddings"
            )
            return []
        try:
            table = self.lance_db.open_table(LANCE_CHUNKS_TABLE)

            # With the LanceModel approach, we can search directly with the text query
            # The embedding will be generated automatically
            # Explicitly specify vector column name
            search_query = table.search(query, vector_column_name="vector")

            # Apply filter if provided
            if filter_str:
                search_query = search_query.where(filter_str)

            # Execute search
            results = search_query.limit(limit).to_list()

            # Format results
            formatted_results = []
            for item in results:
                # Start with core chunk fields
                result = {
                    "id": item["id"],
                    "doc_id": item["doc_id"],
                    "score": item["_distance"],  # Similarity score
                    "chunk_index": item["chunk_index"],
                    "chunk_total": item["chunk_total"],
                }

                # Add all available BaseDocFields
                base_fields = set(BaseDocFields.model_fields.keys())
                for field in base_fields:
                    if field in item:
                        result[field] = item[field]

                # Process JSON fields if they're strings
                for json_field, default_value in JSON_FIELDS.items():
                    if json_field in result and isinstance(result[json_field], str):
                        try:
                            result[json_field] = json.loads(result[json_field])
                        except json.JSONDecodeError:
                            result[json_field] = default_value

                # Process array fields
                for array_field in ARRAY_FIELDS:
                    if array_field in result:
                        if result[array_field] is None:
                            result[array_field] = []
                        elif isinstance(result[array_field], str):
                            # Handle array stored as a JSON string
                            try:
                                result[array_field] = json.loads(result[array_field])
                            except json.JSONDecodeError:
                                result[array_field] = []
                formatted_results.append(result)

            return formatted_results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def get_document_by_id(self, doc_id: str) -> dict[str, Any] | None:
        """Retrieve a document by its ID."""
        if not doc_id:
            return None

        # Generate the base SELECT statement dynamically
        base_select = generate_select_sql(
            Doc,
            DOCUMENTS_TABLE,
            # Exclude text_content (not stored) and geolocation (handled specially)
            exclude_fields=EXCLUDED_FIELDS | {"text_content", "geolocation"},
        )

        with self._get_connection() as conn:
            # Add WHERE clause
            query = f"{base_select} WHERE id = ?"
            # Add geolocation handling
            select_query = add_geolocation_fields_to_query(query)
            df = pl.from_arrow(conn.execute(select_query, [doc_id]).arrow())

            if df.is_empty():
                return None

            # Convert to a plain Python dictionary
            raw_dicts = polars_to_dicts(df)
            if raw_dicts:
                return process_document_fields(raw_dicts[0], ARRAY_FIELDS, JSON_FIELDS)
            return None

    def get_documents(
        self,
        source: str | None = None,
        source_location: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        # Generate the base SELECT statement dynamically from the Doc model
        # Exclude fields not stored directly in the table
        base_select = generate_select_sql(
            Doc,
            DOCUMENTS_TABLE,
            # Exclude text_content (not stored) and geolocation (handled specially)
            exclude_fields=EXCLUDED_FIELDS | {"text_content", "geolocation"},
        )

        with self._get_connection() as conn:
            query = base_select  # Start with the generated SELECT
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

            # Add geolocation handling to the dynamically generated query
            # This adds ST_AsText(geolocation) AS geolocation_wkt OR just selects existing columns
            select_query = add_geolocation_fields_to_query(query)

            df = pl.from_arrow(conn.execute(select_query, params).arrow())

            if df.is_empty():
                return []

            # Convert to list of native Python dictionaries
            raw_dicts = polars_to_dicts(df)
            # Process fields
            return [process_document_fields(doc, ARRAY_FIELDS, JSON_FIELDS) for doc in raw_dicts]

    def _reconstruct_text_from_chunks(self, chunks: List[Dict[str, Any]]) -> str:
        """Reconstructs the original text content from a list of chunks."""
        all_text_blocks = []
        for chunk in sorted(chunks, key=lambda c: c["chunk_index"]):  # Ensure order
            if isinstance(chunk.get("content"), list):  # Check if content is a list
                chunk_text = "\n\n".join(
                    item["text"] for item in chunk["content"] if item.get("type") == "text"
                )
                if chunk_text:
                    all_text_blocks.append(chunk_text)
        return "\n\n".join(all_text_blocks)

    def _find_id_for_update(
        self,
        document: dict[str, Any],
        db_document: dict[str, Any],
        new_chunks: list[Chunk],
        new_text_content: str,
    ) -> tuple[str | None, bool, str | None]:
        """
        Determine if an existing document should be updated, potentially merging content.

        Returns:
            tuple: (doc_id_to_update, should_update_chunks, content_to_use)
            - doc_id_to_update: ID of document to update, or None if creating new.
            - should_update_chunks: Whether chunks need updating (True if content changed or merged).
            - content_to_use: The final text content (merged or new) to generate chunks from.
        """
        doc_id = document.get("id")
        url = document.get("url")

        # --- Check by ID first ---
        if doc_id:
            existing_doc = self.get_document_by_id(doc_id)
            if existing_doc:
                existing_chunks = self.get_duckdb_chunks(doc_id)
                if chunks_are_identical(existing_chunks, new_chunks):
                    logger.debug(
                        f"Document {doc_id} found by ID, content identical. Updating metadata only."
                    )
                    return doc_id, False, None  # Update metadata only

                # Content differs, attempt merge
                logger.debug(f"Document {doc_id} found by ID, content differs. Attempting merge.")
                existing_text = self._reconstruct_text_from_chunks(existing_chunks)
                merge_result = merge_md(existing_text, new_text_content)

                if merge_result.type == MergeResultType.MERGED:
                    logger.info(
                        f"Merge successful for doc ID {doc_id}. Updating with merged content."
                    )
                    return doc_id, True, merge_result.content  # Update with merged content
                else:
                    logger.info(f"Merge not possible for doc ID {doc_id}. Creating new document.")
                    return None, True, new_text_content  # Create new document

        # --- Check by URL if no ID match or ID not provided ---
        if url:
            matching_docs = self.get_documents_by_url(url)
            if matching_docs:
                # Use the most recent existing document by URL
                update_id = matching_docs[0]["id"]
                existing_chunks = self.get_duckdb_chunks(update_id)

                if chunks_are_identical(existing_chunks, new_chunks):
                    logger.debug(
                        f"Document {update_id} found by URL, content identical. Updating metadata only."
                    )
                    # Ensure the incoming document object uses the found ID
                    if not document.get("id"):
                        document["id"] = update_id
                        db_document["id"] = update_id
                    return update_id, False, None  # Update metadata only

                # Content differs, attempt merge
                logger.debug(
                    f"Document {update_id} found by URL, content differs. Attempting merge."
                )
                existing_text = self._reconstruct_text_from_chunks(existing_chunks)
                merge_result = merge_md(existing_text, new_text_content)

                if merge_result.type == MergeResultType.MERGED:
                    logger.info(
                        f"Merge successful for doc URL {url} (ID {update_id}). Updating with merged content."
                    )
                    # Ensure the incoming document object uses the found ID
                    if not document.get("id") or document.get("id") != update_id:
                        document["id"] = update_id
                        db_document["id"] = update_id
                    return update_id, True, merge_result.content  # Update with merged content
                else:
                    logger.info(
                        f"Merge not possible for doc URL {url} (ID {update_id}). Creating new document."
                    )
                    return None, True, new_text_content  # Create new document

        # No existing document found by ID or URL, or merge failed
        logger.debug("No existing document found or merge failed. Creating new document.")
        return None, True, new_text_content  # Create new

    def _update_document(self, conn, db_document: dict[str, Any], doc_id: str) -> None:
        """Execute the UPDATE statement for a given document ID."""
        set_clauses = []
        params = []

        # The document has already been prepared for storage, so we can trust its fields
        # However, we still need to exclude "id" and fields in EXCLUDED_FIELDS
        for key, value in db_document.items():
            if (
                key != "id" and key not in EXCLUDED_FIELDS
            ):  # Skip id field and excluded fields like text_content
                if key == "geolocation" and value is not None:
                    # Use ST_Point function for location update
                    set_clauses.append(f"{key} = ST_GeomFromText(?)")
                    params.append(value)  # value is already the WKT string 'POINT (lon lat)'
                else:
                    set_clauses.append(f"{key} = ?")
                    params.append(value)

        if not set_clauses:
            logger.warning(f"No fields to update for document ID {doc_id}")
            return

        params.append(doc_id)  # Add the ID for the WHERE clause
        update_query = f"UPDATE {DOCUMENTS_TABLE} SET {', '.join(set_clauses)} WHERE id = ?"
        conn.execute(update_query, params)

    def _insert_document(self, conn, db_document: dict[str, Any]) -> None:
        # Ensure document has an ID
        if not db_document.get("id"):
            db_document["id"] = Doc.generate_id()

        # The document has been prepared, but still need to filter out excluded fields
        filtered_doc = {k: v for k, v in db_document.items() if k not in EXCLUDED_FIELDS}

        columns = []
        placeholders = []
        values = []

        for key, value in filtered_doc.items():
            columns.append(key)
            if key == "geolocation" and value is not None:
                # Use ST_Point function for location insert
                placeholders.append("ST_GeomFromText(?)")
                values.append(value)  # value is already the WKT string 'POINT (lon lat)'
            else:
                placeholders.append("?")
                values.append(value)

        columns_str = ", ".join(columns)
        placeholders_str = ", ".join(placeholders)
        insert_query = f"INSERT INTO {DOCUMENTS_TABLE} ({columns_str}) VALUES ({placeholders_str})"
        conn.execute(insert_query, values)

    def _store_duckdb_chunks(self, conn, chunks: list[Chunk]) -> None:
        """
        Store multiple chunks in the DuckDB database.

        This method handles the DuckDB-specific storage of chunks, which differs from
        LanceDB storage in that it:
        1. Stores the content field directly as a JSON string
        2. Does not include document metadata
        3. Does not generate vector embeddings

        Args:
            conn: DuckDB connection
            chunks: List of Chunk objects to store
        """
        for chunk in chunks:
            db_chunk = prepare_chunk_for_storage(chunk)
            columns = ", ".join(db_chunk.keys())
            placeholders = ", ".join(["?"] * len(db_chunk))
            insert_query = f"INSERT INTO {DUCKDB_CHUNKS_TABLE} ({columns}) VALUES ({placeholders})"
            conn.execute(insert_query, list(db_chunk.values()))

    def _store_lance_chunks(self, chunks: list[Chunk], doc: Dict[str, Any]) -> None:
        """
        Store chunks in LanceDB with all the metadata from the document.

        This method handles the special formatting required for LanceDB storage, which differs
        from DuckDB storage in several ways:
        1. Content is wrapped in a structured format with a header
        2. The entire content structure is JSON serialized as a single string
        3. Document metadata is merged with chunk data
        4. The resulting data is used to generate vector embeddings

        Args:
            chunks: List of chunk objects to store
            doc: Document data with metadata for filtering
        """
        if not self.lance_db:
            logger.warning(
                "Vector storage unavailable - LanceDB not properly initialized with embeddings"
            )
            return

        try:
            # Get the table
            table = self.lance_db.open_table(LANCE_CHUNKS_TABLE)

            # Prepare data for LanceDB
            lance_data = []

            for chunk in chunks:
                # Use the helper function to prepare the complete row for LanceDB
                row = prepare_lance_chunk_row(chunk, doc)
                lance_data.append(row)

            # Store chunks in LanceDB - the embedding will be generated automatically
            if lance_data:
                try:
                    table.add(lance_data)
                    logger.debug(f"Added {len(lance_data)} chunks to LanceDB with auto-embeddings")
                except Exception as e:
                    logger.error(f"Failed to add data to LanceDB: {e}")
        except Exception as e:
            logger.error(f"Failed to store in LanceDB: {e}")
            # If we hit an exception accessing the table, mark lance_db as None to avoid future attempts
            self.lance_db = None
            logger.warning(
                "Vector storage disabled due to error - future operations will be skipped"
            )

    def _delete_chunks(self, conn, doc_id: str) -> None:
        """
        Delete all chunks associated with a document ID from both DuckDB and LanceDB.

        This method ensures chunks are removed from both storage systems to maintain
        consistency between the databases.

        Args:
            conn: DuckDB connection
            doc_id: The document ID whose chunks should be deleted
        """
        conn.execute(f"DELETE FROM {DUCKDB_CHUNKS_TABLE} WHERE doc_id = ?", [doc_id])

        # Also delete from LanceDB
        if self.lance_db:
            try:
                table = self.lance_db.open_table(LANCE_CHUNKS_TABLE)
                # Delete where doc_id matches
                table.delete(f"doc_id = '{doc_id}'")
                logger.debug(f"Deleted chunks for doc_id {doc_id} from LanceDB")
            except Exception as e:
                logger.error(f"Failed to delete from LanceDB: {e}")
                # If we encounter an error, mark lance_db as None to avoid future attempts
                self.lance_db = None
                logger.warning(
                    "Vector storage disabled due to error - future operations will be skipped"
                )

    def store_document(self, document: Doc) -> bool:
        """
        Store a document in the database, updating if it already exists.
        If content differs but is mergeable, updates with merged content.
        Otherwise, creates a new document entry.

        Args:
            document: A Doc object that must contain text_content for chunking.

        Returns:
            bool: True if the document was stored successfully.

        Raises:
            ValueError: If document doesn't contain required text_content field.
        """
        # Convert to dict for processing
        doc_dict = document.model_dump()

        # Ensure location is properly captured
        if hasattr(document, "geolocation") and document.geolocation is not None:
            doc_dict["geolocation"] = document.geolocation
        elif "geolocation" not in doc_dict:
            doc_dict["geolocation"] = None

        # Require text_content
        text_content = doc_dict.pop("text_content", None)
        if text_content is None:  # Check for None specifically, allow empty string
            raise ValueError("Document must contain text_content field for chunking")

        # Create a copy of the document data to avoid modifying the original
        doc_data = doc_dict.copy()
        original_id = doc_data.get("id")

        # Generate initial chunks from the *incoming* text content to check for identity
        # We may regenerate these later if merging happens.
        initial_chunked_content = chunk_markdown(text_content)
        initial_doc_obj_for_chunking = Doc(**doc_data)  # Use a temporary Doc for chunk ID gen
        initial_chunks = Doc.create_chunks_for_doc(
            initial_doc_obj_for_chunking, initial_chunked_content
        )

        with self._get_connection() as conn:
            # Check if an existing document needs to be updated or merged
            id_to_update, should_update_chunks, content_to_use = self._find_id_for_update(
                doc_data, doc_data, initial_chunks, text_content
            )

            if id_to_update:
                # Existing document found (either by ID or URL)
                db_document = prepare_document_for_storage(
                    doc_data
                )  # Prepare with potentially updated ID
                self._update_document(conn, db_document, id_to_update)
                logger.debug(f"Updated metadata for document ID {id_to_update}")

                if should_update_chunks:
                    # Content was merged, need to regenerate chunks
                    logger.debug(
                        f"Content merged for {id_to_update}. Regenerating and replacing chunks."
                    )
                    if content_to_use is None:
                        # Should not happen if should_update_chunks is True, but defensively handle
                        logger.error(
                            f"Error: should_update_chunks is True but content_to_use is None for doc {id_to_update}. Skipping chunk update."
                        )
                        return False  # Indicate potential issue

                    # Regenerate chunks based on the merged content
                    merged_chunked_content = chunk_markdown(content_to_use)
                    # Important: Use the *updated* doc_data (which now has the correct ID) for chunk creation
                    doc_obj_for_merged_chunks = Doc(**doc_data)
                    merged_chunks = Doc.create_chunks_for_doc(
                        doc_obj_for_merged_chunks, merged_chunked_content
                    )

                    # Delete old chunks and store new ones
                    self._delete_chunks(conn, id_to_update)
                    self._store_duckdb_chunks(conn, merged_chunks)
                    self._store_lance_chunks(merged_chunks, doc_data)  # Pass doc_data for metadata
                # else: Content was identical, only metadata was updated above.

            else:
                # No suitable existing document found, or merge wasn't possible/chosen.
                # Create a completely new document entry.
                logger.debug("Creating new document entry.")

                # Ensure a unique ID if the original ID belonged to a doc we decided not to update
                if original_id and self.get_document_by_id(original_id):
                    new_id = Doc.generate_id()
                    logger.debug(f"Original ID {original_id} exists, generating new ID {new_id}")
                    doc_data["id"] = new_id
                elif not doc_data.get("id"):
                    # If no original ID or if ID was already None
                    doc_data["id"] = Doc.generate_id()
                    logger.debug(f"No initial ID, generated new ID {doc_data['id']}")

                # Generate chunks using the new/final content_to_use
                if content_to_use is None:
                    # If merge failed, content_to_use is the original text_content
                    content_to_use = text_content

                final_chunked_content = chunk_markdown(content_to_use)
                # Ensure the doc object used for chunking has the final correct ID
                doc_obj_for_new_chunks = Doc(**doc_data)
                final_chunks = Doc.create_chunks_for_doc(
                    doc_obj_for_new_chunks, final_chunked_content
                )

                # Prepare document for storage (with final ID)
                db_document = prepare_document_for_storage(doc_data)

                # Insert new document and its chunks
                self._insert_document(conn, db_document)
                self._store_duckdb_chunks(conn, final_chunks)
                self._store_lance_chunks(final_chunks, doc_data)

        return True

    def launch_duckdb_ui(self) -> None:
        """https://duckdb.org/docs/stable/extensions/ui.html"""
        import time
        import webbrowser

        # Use the helper to ensure extensions can be loaded if needed
        with self._get_connection() as conn:
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
