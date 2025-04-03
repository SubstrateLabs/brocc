#!/usr/bin/env python3
"""
Script to launch the DuckDB UI for the documents database.
"""

from brocc_li.doc_db import DocDB


def main() -> None:
    """Launch the DuckDB UI for the documents database."""
    storage = DocDB()
    storage.launch_duckdb_ui()


if __name__ == "__main__":
    main()
