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

import inspect
import json
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Union, get_args, get_origin

import duckdb
import polars as pl
from platformdirs import user_data_dir
from pydantic import BaseModel

from brocc_li.types.doc import Doc

# Define app information for appdirs
APP_NAME = "brocc"
APP_AUTHOR = "substratelabs"

# Database constants
DEFAULT_DB_FILENAME = "documents.duckdb"
DOCUMENTS_TABLE = "documents"

# Mapping from Pydantic/Python types to DuckDB SQL types
# Note: Enums and datetimes (stored as strings) are mapped to VARCHAR
# Note: Optional types are mapped to their underlying type (DuckDB columns are nullable by default)
# Note: Dict is mapped to JSON
# Note: List[str] is mapped to VARCHAR[]
TYPE_MAPPING = {
    str: "VARCHAR",
    int: "BIGINT",  # Using BIGINT for safety, though INTEGER might suffice
    float: "DOUBLE",
    bool: "BOOLEAN",
    datetime: "VARCHAR",  # Stored as formatted string
    bytes: "BLOB",
    list: "VARCHAR[]",  # Default for lists, refine below for specific types like List[str]
    dict: "JSON",
    Enum: "VARCHAR",  # Store enum value
}


def _get_sql_type(field_type: Any) -> str:
    """Map a Python/Pydantic type hint to a DuckDB SQL type."""
    origin = get_origin(field_type)
    args = get_args(field_type)

    if origin is Union or origin == getattr(
        Union, "__origin__", None
    ):  # Handles Optional[T] which is Union[T, None]
        # Filter out NoneType and get the first actual type
        non_none_args = [arg for arg in args if arg is not type(None)]
        if non_none_args:
            # Recursively get the type for the first non-None type
            return _get_sql_type(non_none_args[0])
        else:
            # Should not happen for Optional[T] but handle just in case
            return "VARCHAR"  # Default fallback

    if origin is list or origin is list:
        if args and args[0] is str:
            return "VARCHAR[]"
        elif args and args[0] is dict:
            # DuckDB doesn't directly support LIST<JSON>, so serialize or use STRUCT if needed.
            # Storing as JSON string array might be an option, but VARCHAR[] is simpler for now if items are simple.
            # Let's default to VARCHAR[] for list of dicts for now, assuming simple structures or string representations.
            # A better approach might be to store the whole list as a single JSON string.
            # For participant_metadatas (List[Dict[str, Any]]), JSON seems more appropriate for the whole list.
            # Let's refine this specifically for known fields later if needed.
            # Defaulting List[Dict] to JSON for the whole list.
            return "JSON"  # Store the whole list as a JSON string
        else:
            # Fallback for other list types
            return TYPE_MAPPING.get(list, "VARCHAR[]")  # Default list type

    if origin is dict or origin is dict:
        return TYPE_MAPPING.get(dict, "JSON")

    # Handle Enum types by checking inheritance
    if inspect.isclass(field_type) and issubclass(field_type, Enum):
        return TYPE_MAPPING.get(Enum, "VARCHAR")

    # Handle basic types
    return TYPE_MAPPING.get(field_type, "VARCHAR")  # Default to VARCHAR if type not found


def _generate_create_table_sql(model: type[BaseModel], table_name: str) -> str:
    """Generate a CREATE TABLE SQL statement from a Pydantic model."""
    columns = []
    for name, field in model.model_fields.items():
        sql_type = _get_sql_type(field.annotation)

        # Handle specific overrides for complex types if needed
        # Example: participant_metadatas is Optional[List[Dict[str, Any]]]
        if name == "participant_metadatas":
            sql_type = "JSON"  # Store the list of dicts as a single JSON string

        column_def = f"{name} {sql_type}"
        if name == "id":  # Assuming 'id' is always the primary key
            column_def += " PRIMARY KEY"
        columns.append(column_def)

    # Add fields present in the old schema but not in Doc model, if strictly needed.
    # For now, adhering strictly to the Doc model + last_updated.
    columns.append("last_updated VARCHAR")  # Add last_updated manually

    columns_sql = ",\n                    ".join(columns)
    return f"CREATE TABLE IF NOT EXISTS {table_name} (\n                    {columns_sql}\n                )"


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
            create_table_sql = _generate_create_table_sql(Doc, DOCUMENTS_TABLE)
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

                    documents.append(row)
            else:
                # Handle Series case
                documents.append(df.item())

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
        # Assuming participant_names/identifiers are VARCHAR[] and metadatas is JSON based on _get_sql_type logic.
        if prepared_doc.get("participant_names") == []:
            prepared_doc["participant_names"] = None  # For VARCHAR[]
        if prepared_doc.get("participant_identifiers") == []:
            prepared_doc["participant_identifiers"] = None  # For VARCHAR[]
        # participant_metadatas is mapped to JSON, so empty list [] is fine for json.dumps

        # Convert metadata and participant_metadatas to JSON string
        prepared_doc["metadata"] = json.dumps(prepared_doc.get("metadata") or {})
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

            # DuckDB returns JSON as a string, parse it back to dict
            if "metadata" in document and document["metadata"]:
                document["metadata"] = json.loads(document["metadata"])
            else:
                document["metadata"] = {}

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

                    documents.append(row)
            else:
                # Handle Series case
                documents.append(df.item())

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
