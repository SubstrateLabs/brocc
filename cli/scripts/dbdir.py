#!/usr/bin/env python3
"""
Script to open the database directory in the system's file browser.
"""

import os
import webbrowser

from platformdirs import user_data_dir

from brocc_li.doc_db import APP_AUTHOR, APP_NAME
from brocc_li.utils.logger import logger


def main() -> None:
    """Open the application data directory in the system's file browser."""
    data_dir = user_data_dir(APP_NAME, APP_AUTHOR)
    os.makedirs(data_dir, exist_ok=True)

    # Use webbrowser module for cross-platform support
    try:
        url = f"file://{data_dir}"
        webbrowser.open(url)
        logger.debug(f"Opened data directory: {data_dir}")
    except Exception as e:
        logger.error(f"Failed to open data directory: {e}")
        logger.debug(f"Data directory path: {data_dir}")


if __name__ == "__main__":
    main()
