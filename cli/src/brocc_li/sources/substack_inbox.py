import re
from datetime import datetime, timedelta
from typing import ClassVar

from brocc_li.extract.extract_field import ExtractField
from brocc_li.types.doc import DocExtractor, Source
from brocc_li.types.extract_feed_config import (
    ExtractFeedConfig,
    NavigateOptions,
    ScrollConfig,
)
from brocc_li.utils.logger import logger
from brocc_li.utils.timestamp import parse_timestamp

# Config flags for development (running main)
MAX_ITEMS = None  # Set to None to get all items, or a number to limit
URL = "https://substack.com/inbox"
NAME = "Substack Inbox"
DEBUG = False  # Turn this on, disable storage, set max items lower. Writes debug jsonl to /debug
USE_STORAGE = True  # Enable storage in duckdb
CONTINUE_ON_SEEN = True  # Continue past seen URLs to get a complete feed

# Set to a datetime value to stop extraction after reaching items older than this date
# Examples:
#   None - extract everything (default)
#   datetime.now() - timedelta(days=7) - only get items from the last week
#   datetime.fromisoformat("2023-11-01") - only get items on or after Nov 1, 2023
STOP_AFTER_DATE = datetime.fromisoformat("2023-03-15")  # Change this to filter by date


class SubstackExtractSchema(DocExtractor):
    container: ClassVar[ExtractField] = ExtractField(
        selector=".reader2-post-container", is_container=True
    )
    url: ClassVar[ExtractField] = ExtractField(
        selector="a.reader2-inbox-post",
        attribute="href",
        transform=lambda x: x if x else None,
    )
    created_at: ClassVar[ExtractField] = ExtractField(
        selector=".inbox-item-timestamp",
        transform=lambda x: parse_timestamp(x.strip() if x else ""),
    )
    title: ClassVar[ExtractField] = ExtractField(
        selector=".reader2-post-title", transform=lambda x: x.strip() if x else None
    )
    description: ClassVar[ExtractField] = ExtractField(
        selector=".reader2-paragraph.reader2-secondary",
        extract=lambda element, field: merge_description_publication(element),
    )
    # Map author to author_name for DocumentExtractor compatibility
    contact_name: ClassVar[ExtractField] = ExtractField(
        selector=".reader2-item-meta",
        transform=lambda x: parse_author(x.strip() if x else ""),
    )
    # Add required fields from DocumentExtractor
    contact_identifier: ClassVar[ExtractField] = ExtractField(selector="", transform=lambda x: "")
    # Use a simple placeholder for content that will be replaced during navigate
    text_content: ClassVar[ExtractField] = ExtractField(selector="", transform=lambda x: "")
    metadata: ClassVar[ExtractField] = ExtractField(
        selector=".reader2-post-container",
        extract=lambda element, field: {
            "publication": element.query_selector(".pub-name a").inner_text().strip()
            if element.query_selector(".pub-name a")
            else None,
        },
    )

    # Selector to use for markdown content of navigated pages
    navigate_content_selector: ClassVar[str | None] = "article"


SUBSTACK_CONFIG = ExtractFeedConfig(
    feed_schema=SubstackExtractSchema,
    max_items=MAX_ITEMS,
    navigate_options=NavigateOptions(
        wait_networkidle=True,
        content_timeout_ms=2000,
        min_delay_ms=2000,
        max_delay_ms=4000,
    ),
    source=Source.SUBSTACK.value,
    source_location_identifier=URL,
    source_location_name=NAME,
    use_storage=USE_STORAGE,
    continue_on_seen=CONTINUE_ON_SEEN,
    stop_after_date=STOP_AFTER_DATE,
    debug=DEBUG,
    scroll_config=ScrollConfig(
        max_no_new_items=30,  # More persistent scrolling - higher value to keep going past seen items
        max_consecutive_same_height=4,  # More aggressive handling of same-height detection
        min_delay=0.3,  # Faster minimum delay
        max_delay=1.0,  # Faster maximum delay
        jitter_factor=0.2,  # Less random variation
    ),
    # Reduce timeouts for faster performance
    initial_load_timeout_ms=8000,
    network_idle_timeout_ms=3000,
    click_wait_timeout_ms=300,
)


def merge_description_publication(element):
    """Merge description and publication content."""
    description_text = element.query_selector(".reader2-paragraph.reader2-secondary")
    description = description_text.inner_text().strip() if description_text else ""

    pub_element = element.query_selector(".pub-name a")
    publication = pub_element.inner_text().strip() if pub_element else None

    if publication:
        return f"{description}\nPublication: {publication}"
    return description


def parse_author(meta_text: str) -> str | None:
    """Extract author name from metadata text."""
    if not meta_text:
        return None

    # First, explicitly handle the exact "PAID" text case
    if meta_text.strip() == "PAID":
        return None  # Return None so we can detect and fix these later

    # Clean up text by removing PAID indicator - handle more variants
    meta_text = re.sub(r"\bPAID\b\s*", "", meta_text, flags=re.IGNORECASE).strip()

    # Try to handle publication pattern: "Meta text · PUBLICATION"
    # Check if it's just a publication name with "PUBLICATION" or "NEWSLETTER"
    if re.match(r"^[A-Z\s]+$", meta_text) and any(
        word in meta_text.upper()
        for word in ["REVIEW", "COLLECTIVE", "NEWSLETTER", "PUBLICATION", "CLUB"]
    ):
        return meta_text  # This is likely a publication name acting as author

    # Handle special cases with known multi-author formats
    if "&" in meta_text or " AND " in meta_text.upper() or "," in meta_text:
        # Likely a multi-author post, clean it up but keep all authors
        text = re.sub(r"\bPAID\b|\bSUBSCRIBE[RD]*\b", "", meta_text, flags=re.IGNORECASE)
        text = re.sub(r"\d+\s+MIN\s+(READ|LISTEN|WATCH)", "", text, flags=re.IGNORECASE)
        # Remove any date patterns
        text = re.sub(
            r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d{1,2}(?:,\s+\d{4})?",
            "",
            text,
            flags=re.IGNORECASE,
        )
        cleaned = text.replace("∙", " ").replace("|", " ").strip()
        if cleaned and cleaned.lower() != "paid":
            return cleaned

    # Handle standard AUTHOR∙LENGTH format
    parts = meta_text.split("∙")
    if len(parts) >= 2:
        # Get the first part as potential author name
        # But verify it's not a date or some other non-author text
        first_part = parts[0].strip()

        # Skip if it looks like a date
        if not re.search(
            r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)",
            first_part,
            re.IGNORECASE,
        ):
            # Check for other disqualifying patterns
            if (
                not re.search(r"\d+\s+MIN", first_part, re.IGNORECASE)
                and first_part.lower() != "paid"
            ):
                return first_part

    # Extract from complex formats - remove dates
    text = re.sub(
        r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d{1,2}(?:,\s+\d{4})?",
        "",
        meta_text,
        flags=re.IGNORECASE,
    )
    # Remove reading time indicators
    text = re.sub(r"\d+\s+MIN\s+(READ|LISTEN|WATCH)", "", text, flags=re.IGNORECASE)
    # Remove "PAID" and subscription indicators more aggressively
    text = re.sub(r"\bPAID\b|\bSUBSCRIBE[RD]*\b", "", text, flags=re.IGNORECASE)

    # Clean up separators and whitespace
    cleaned = text.replace("∙", " ").replace("|", " ").strip()

    # Only return non-empty, non-PAID values
    if cleaned and cleaned.lower() != "paid" and len(cleaned) > 1:
        return cleaned

    return None


def parse_date_string(date_str: str) -> datetime | None:
    """Parse date string in various formats.

    Args:
        date_str: Date string (e.g., '2023-11-01', '1d', '1w', '1m')

    Returns:
        Parsed datetime object or None if parsing failed
    """
    if not date_str:
        return None

    # Check for relative dates (1d, 1w, 1m, etc.)
    if re.match(r"^(\d+)([dwmy])$", date_str):
        match = re.match(r"^(\d+)([dwmy])$", date_str)
        if match:
            value = int(match.group(1))
            unit = match.group(2)

            now = datetime.now()
            if unit == "d":
                return now - timedelta(days=value)
            elif unit == "w":
                return now - timedelta(weeks=value)
            elif unit == "m":
                # Approximate months as 30 days
                return now - timedelta(days=value * 30)
            elif unit == "y":
                # Approximate years as 365 days
                return now - timedelta(days=value * 365)

    # Try direct parsing for absolute dates (YYYY-MM-DD)
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        pass

    # Try more flexible parsing
    try:
        from dateutil.parser import parse

        return parse(date_str)
    except Exception as e:
        logger.error(f"Could not parse date {date_str}: {e}")
        return None
