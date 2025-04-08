import random
from collections.abc import Generator
from datetime import datetime
from typing import Any

from playwright.sync_api import (
    Error as PlaywrightError,
)
from playwright.sync_api import (
    Page,
    TimeoutError,
)

from brocc_li.scroll_prototype.adjust_timeout_counter import adjust_timeout_counter
from brocc_li.scroll_prototype.extract_markdown import extract_markdown
from brocc_li.scroll_prototype.extract_navigate_content import extract_navigate_content
from brocc_li.scroll_prototype.extract_schema import extract_schema
from brocc_li.scroll_prototype.find_container import find_container
from brocc_li.scroll_prototype.find_element import find_element
from brocc_li.scroll_prototype.is_valid_page import is_valid_page
from brocc_li.scroll_prototype.rate_limit_backoff_s import (
    RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD,
)
from brocc_li.scroll_prototype.restore_scroll import restore_scroll_position
from brocc_li.scroll_prototype.save_extract_log import save_extract_log
from brocc_li.scroll_prototype.scroll_strategies import perform_adaptive_scroll
from brocc_li.scroll_prototype.wait_for_navigation import (
    DEFAULT_JITTER_FACTOR,
    wait_for_navigation,
)
from brocc_li.types.extract_feed_config import ExtractFeedConfig
from brocc_li.types.extract_field import ExtractField
from brocc_li.utils.logger import logger
from brocc_li.utils.random_delay import random_delay, random_delay_with_jitter

TEXT_CONTENT_FIELD = "text_content"
URL_FIELD = "url"
DEFAULT_PROGRESS_LABEL = "items"


# Fallback selector when specific content selectors fail
DEFAULT_BODY_SELECTOR = "body"

# Maximum number of retry attempts when navigation fails for a single item
NAVIGATE_MAX_RETRIES = 2


def extract_and_save_content(
    page: Page,
    item: dict[str, Any],
    config: ExtractFeedConfig,
    consecutive_timeouts: int = 0,
) -> tuple[bool, int]:
    """Extract and save content from the detail page."""
    if not config.navigate_options:
        return False, 0

    # Check if schema defines a navigate_content_selector and use it if available
    schema_selector = getattr(config.feed_schema, "navigate_content_selector", None)
    if schema_selector is not None:  # Only use it if explicitly set (not None)
        config.navigate_options.content_selector = schema_selector

    content, new_consecutive_timeouts = extract_navigate_content(
        page, config.navigate_options, consecutive_timeouts
    )
    if content:
        item[TEXT_CONTENT_FIELD] = content

        # Save debug info for navigate
        if config.debug:
            save_extract_log(
                page,
                config,
                "navigate",
                {
                    "html": page.content(),
                    "content_selector": config.navigate_options.content_selector,
                },
            )

        # Even on success, maintain some of the timeout count if it's high
        return True, adjust_timeout_counter(
            consecutive_timeouts,
            success=True,
            aggressive=(consecutive_timeouts > RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD),
        )

    # Track consecutive timeouts
    if new_consecutive_timeouts > 0:
        # Return early if we're experiencing rate limiting
        if new_consecutive_timeouts >= RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD:
            item[TEXT_CONTENT_FIELD] = "Rate limited - content extraction unsuccessful"
            return False, new_consecutive_timeouts

    # Fallback to body content
    content = extract_markdown(page, DEFAULT_BODY_SELECTOR)
    if content:
        item[TEXT_CONTENT_FIELD] = content
        return True, adjust_timeout_counter(consecutive_timeouts, success=True)

    item[TEXT_CONTENT_FIELD] = "No content found"
    # Maintain the timeout count even on failure
    return True, consecutive_timeouts


def handle_navigation(
    page: Page,
    item: dict[str, Any],
    config: ExtractFeedConfig,
    item_position: int,
    original_url: str,
    current_consecutive_timeouts: int = 0,
    scroll_position: int = 0,
) -> int:
    """Handle deep scraping for a single item.

    Args:
        page: The current page
        item: The item being processed
        config: Feed configuration
        item_position: Position of the item in the feed
        original_url: Original URL to return to
        current_consecutive_timeouts: Current count of consecutive timeouts
        scroll_position: Scroll position to restore after navigation

    Returns:
        The number of consecutive timeouts encountered (for rate limiting detection).
    """
    if not config.navigate_options:
        return 0

    retry_count = 0
    content_found = False
    consecutive_timeouts = current_consecutive_timeouts  # Start from the current count, don't reset

    # First ensure we're on the correct starting page before attempting to navigate
    if page.url != original_url:
        if not ensure_original_page(page, original_url, config, scroll_position):
            logger.error("Failed to establish starting page for deep scraping, skipping this item")
            item[TEXT_CONTENT_FIELD] = "Error: Navigation failure before scraping"
            return consecutive_timeouts

    while retry_count <= NAVIGATE_MAX_RETRIES and not content_found:
        try:
            # Check if we're on an about:blank page, which indicates navigation issue
            if page.url == "about:blank" or not page.url:
                logger.warning("About:blank detected, attempting to recover...")
                if not ensure_original_page(page, original_url, config, scroll_position):
                    retry_count += 1
                    logger.error("Failed to recover from about:blank, trying next retry")
                    continue

            if retry_count > 0:
                logger.warning(f"Retry attempt {retry_count}/{NAVIGATE_MAX_RETRIES}")
                # Ensure we're back on the original page before retry
                if not ensure_original_page(page, original_url, config, scroll_position):
                    retry_count += 1
                    logger.error("Failed to return to original page for retry, continuing")
                    continue

                random_delay_with_jitter(
                    config.navigate_options.min_delay_ms,
                    config.navigate_options.max_delay_ms,
                    DEFAULT_JITTER_FACTOR,
                )

            # Try to navigate to the item
            navigation_success = navigate_to_item(page, config, item_position)
            if not navigation_success:
                retry_count += 1
                logger.warning("Failed to navigate to item, attempting retry")
                # Ensure we're back at the original page for the next attempt
                ensure_original_page(page, original_url, config, scroll_position)
                continue

            content_found, new_consecutive_timeouts = extract_and_save_content(
                page, item, config, consecutive_timeouts
            )
            consecutive_timeouts = new_consecutive_timeouts

        except Exception as e:
            logger.error(f"Error during deep scraping: {str(e)}")
            retry_count += 1
            if retry_count <= NAVIGATE_MAX_RETRIES:
                # Try to recover by ensuring we're back at the original page
                ensure_original_page(page, original_url, config, scroll_position)
                random_delay_with_jitter(
                    config.navigate_options.min_delay_ms,
                    config.navigate_options.max_delay_ms,
                    DEFAULT_JITTER_FACTOR,
                )
            else:
                item[TEXT_CONTENT_FIELD] = f"Error: {str(e)}"

    # Always attempt to return to the original page before exiting
    if not ensure_original_page(page, original_url, config, scroll_position):
        # If we couldn't get back to the original page, try a more aggressive approach
        try:
            logger.warning("Final attempt to return to original page...")
            page.goto(original_url, wait_until="domcontentloaded")  # Less strict wait condition
            if page.url == original_url:
                # Try to restore scroll position one last time
                if scroll_position > 0:
                    page.evaluate(f"window.scrollTo(0, {scroll_position})")
                    logger.debug(f"Restored scroll position: {scroll_position}px")
            else:
                logger.error(
                    f"Failed to return to original page after all attempts. Currently at: {page.url}"
                )
        except Exception as e:
            logger.error(f"Fatal navigation error: {str(e)}")

    return consecutive_timeouts


def navigate_to_item(page: Page, config: ExtractFeedConfig, item_position: int) -> bool:
    """Navigate to a specific item's detail page.

    Returns:
        bool: True if navigation was successful, False otherwise
    """
    if not config.navigate_options or not config.container_selector:
        return False

    try:
        # Find the container at the specified position
        container = find_container(
            page, config.container_selector, item_position, "container to navigate"
        )

        if not container:
            return False

        # Get the URL field from the schema
        url_field = next(
            (
                field
                for field_name, field in config.feed_schema.__dict__.items()
                if isinstance(field, ExtractField) and field_name == URL_FIELD
            ),
            None,
        )

        if not url_field:
            logger.warning("URL field not found in schema")
            return False

        # Find the clickable element
        clickable = find_element(
            container,
            url_field.selector,
            required=True,
            description=f"clickable element ({URL_FIELD})",
        )

        if not clickable:
            return False

        # Log that we're about to navigate
        try:
            href = clickable.get_attribute("href")
            logger.debug(f"Navigating to: {href}")
        except Exception as e:
            logger.debug(f"Navigating to item (href not available): {e}")

        # Perform the click
        clickable.click()

        # Wait for navigation to complete with proper error handling
        if not wait_for_navigation(page, config):
            logger.warning("Navigation failed or resulted in invalid page")
            return False

        return True

    except Exception as e:
        logger.warning(f"Navigation error: {str(e)}")
        return False


def ensure_original_page(
    page: Page, original_url: str, config: ExtractFeedConfig, scroll_position: int = 0
) -> bool:
    """Ensure we're back at the original page and restore scroll position.

    Args:
        page: The current page
        original_url: URL to navigate back to
        config: Feed configuration
        scroll_position: Scroll position to restore after navigation (in pixels)

    Returns:
        bool: True if successfully returned to original page, False otherwise
    """
    if not config.navigate_options:
        return True

    # If we're already at the original URL, nothing to do
    if page.url == original_url:
        return True

    # Handle invalid page state explicitly
    if not is_valid_page(page):
        logger.warning("Detected invalid page state, navigating directly to original URL")
        try:
            page.goto(
                original_url,
                wait_until="networkidle"
                if config.navigate_options.wait_networkidle
                else "domcontentloaded",
                timeout=config.network_idle_timeout_ms * 2,  # More generous timeout for recovery
            )
            # Verify we're actually back at the original URL
            if page.url == original_url:
                logger.success("Successfully returned to original page")
                # Restore scroll position with verification
                if scroll_position > 0:
                    restore_scroll_position(page, scroll_position)
                return True
            else:
                logger.error(f"Failed to return to original page. Currently at: {page.url}")
                return False
        except (TimeoutError, PlaywrightError) as e:
            logger.error(f"Failed navigation to original URL: {str(e)}")
            return False

    # Try using browser history first
    try:
        logger.debug("Attempting to use browser history to return to original page...")
        page.go_back()
        random_delay(0.5, 0.1)  # Brief delay to let the navigation complete

        # If back button worked, we're done
        if page.url == original_url:
            # Restore scroll position with verification
            if scroll_position > 0:
                restore_scroll_position(page, scroll_position)
            return True

        # Otherwise try direct navigation
        logger.warning("Browser history navigation failed, trying direct navigation...")
        page.goto(
            original_url,
            wait_until="networkidle"
            if config.navigate_options.wait_networkidle
            else "domcontentloaded",
            timeout=config.network_idle_timeout_ms * 2,  # More generous timeout for recovery
        )

        # Verify we're actually back at the original URL
        if page.url == original_url:
            logger.success("Successfully returned to original page")
            # Restore scroll position with verification
            if scroll_position > 0:
                restore_scroll_position(page, scroll_position)
            return True
        else:
            logger.error(f"Failed to return to original page. Currently at: {page.url}")
            return False

    except (TimeoutError, PlaywrightError) as e:
        logger.error(f"Failed all navigation attempts: {str(e)}")
        return False


def scroll_and_extract(
    page: Page, config: ExtractFeedConfig
) -> Generator[dict[str, Any], None, None]:
    """Generator function to scroll through a page and yield items as they're found.

    Return type explanation:
    - Generator[Dict[str, Any], None, None] means:
      - Yields: Dict[str, Any] (each item is a dictionary with string keys and any values)
      - Receives: None (generator doesn't accept any values via .send())
      - Returns: None (generator doesn't return a final value)
    """
    try:
        if config.container_selector is None:
            for _field_name, field in config.feed_schema.__dict__.items():
                if isinstance(field, ExtractField) and field.is_container:
                    config.container_selector = field.selector
                    break
            if config.container_selector is None:
                raise ValueError("No container selector found in schema")

        page.wait_for_selector(config.container_selector, timeout=config.initial_load_timeout_ms)
    except Exception as e:
        logger.error(f"Timeout waiting for {DEFAULT_PROGRESS_LABEL} to load: {str(e)}")
        return

    # Initialize storage if configured
    storage = None
    if config.use_storage:
        # Import here to avoid circular imports
        from brocc_li.doc_db import DocDB

        storage = DocDB(config.storage_path)
        logger.debug(f"Using document storage: {storage.db_path}")

    # Get seen URLs if using storage
    seen_urls: set[str] = set()
    if storage:
        # Always load the seen URLs that have been seen for this source (across all locations)
        seen_urls = storage.get_seen_urls(source=config.source)
        logger.debug(f"Found {len(seen_urls)} previously seen URLs for {config.source}")

    items_yielded = 0
    no_new_items_count = 0
    consecutive_same_height = 0
    consecutive_all_seen = 0  # Track consecutive scrolls where all items were seen
    original_url = page.url
    total_skipped = 0
    consecutive_timeouts = 0  # Track consecutive timeouts for rate limiting detection
    last_scroll_position = 0  # Track last scroll position to restore after navigation
    date_cutoff_reached = False  # Track if we've reached the date cutoff
    is_turbo_mode = False  # Track if we're in turbo mode

    while (
        (config.max_items is None or items_yielded < config.max_items)
        and no_new_items_count < config.scroll_config.max_no_new_items
        and not date_cutoff_reached
    ):
        # If we've experienced significant rate limiting, abort the extraction
        if consecutive_timeouts >= RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD * 2:
            logger.error(
                f"Aborting extraction due to persistent rate limiting ({consecutive_timeouts} timeouts)"
            )
            return

        # Log the current consecutive timeouts count if it's non-zero
        if consecutive_timeouts > 0:
            logger.warning(f"Current consecutive timeouts: {consecutive_timeouts}")

        # Skip expandable elements in turbo mode to speed things up
        if not is_turbo_mode and config.expand_item_selector:
            for element in page.query_selector_all(config.expand_item_selector):
                try:
                    if element.is_visible():
                        element.click()
                        page.wait_for_timeout(config.click_wait_timeout_ms)
                except Exception as e:
                    logger.error(f"Failed to expand element: {str(e)}")

        # Normal extraction mode
        current_items = extract_schema(page, config.feed_schema, config.container_selector, config)
        new_items = 0
        skipped_items = 0

        # Save current scroll position before processing any items
        last_scroll_position = page.evaluate("window.scrollY")

        # Skip deep scraping in turbo mode to improve performance
        should_do_deep_scraping = not is_turbo_mode

        for idx, item in enumerate(current_items):
            if config.max_items is not None and items_yielded >= config.max_items:
                break

            # Check if this item's date is past our cutoff
            if config.stop_after_date and "created_at" in item and item["created_at"]:
                try:
                    item_date = item["created_at"]
                    # Handle both string dates and datetime objects
                    if isinstance(item_date, str):
                        # Try parsing from ISO format first
                        try:
                            item_date = datetime.fromisoformat(item_date.replace("Z", "+00:00"))
                        except ValueError:
                            # Fall back to more flexible parsing if needed
                            from dateutil.parser import parse

                            item_date = parse(item_date)

                    if item_date < config.stop_after_date:
                        logger.warning(
                            f"Reached date cutoff: item from {item_date} is older than {config.stop_after_date}"
                        )
                        date_cutoff_reached = True
                        break
                except Exception as e:
                    logger.warning(f"Error parsing date: {str(e)}")

            url = item.get(URL_FIELD)
            if not url:
                continue

            # Check if we've seen this URL before
            if url in seen_urls:
                skipped_items += 1
                total_skipped += 1

                # If continue_on_seen is False, we should STOP extraction when we hit a seen URL
                if not config.continue_on_seen:
                    logger.warning(f"Found already seen URL: {url}")
                    logger.warning("Stopping extraction as continue_on_seen is False")
                    return  # Stop the generator immediately

                # Otherwise, skip this item and continue
                continue

            # Found an unseen URL - if we're in turbo mode, exit it to process content properly
            if is_turbo_mode:
                logger.success("Found unseen content, exiting turbo mode to process it properly")
                is_turbo_mode = False

            # Add to seen URLs to avoid duplicates in this session
            seen_urls.add(url)
            item_position = idx  # Use the position in the current items list, not items_yielded

            # Process this unseen item - but skip deep scraping in turbo mode
            if should_do_deep_scraping and config.navigate_options and url:
                new_consecutive_timeouts = handle_navigation(
                    page,
                    item,
                    config,
                    item_position,
                    original_url,
                    consecutive_timeouts,
                    last_scroll_position,
                )
                consecutive_timeouts = new_consecutive_timeouts

            # Store the item if using storage
            if storage:
                # Convert to Document format for storage
                from brocc_li.types.doc import Doc, Source, SourceType

                try:
                    source = Source(config.source)
                except ValueError:
                    source = Source.TWITTER  # Default fallback

                doc = Doc.from_extracted_data(
                    data=item,
                    source=source,
                    source_type=SourceType.DOCUMENT,
                    source_location_identifier=config.source_location_identifier,
                    source_location_name=config.source_location_name,
                )
                # Pass the Doc object directly
                storage.store_document(doc)

            # Yield the item
            yield item
            items_yielded += 1
            new_items += 1

            # If we've found some unseen content, exit turbo mode
            if new_items > 0 and is_turbo_mode:
                logger.success("Found new items, exiting turbo mode")
                is_turbo_mode = False

        if skipped_items > 0:
            logger.debug(f"Skipped {skipped_items} already seen items")

        # Track if all items in this batch were already seen
        all_items_seen = skipped_items > 0 and skipped_items == len(current_items)

        # Update the counter for consecutive all-seen scrolls
        if all_items_seen:
            consecutive_all_seen += 1
            if consecutive_all_seen > 3 and not is_turbo_mode:
                logger.warning("Multiple scrolls with only seen items, using fast-scroll mode...")
        else:
            consecutive_all_seen = 0
            # If we find new items, exit turbo mode
            if new_items > 0 and is_turbo_mode:
                logger.success("Found new items, exiting turbo mode")
                is_turbo_mode = False

        # If we're continuing on seen items but still finding new ones,
        # reset the no_new_items counter to keep scrolling
        if new_items > 0:
            no_new_items_count = 0
        else:
            no_new_items_count += 1
            # If we're continuing on seen and have skipped some items, be more persistent
            if (
                config.continue_on_seen
                and total_skipped > 0
                and no_new_items_count < config.scroll_config.max_no_new_items
            ):
                logger.debug(
                    "No new items this scroll, but continuing to look for unseen content..."
                )

        # NEW: Track container count to detect when we've truly reached the end of the feed
        previous_container_count = len(current_items)

        # Perform adaptive scrolling based on context
        consecutive_same_height, last_height, consecutive_all_seen, is_turbo_mode = (
            perform_adaptive_scroll(
                page,
                new_items,
                consecutive_same_height,
                config,
                all_items_seen,
                consecutive_all_seen,
                is_turbo_mode,
            )
        )

        # Check if we've reached the true end of the feed by seeing if more containers appear
        # If we're in "continue_on_seen" mode, we track total containers, not just new items
        if config.continue_on_seen and total_skipped > 0 and not is_turbo_mode:
            # After scrolling, check if we're getting new containers
            new_containers = page.query_selector_all(config.container_selector)

            # If the container count hasn't changed after multiple scrolls, we've likely reached the end
            if (
                len(new_containers) == previous_container_count
                and consecutive_same_height >= config.scroll_config.max_consecutive_same_height - 1
                and no_new_items_count >= config.scroll_config.max_no_new_items - 1
            ):
                logger.warning(
                    f"Reached end of feed: No new containers after {no_new_items_count} scrolls"
                )
                break  # Exit loop - we've truly reached the end

            # If we're getting more containers but they're all seen, be persistent and keep scrolling
            if len(new_containers) > previous_container_count:
                logger.debug(
                    f"Found more containers ({len(new_containers)} vs {previous_container_count}), continuing to scroll..."
                )
                # Be more lenient with no_new_items_count when we're finding more containers
                if no_new_items_count > 0 and skipped_items > 0:
                    no_new_items_count = max(0, no_new_items_count - 1)  # Reduce the counter

        if (
            items_yielded % random.randint(*config.scroll_config.random_pause_interval) == 0
            and not is_turbo_mode  # Skip random pauses in turbo mode
        ):
            random_delay(2.0, 0.5)

        # If we've reached the date cutoff, exit the loop
        if date_cutoff_reached:
            logger.warning(
                f"Stopping extraction as items older than {config.stop_after_date} have been reached"
            )
            break
