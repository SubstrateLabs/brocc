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

import duckdb
import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Set, Union
from platformdirs import user_data_dir
from pathlib import Path
from brocc_li.types.doc import Doc
import polars as pl

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

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the storage with the given database path or the default."""
        self.db_path = db_path or get_default_db_path()
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Set up the database and create tables if they don't exist."""
        # Create the parent directory if it doesn't exist
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with duckdb.connect(self.db_path) as conn:
            # Create documents table if it doesn't exist
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {DOCUMENTS_TABLE} (
                    id VARCHAR PRIMARY KEY,
                    url VARCHAR,
                    title VARCHAR,
                    description VARCHAR,
                    text_content VARCHAR,
                    image_data VARCHAR,
                    author_name VARCHAR,
                    author_identifier VARCHAR,
                    participant_names VARCHAR[],
                    participant_identifiers VARCHAR[],
                    created_at VARCHAR,
                    metadata JSON,  -- Native JSON type
                    source VARCHAR,
                    source_location_identifier VARCHAR,
                    source_location_name VARCHAR,
                    ingested_at VARCHAR,
                    last_updated VARCHAR
                )
            """)

    def url_exists(self, url: str) -> bool:
        """Check if a document with the given URL already exists."""
        if not url:
            return False

        with duckdb.connect(self.db_path) as conn:
            result = conn.execute(
                f"SELECT COUNT(*) FROM {DOCUMENTS_TABLE} WHERE url = ?", [url]
            ).fetchone()
            return result is not None and result[0] > 0

    def get_seen_urls(self, source: Optional[str] = None) -> Set[str]:
        """Get a set of URLs that have already been seen."""
        with duckdb.connect(self.db_path) as conn:
            query = f"SELECT url FROM {DOCUMENTS_TABLE}"
            params = []

            if source:
                query += " WHERE source = ?"
                params.append(source)

            df: Union[pl.DataFrame, pl.Series] = pl.from_arrow(
                conn.execute(query, params).arrow()
            )
            return set(df["url"].drop_nulls().to_list())

    def get_documents_by_url(self, url: str) -> List[Dict[str, Any]]:
        """Retrieve all documents with the given URL."""
        if not url:
            return []

        with duckdb.connect(self.db_path) as conn:
            df: Union[pl.DataFrame, pl.Series] = pl.from_arrow(
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

    def store_document(self, document: Dict[str, Any]) -> bool:
        """Store a document in the database, updating if it already exists."""
        # Validate document structure using Pydantic model
        try:
            # Convert dict to Document model to validate
            doc = Doc(**document)
            # Convert back to dict for storage
            document = doc.model_dump()
        except Exception as e:
            raise ValueError(f"Invalid document structure: {str(e)}")

        # Format timestamps consistently
        document["last_updated"] = Doc.format_date(datetime.now())
        if not document.get("ingested_at"):
            document["ingested_at"] = Doc.format_date(datetime.now())

        # Convert enum values to strings
        for key, value in document.items():
            if hasattr(value, "value"):  # Check if it's an enum
                document[key] = value.value

        # Make a copy of the document for database operations
        db_document = document.copy()

        # Ensure array fields are properly handled - empty lists should be None for DuckDB arrays
        if document.get("participant_names") == []:
            db_document["participant_names"] = None

        if document.get("participant_identifiers") == []:
            db_document["participant_identifiers"] = None

        # Convert metadata to JSON string for DuckDB
        if "metadata" in db_document:
            import json

            # DuckDB expects a JSON string for its JSON type
            db_document["metadata"] = json.dumps(db_document["metadata"])

        with duckdb.connect(self.db_path) as conn:
            # Determine if this is an update or insert
            is_update = False
            update_condition = None
            update_param = None

            # First priority: update by ID if exists
            if document.get("id"):
                existing_doc = self.get_document_by_id(document["id"])
                if existing_doc:
                    is_update = True
                    update_condition = "id = ?"
                    update_param = document["id"]

            # Second priority: update by URL if ID doesn't exist or didn't match
            if not is_update and document.get("url"):
                # Check if any documents exist with this URL
                matching_docs = self.get_documents_by_url(document["url"])
                if matching_docs:
                    # If there's just one match, update it
                    if len(matching_docs) == 1:
                        is_update = True
                        update_condition = "url = ?"
                        update_param = document["url"]
                    # If multiple matches, set doc["id"] to the most recent matching doc's ID
                    else:
                        # Set the ID to the most recent one (returned first from get_documents_by_url)
                        most_recent_id = matching_docs[0]["id"]
                        # Use the existing ID for this update
                        if not document.get("id"):
                            document["id"] = most_recent_id
                            db_document["id"] = most_recent_id

                        is_update = True
                        update_condition = "id = ?"
                        update_param = most_recent_id

            if is_update:
                # Update the existing document
                set_clauses = []
                params = []

                for key, value in db_document.items():
                    if key != "id":  # Don't update the ID
                        set_clauses.append(f"{key} = ?")
                        params.append(value)

                # Add the condition parameter
                params.append(update_param)

                conn.execute(
                    f"UPDATE {DOCUMENTS_TABLE} SET {', '.join(set_clauses)} WHERE {update_condition}",
                    params,
                )
            else:
                # Ensure document has an ID
                if not document.get("id"):
                    db_document["id"] = Doc.generate_id()

                # Insert new document
                columns = ", ".join(db_document.keys())
                placeholders = ", ".join(["?"] * len(db_document))
                conn.execute(
                    f"INSERT INTO {DOCUMENTS_TABLE} ({columns}) VALUES ({placeholders})",
                    list(db_document.values()),
                )

        return True

    def get_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a document by its ID."""
        if not doc_id:
            return None

        with duckdb.connect(self.db_path) as conn:
            df: Union[pl.DataFrame, pl.Series] = pl.from_arrow(
                conn.execute(
                    f"SELECT * FROM {DOCUMENTS_TABLE} WHERE id = ?", [doc_id]
                ).arrow()
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
                import json

                document["metadata"] = json.loads(document["metadata"])
            else:
                document["metadata"] = {}

            return document

    def get_documents(
        self,
        source: Optional[str] = None,
        source_location: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
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

            df: Union[pl.DataFrame, pl.Series] = pl.from_arrow(
                conn.execute(query, params).arrow()
            )

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
        import duckdb
        import webbrowser
        import time

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


def delete_db(db_path: Optional[str] = None) -> bool:
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
