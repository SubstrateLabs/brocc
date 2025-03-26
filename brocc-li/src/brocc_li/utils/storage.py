import duckdb
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Set
from appdirs import user_data_dir
from pathlib import Path
from brocc_li.types.document import Document

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


class DocumentStorage:
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
                    url VARCHAR UNIQUE,
                    title VARCHAR,
                    description VARCHAR,
                    content VARCHAR,
                    author_name VARCHAR,
                    author_identifier VARCHAR,
                    created_at VARCHAR,
                    metadata VARCHAR,  -- JSON string
                    source VARCHAR,
                    source_location VARCHAR,
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

    def get_seen_urls(
        self, source: Optional[str] = None, source_location: Optional[str] = None
    ) -> Set[str]:
        """Get a set of URLs that have already been seen."""
        with duckdb.connect(self.db_path) as conn:
            query = f"SELECT url FROM {DOCUMENTS_TABLE}"
            params = []

            # Add optional filters
            where_clauses = []
            if source:
                where_clauses.append("source = ?")
                params.append(source)
            if source_location:
                where_clauses.append("source_location = ?")
                params.append(source_location)

            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)

            # Use pandas for efficient memory handling
            df = conn.execute(query, params).df()
            return set(df["url"].dropna().tolist())

    def store_document(self, document: Dict[str, Any]) -> bool:
        """Store a document in the database, updating if it already exists."""
        if not document.get("url"):
            return False

        # Validate document structure using Pydantic model
        try:
            # Convert dict to Document model to validate
            doc = Document(**document)
            # Convert back to dict for storage
            document = doc.model_dump()
        except Exception as e:
            raise ValueError(f"Invalid document structure: {str(e)}")

        # Format timestamps consistently
        document["last_updated"] = Document.format_date(datetime.now())
        if not document.get("ingested_at"):
            document["ingested_at"] = Document.format_date(datetime.now())

        # Convert metadata to JSON string (it's always a dict)
        if document.get("metadata"):
            document["metadata"] = json.dumps(document["metadata"])

        # Convert enum values to strings
        for key, value in document.items():
            if hasattr(value, "value"):  # Check if it's an enum
                document[key] = value.value

        with duckdb.connect(self.db_path) as conn:
            # Check if the document already exists
            if self.url_exists(document["url"]):
                # Update the existing document
                set_clauses = []
                params = []

                for key, value in document.items():
                    if key != "url":  # Don't update the URL
                        set_clauses.append(f"{key} = ?")
                        params.append(value)

                # Add the URL as the last parameter for the WHERE clause
                params.append(document["url"])

                conn.execute(
                    f"UPDATE {DOCUMENTS_TABLE} SET {', '.join(set_clauses)} WHERE url = ?",
                    params,
                )
            else:
                # Insert new document
                columns = ", ".join(document.keys())
                placeholders = ", ".join(["?"] * len(document))
                conn.execute(
                    f"INSERT INTO {DOCUMENTS_TABLE} ({columns}) VALUES ({placeholders})",
                    list(document.values()),
                )

        return True

    def get_document_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Retrieve a document by its URL."""
        if not url:
            return None

        with duckdb.connect(self.db_path) as conn:
            # Use pandas for efficient memory handling
            df = conn.execute(
                f"SELECT * FROM {DOCUMENTS_TABLE} WHERE url = ?", [url]
            ).df()

            if df.empty:
                return None

            # Convert to dict and handle JSON fields
            document = df.iloc[0].to_dict()

            # Parse JSON strings back to dicts
            if document.get("metadata"):
                try:
                    document["metadata"] = json.loads(document["metadata"])
                except json.JSONDecodeError:
                    pass

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
                where_clauses.append("source_location = ?")
                params.append(source_location)

            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)

            # Add limit and offset
            query += f" ORDER BY ingested_at DESC LIMIT {limit} OFFSET {offset}"

            # Use pandas for efficient memory handling
            df = conn.execute(query, params).df()

            # Convert to list of dicts and handle JSON fields
            documents = []
            for _, row in df.iterrows():
                document = row.to_dict()

                # Parse JSON strings back to dicts
                if document.get("metadata"):
                    try:
                        document["metadata"] = json.loads(document["metadata"])
                    except json.JSONDecodeError:
                        pass

                documents.append(document)

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
    storage = DocumentStorage()
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
