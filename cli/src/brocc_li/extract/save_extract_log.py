import json
import os
from datetime import datetime
from typing import Any

from playwright.sync_api import Page

from brocc_li.types.extract_feed_config import (
    ExtractFeedConfig,
)
from brocc_li.utils.slugify import slugify

DEBUG_FOLDER = "debug"
DEBUG_FILENAME_FORMAT = "brocc_debug_{source}_{location}.jsonl"


def save_extract_log(
    page: Page,
    config: ExtractFeedConfig,
    log_type: str,
    data: dict[str, Any],
) -> None:
    """Save debug information to a JSONL file.

    Args:
        page: The current page
        config: Feed configuration
        log_type: Type of debug data (feed_page, container, navigate, extract_result)
        data: The data to log
    """
    if not config.debug:
        return

    # Create debug file if it doesn't exist
    if not config.debug_file:
        os.makedirs(DEBUG_FOLDER, exist_ok=True)

        # Extract source from page URL
        url = page.url
        source = url.split("//")[-1].split("/")[0]  # Extract domain as source
        source = slugify(source)

        # Extract location (path) from URL
        location = "/".join(url.split("//")[-1].split("/")[1:])
        location = slugify(location)

        # If location is empty, use 'home'
        if not location:
            location = "home"

        config.debug_file = os.path.join(
            DEBUG_FOLDER, DEBUG_FILENAME_FORMAT.format(source=source, location=location)
        )

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "type": log_type,
        "url": page.url,
        "data": data,
    }

    with open(config.debug_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")
