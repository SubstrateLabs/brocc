from playwright.sync_api import sync_playwright
from typing import ClassVar, Optional
import time
import re
from datetime import datetime, timedelta
from brocc_li.types.doc import DocExtractor, Doc, Source, SourceType
from brocc_li.chrome_manager import ChromeManager
from brocc_li.extract.extract_field import ExtractField
from brocc_li.extract_feed import scroll_and_extract
from brocc_li.types.extract_feed_config import (
    NavigateOptions,
    ExtractFeedConfig,
    ScrollConfig,
)
from brocc_li.utils.display_result import display_items, ProgressTracker
from brocc_li.utils.timestamp import parse_timestamp
from brocc_li.doc_db import DocDB
from brocc_li.utils.logger import logger

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
    contact_identifier: ClassVar[ExtractField] = ExtractField(
        selector="", transform=lambda x: ""
    )
    # Use a simple placeholder for content that will be replaced during navigate
    text_content: ClassVar[ExtractField] = ExtractField(
        selector="", transform=lambda x: ""
    )
    metadata: ClassVar[ExtractField] = ExtractField(
        selector=".reader2-post-container",
        extract=lambda element, field: {
            "publication": element.query_selector(".pub-name a").inner_text().strip()
            if element.query_selector(".pub-name a")
            else None,
        },
    )

    # Selector to use for markdown content of navigated pages
    navigate_content_selector: ClassVar[Optional[str]] = "article"


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


def parse_author(meta_text: str) -> Optional[str]:
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
        text = re.sub(
            r"\bPAID\b|\bSUBSCRIBE[RD]*\b", "", meta_text, flags=re.IGNORECASE
        )
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


def parse_date_string(date_str: str) -> Optional[datetime]:
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


def main() -> None:
    with sync_playwright() as p:
        # Use ChromeManager
        chrome_manager = ChromeManager()
        browser = chrome_manager.connect(
            p
        )  # Connect (will handle launch/relaunch/connect logic)

        if not browser:
            logger.error("Could not establish connection with Chrome.")
            return

        source_url = URL
        # Use the manager's open_new_tab method
        page = chrome_manager.open_new_tab(browser, source_url)
        if not page:
            # No need to close browser here
            return

        start_time = time.time()

        # Initialize storage
        storage = None
        if USE_STORAGE:
            storage = DocDB()
            logger.debug(f"Using document storage at: {storage.db_path}")

        if MAX_ITEMS:
            logger.debug(f"Maximum items: {MAX_ITEMS}")

        # Log date cutoff if active
        if STOP_AFTER_DATE:
            logger.success(
                f"Will stop extraction after reaching items older than: {STOP_AFTER_DATE}"
            )

        # Initialize progress tracker
        progress = ProgressTracker(label="posts", target=MAX_ITEMS)

        # Process items as they're streamed back
        docs = []
        formatted_posts = []
        extraction_generator = scroll_and_extract(page=page, config=SUBSTACK_CONFIG)

        for item in extraction_generator:
            # Convert to Document object
            doc = Doc.from_extracted_data(
                data=item,
                source=Source.SUBSTACK,
                source_type=SourceType.DOCUMENT,
                source_location_identifier=source_url,
                source_location_name=NAME,
            )
            docs.append(doc)

            # Format for display as we get each post
            # Truncate content for display
            content = doc.text_content
            if content and isinstance(content, str):
                content_text = content.replace("\n", " ").strip()
                content = (
                    (content_text[:100] + "...")
                    if len(content_text) > 100
                    else content_text
                )

            formatted_posts.append(
                {
                    "Title": doc.title or "No title",
                    "Description": doc.description or "",
                    "Date": doc.created_at or "No date",
                    "Contact": doc.contact_name or "Unknown",
                    "URL": doc.url,
                    "Content Preview": content or "No content",
                    "Publication": doc.metadata.get("publication", "")
                    if doc.metadata
                    else "",
                }
            )

            # Update progress tracker with current count
            progress.update(
                item_info=f"Post: {doc.title or 'Untitled'} by {doc.contact_name or 'Unknown'}"
            )

        # Final update to progress tracker with force display
        if docs:
            progress.update(force_display=True)

            display_items(
                items=formatted_posts,
                title="Substack Posts",
                columns=[
                    "Title",
                    "Description",
                    "Date",
                    "Author",
                    "URL",
                    "Content Preview",
                    "Publication",
                ],
            )

            elapsed_time = time.time() - start_time
            posts_per_minute = (len(docs) / elapsed_time) * 60
            logger.success(f"Successfully extracted {len(docs)} unique posts")
            logger.info(f"Collection rate: {posts_per_minute:.1f} posts/minute")
            logger.debug(f"Time taken: {elapsed_time:.1f} seconds")
            if storage:
                logger.debug(f"Documents stored in database: {storage.db_path}")
        else:
            logger.warning("No posts found")

        # No need to close browser here
        # if browser and browser.is_connected():
        #     browser.close() # Don't close the externally managed browser

        # Close the specific page when done
        if page and not page.is_closed():
            page.close()


if __name__ == "__main__":
    main()
