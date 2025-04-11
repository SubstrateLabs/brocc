#!/usr/bin/env python3
"""
Script to clear all brocc database files (DuckDB and LanceDB).
This will completely erase all stored documents and their chunks.
"""

import argparse
import sys

from brocc_li.doc_db import DocDB
from brocc_li.utils.logger import logger


def parse_args():
    parser = argparse.ArgumentParser(
        description="Clear all brocc database files (DuckDB and LanceDB)"
    )
    parser.add_argument(
        "-f", "--force", action="store_true", help="Force deletion without confirmation"
    )
    parser.add_argument("-p", "--path", type=str, help="Custom database path (optional)")
    parser.add_argument("-l", "--lance-path", type=str, help="Custom LanceDB path (optional)")
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.force:
        confirmation = input(
            "\n⚠️  WARNING: This will permanently delete all your stored documents and their chunks!\n"
            "Are you sure you want to continue? [y/N]: "
        )
        if confirmation.lower() not in ["y", "yes"]:
            print("Operation cancelled.")
            return 0

    # Initialize DocDB with optional custom paths
    db = DocDB(
        db_path=args.path if args.path else None,
        lance_path=args.lance_path if args.lance_path else None,
    )

    # Clear databases
    logger.info("Clearing all database files...")
    result = db.clear_databases()

    if result:
        logger.success("🧹 All database files cleared and reinitialized successfully!")
        return 0
    else:
        logger.error("❌ Failed to clear database files")
        return 1


if __name__ == "__main__":
    sys.exit(main())
