import json
import os
import random
import time
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from html_to_markdown import convert_to_markdown
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, TimeoutError
from pydantic import BaseModel
from rich.console import Console

from brocc_li.types.extract_field import ExtractField
from brocc_li.utils.slugify import slugify

console = Console()


class ScrollPattern(Enum):
    NORMAL = "normal"
    FAST = "fast"
    SLOW = "slow"
    BOUNCE = "bounce"


@dataclass
class ScrollConfig:
    # Minimum delay in seconds between scrolls
    min_delay: float = 0.5
    # Maximum delay in seconds between scrolls
    max_delay: float = 2.0
    # Random variation factor applied to delays (0.3 = ±30% variation)
    jitter_factor: float = 0.3
    # How many scrolls without finding new items before stopping extraction
    max_no_new_items: int = 3
    # How many scrolls with same page height before trying aggressive scroll strategies
    max_consecutive_same_height: int = 3
    # Add a longer random pause after this many items (min, max range)
    random_pause_interval: tuple[int, int] = (15, 25)


# Constants for deep scraping
MARKDOWN_FIELD_NAME = "text_content"
MARKDOWN_FOLDER = "debug"
URL_FIELD = "url"
PROGRESS_LABEL = "items"

# Timeout constants (in milliseconds)
# Maximum time to wait for initial feed containers to load before aborting
INITIAL_LOAD_TIMEOUT_MS = 10000
# Maximum time to wait for the article content selector to be found on a detail page
CONTENT_EXTRACTION_TIMEOUT_MS = 3000
# Brief delay after clicking expandable elements, allows UI to respond
CLICK_WAIT_TIMEOUT_MS = 500
# Time to wait for all network activity to finish when navigating between pages
NETWORK_IDLE_TIMEOUT_MS = 5000

# Delay constants (in milliseconds)
# Default minimum delay between scraping actions for human-like behavior
DEFAULT_MIN_DELAY_MS = 1000
# Default maximum delay between scraping actions for human-like behavior
DEFAULT_MAX_DELAY_MS = 3000
# Factor to add random variation to delays (0.3 = ±30% variation)
DEFAULT_JITTER_FACTOR = 0.3

# Content extraction constants
# Minimum character length to consider extracted content valid
MIN_CONTENT_LENGTH = 100
# Default CSS selector to locate article content on detail pages
DEFAULT_CONTENT_SELECTOR = "article"
# Fallback selector when specific content selectors fail
DEFAULT_BODY_SELECTOR = "body"

# Maximum number of retry attempts when navigation fails for a single item
NAVIGATE_MAX_RETRIES = 2
# Minimum delay between retry attempts when navigation fails
NAVIGATE_RETRY_DELAY_MIN_MS = 1000
# Maximum delay between retry attempts when navigation fails
NAVIGATE_RETRY_DELAY_MAX_MS = 2000

# Rate limiting constants
# Number of consecutive timeouts needed to trigger rate limit detection
RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD = 2
# Initial cooldown period (in ms) when rate limiting is detected
RATE_LIMIT_INITIAL_COOLDOWN_MS = 5000
# Maximum cooldown period (in ms) regardless of consecutive timeouts
RATE_LIMIT_MAX_COOLDOWN_MS = 30000
# Exponential factor for increasing cooldown time with each additional timeout
# Formula: cooldown = min(MAX_COOLDOWN, INITIAL_COOLDOWN * BACKOFF_FACTOR^(timeouts - threshold))
RATE_LIMIT_BACKOFF_FACTOR = 2

# Scroll constants
# Multiplier ranges for viewport height when scrolling in different patterns
# (min_multiplier, max_multiplier) - random value in this range * viewport height = scroll amount
SCROLL_PATTERN_CONFIGS = {
    ScrollPattern.NORMAL: (0.8, 1.2),  # Regular scrolling, ~1 viewport
    ScrollPattern.FAST: (1.5, 2.5),  # Fast scrolling, 1.5-2.5 viewports at once
    ScrollPattern.SLOW: (0.5, 0.8),  # Slow scrolling, less than 1 viewport
    ScrollPattern.BOUNCE: (1.2, 1.5),  # Bounce scrolling, slightly more than 1 viewport
}
# For bounce pattern: min ratio of up-scroll compared to down-scroll
BOUNCE_SCROLL_UP_RATIO_MIN = 0.3
# For bounce pattern: max ratio of up-scroll compared to down-scroll
BOUNCE_SCROLL_UP_RATIO_MAX = 0.5
# For bounce pattern: min pause time (seconds) between down and up scroll
BOUNCE_SCROLL_PAUSE_MIN = 0.2
# For bounce pattern: max pause time (seconds) between down and up scroll
BOUNCE_SCROLL_PAUSE_MAX = 0.4

# Constants for debug logging
DEBUG_FOLDER = "debug"
DEBUG_FILENAME_FORMAT = "brocc_debug_{source}_{location}.jsonl"


class ExtractFeedConfig(BaseModel):
    # Schema definition
    feed_schema: type[BaseModel]

    # Navigate to each item
    navigate_options: Optional["NavigateOptions"] = None

    # Runtime behavior
    max_items: int | None = None
    expand_item_selector: str | None = None
    container_selector: str | None = None

    # Source information (required)
    source: str
    source_location: str

    # Scroll behavior
    scroll_pattern: ScrollPattern = ScrollPattern.NORMAL
    scroll_config: ScrollConfig = ScrollConfig()

    # Timeouts (in milliseconds)
    initial_load_timeout_ms: int = INITIAL_LOAD_TIMEOUT_MS
    network_idle_timeout_ms: int = NETWORK_IDLE_TIMEOUT_MS
    click_wait_timeout_ms: int = CLICK_WAIT_TIMEOUT_MS

    # Storage options
    use_storage: bool = False
    storage_path: str | None = None
    continue_on_seen: bool = False

    # Date cutoff options
    stop_after_date: datetime | None = None

    # Debug options
    debug: bool = False
    debug_file: str | None = None


class NavigateOptions(BaseModel):
    """Configuration options for deep scraping content.

    Provides a simple way to customize the behavior of deep scraping
    when navigating to individual content pages.
    """

    # CSS selector to find the content element on the detail page
    content_selector: str = DEFAULT_CONTENT_SELECTOR

    # Whether to wait for network idle when navigating to pages
    wait_networkidle: bool = True

    # Maximum time in milliseconds to wait for content selector to appear
    content_timeout_ms: int = CONTENT_EXTRACTION_TIMEOUT_MS

    # Minimum delay in milliseconds between scraping actions
    min_delay_ms: int = DEFAULT_MIN_DELAY_MS

    # Maximum delay in milliseconds between scraping actions
    max_delay_ms: int = DEFAULT_MAX_DELAY_MS


def extract_field(element: Any, field: ExtractField, parent_key: str = "") -> Any:
    """Extract data from an element based on a schema field."""
    if field.extract:
        return field.extract(element, field)

    if field.children:
        container = element.query_selector(field.selector) if field.selector else element
        if not container:
            console.print(
                f"[dim]No container found for {parent_key} with selector {field.selector}[/dim]"
            )
            return {}
        return {
            key: extract_field(container, child, f"{parent_key}.{key}")
            for key, child in field.children.items()
        }

    if field.multiple:
        elements = element.query_selector_all(field.selector)
        results = []
        for el in elements:
            value = el.get_attribute(field.attribute) if field.attribute else el.inner_text()
            if field.transform:
                value = field.transform(value)
            if value is not None:
                results.append(value)
        return results

    element = element.query_selector(field.selector) if field.selector else element
    if not element:
        console.print(
            f"[dim]No element found for {parent_key} with selector {field.selector}[/dim]"
        )
        return None

    value = element.get_attribute(field.attribute) if field.attribute else element.inner_text()
    return field.transform(value) if field.transform else value


def scrape_schema(
    page: Page,
    schema: type[BaseModel],
    container_selector: str,
    config: ExtractFeedConfig | None = None,
) -> list[dict[str, Any]]:
    """Scrape data using a schema definition."""
    try:
        # Find container selector from schema if not provided
        if not container_selector:
            for _field_name, field in schema.__dict__.items():
                if isinstance(field, ExtractField) and field.is_container:
                    container_selector = field.selector
                    break
            if not container_selector:
                raise ValueError("No container selector found in schema")

        containers = page.query_selector_all(container_selector)
        console.print(f"[dim]Found {len(containers)} containers[/dim]")

        # Save feed page HTML if debug is enabled
        if config and config.debug:
            save_debug_log(
                page,
                config,
                "feed_page",
                {"html": page.content()},
            )

        items = []
        for i, container in enumerate(containers):
            try:
                if not container.is_visible():
                    console.print(f"[dim]Container {i} is not visible, skipping[/dim]")
                    continue

                # Save container HTML if debug is enabled
                if config and config.debug:
                    save_debug_log(
                        page,
                        config,
                        "container",
                        {"html": container.inner_html(), "position": i},
                    )

                data = {}
                for field_name, field in schema.__dict__.items():
                    if field_name != "container" and isinstance(field, ExtractField):
                        try:
                            data[field_name] = extract_field(container, field, field_name)
                        except Exception as e:
                            console.print(
                                f"[red]Failed to extract field {field_name}: {str(e)}[/red]"
                            )
                            data[field_name] = None

                # Save extract results if debug is enabled
                if config and config.debug:
                    save_debug_log(
                        page,
                        config,
                        "extract_result",
                        {"position": i, "fields": data},
                    )

                items.append(data)
            except Exception as e:
                console.print(f"[red]Failed to process container {i}: {str(e)}[/red]")
                continue

        return items
    except Exception as e:
        console.print(f"[red]Failed to scrape data: {str(e)}[/red]")
        return []


def random_delay(base_delay: float, variation: float = 0.2) -> None:
    """Add random variation to delays."""
    time.sleep(base_delay * random.uniform(1 - variation, 1 + variation))


def human_scroll(page: Page, pattern: ScrollPattern, seen_only_multiplier: float = 1.0) -> None:
    """Simulate human-like scrolling behavior.

    Args:
        page: The current page
        pattern: The scrolling pattern to use
        seen_only_multiplier: Multiplier to increase scroll distance when only seen items are found
    """
    viewport_height = page.evaluate("window.innerHeight")

    if pattern == ScrollPattern.BOUNCE:
        down_amount = int(
            viewport_height
            * random.uniform(*SCROLL_PATTERN_CONFIGS[pattern])
            * seen_only_multiplier
        )
        up_amount = int(
            down_amount * random.uniform(BOUNCE_SCROLL_UP_RATIO_MIN, BOUNCE_SCROLL_UP_RATIO_MAX)
        )
        page.evaluate(f"window.scrollBy(0, {down_amount})")
        time.sleep(random.uniform(BOUNCE_SCROLL_PAUSE_MIN, BOUNCE_SCROLL_PAUSE_MAX))
        page.evaluate(f"window.scrollBy(0, -{up_amount})")
    else:
        scroll_amount = int(
            viewport_height
            * random.uniform(*SCROLL_PATTERN_CONFIGS[pattern])
            * seen_only_multiplier
        )
        page.evaluate(f"window.scrollBy(0, {scroll_amount})")

        # When using a large multiplier for aggressive scrolling, log it
        if seen_only_multiplier > 1.5:
            console.print(
                f"[dim]Fast-scrolling with {seen_only_multiplier:.1f}x multiplier ({scroll_amount} pixels)[/dim]"
            )


def random_delay_with_jitter(min_ms: int, max_ms: int, jitter_factor: float = 0.3) -> None:
    """Add a random delay with jitter to make scraping more human-like."""
    min_delay = min_ms / 1000
    max_delay = max_ms / 1000
    base_delay = random.uniform(min_delay, max_delay)
    jitter = base_delay * jitter_factor * random.choice([-1, 1])
    final_delay = min(max_delay, max(0.1, base_delay + jitter))
    console.print(f"[dim]Waiting for {final_delay:.2f} seconds...[/dim]")
    time.sleep(final_delay)


def extract_content_from_page(
    page: Page, options: NavigateOptions, consecutive_timeouts: int = 0
) -> tuple[str | None, int]:
    """Extract content from a page using the provided selector.

    Returns:
        Tuple containing the extracted content (or None) and the number of consecutive timeouts.
    """
    selector = options.content_selector.strip()

    try:
        # If we've hit consecutive timeouts, implement a cooldown
        if consecutive_timeouts >= RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD:
            # Calculate exponential backoff cooldown time
            cooldown_ms = min(
                RATE_LIMIT_MAX_COOLDOWN_MS,
                RATE_LIMIT_INITIAL_COOLDOWN_MS
                * (
                    RATE_LIMIT_BACKOFF_FACTOR
                    ** (consecutive_timeouts - RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD)
                ),
            )
            cooldown_s = cooldown_ms / 1000
            console.print(
                f"[yellow]Rate limit detected! Cooling down for {cooldown_s:.1f} seconds...[/yellow]"
            )
            time.sleep(cooldown_s)

        page.wait_for_selector(selector, timeout=options.content_timeout_ms)
        console.print(f"[green]Found content with selector: '{selector}'[/green]")

        content_elements = page.query_selector_all(selector)
        if not content_elements:
            # Be more cautious when we've had timeouts before
            if consecutive_timeouts > 0:
                return None, max(0, consecutive_timeouts - 1)
            return None, 0  # Only fully reset if we haven't had timeouts

        largest_content = max((el.inner_html() for el in content_elements), key=len, default="")

        if len(largest_content) > MIN_CONTENT_LENGTH:
            console.print(
                f"[green]Selected content from '{selector}' ({len(largest_content)} chars)[/green]"
            )
            # On success, decrease the timeout counter but don't fully reset
            # This ensures we remain cautious if we've had multiple timeouts
            if consecutive_timeouts > 0:
                return largest_content, max(0, consecutive_timeouts - 1)
            return largest_content, 0

    except TimeoutError as e:
        # Increment timeout counter for rate limiting detection
        consecutive_timeouts += 1
        console.print(f"[yellow]Timeout error with selector '{selector}': {str(e)}[/yellow]")

        # Adaptive cooldown - apply a brief cooldown even on first timeout
        # Scale from 0.5s for first timeout up to full exponential backoff
        if consecutive_timeouts >= RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD:
            # Use existing exponential backoff for multiple timeouts
            cooldown_ms = min(
                RATE_LIMIT_MAX_COOLDOWN_MS,
                RATE_LIMIT_INITIAL_COOLDOWN_MS
                * (
                    RATE_LIMIT_BACKOFF_FACTOR
                    ** (consecutive_timeouts - RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD)
                ),
            )
            cooldown_s = cooldown_ms / 1000
            console.print(
                f"[yellow]Multiple timeouts detected! Cooling down for {cooldown_s:.1f} seconds...[/yellow]"
            )
        else:
            # For early timeouts, scale cooldown gradually
            cooldown_s = 0.5 + (consecutive_timeouts - 1) * 0.5
            console.print(
                f"[yellow]Timeout detected, brief cooldown for {cooldown_s:.1f} seconds...[/yellow]"
            )

        time.sleep(cooldown_s)

        if consecutive_timeouts >= RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD:
            console.print(
                f"[yellow]Detected {consecutive_timeouts} consecutive timeouts, possible rate limiting[/yellow]"
            )
        return None, consecutive_timeouts
    except Exception as e:
        console.print(f"[yellow]Error with selector '{selector}': {str(e)}[/yellow]")
        # For non-timeout errors, still be a bit cautious if we've had timeouts before
        if consecutive_timeouts > 0:
            return None, max(0, consecutive_timeouts - 1)
        return None, 0  # Reset timeout counter on non-timeout errors

    # Apply the same conservative logic for the default return
    if consecutive_timeouts > 0:
        return None, max(0, consecutive_timeouts - 1)
    return None, 0  # Reset timeout counter by default


def save_debug_log(
    page: Page,
    config: ExtractFeedConfig,
    log_type: str,
    data: dict[str, Any],
) -> None:
    """Save debug information to a JSONL file.

    Args:
        page: The current page
        config: Feed configuration
        log_type: Type of debug data (feed_page, container, deep_scrape, extract_result)
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


def extract_and_save_content(
    page: Page,
    item: dict[str, Any],
    config: ExtractFeedConfig,
    consecutive_timeouts: int = 0,
) -> tuple[bool, int]:
    """Extract and save content from the detail page."""
    if not config.navigate_options:
        return False, 0

    # Check if schema defines a deep_content_selector and use it if available
    schema_selector = getattr(config.feed_schema, "deep_content_selector", None)
    if schema_selector is not None:  # Only use it if explicitly set (not None)
        config.navigate_options.content_selector = schema_selector

    html_content, new_consecutive_timeouts = extract_content_from_page(
        page, config.navigate_options, consecutive_timeouts
    )
    if html_content:
        content = convert_to_markdown(html_content)
        item[MARKDOWN_FIELD_NAME] = content

        # Save debug info for deep scrape
        if config.debug:
            save_debug_log(
                page,
                config,
                "deep_scrape",
                {
                    "html": page.content(),
                    "content_selector": config.navigate_options.content_selector,
                },
            )

        # Even on success, maintain some of the timeout count if it's high
        if consecutive_timeouts > RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD:
            return True, max(1, consecutive_timeouts - 2)  # Reduce but don't reset completely
        elif consecutive_timeouts > 0:
            return True, max(0, consecutive_timeouts - 1)  # Decrease by 1

        return True, 0  # Only fully reset on success if we haven't had many timeouts

    # Track consecutive timeouts
    if new_consecutive_timeouts > 0:
        # Return early if we're experiencing rate limiting
        if new_consecutive_timeouts >= RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD:
            item[MARKDOWN_FIELD_NAME] = "Rate limited - content extraction unsuccessful"
            return False, new_consecutive_timeouts

    # Fallback to body content
    body_element = page.query_selector(DEFAULT_BODY_SELECTOR)
    if body_element:
        body_html = body_element.inner_html()
        item[MARKDOWN_FIELD_NAME] = convert_to_markdown(body_html)

        # Even with fallback success, be cautious if we've had timeouts
        if consecutive_timeouts > 0:
            return True, max(0, consecutive_timeouts - 1)
        return True, 0

    item[MARKDOWN_FIELD_NAME] = "No content found"
    # Maintain the timeout count even on failure
    return True, consecutive_timeouts


def handle_deep_scraping(
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
            console.print(
                "[red]Failed to establish starting page for deep scraping, skipping this item[/red]"
            )
            item[MARKDOWN_FIELD_NAME] = "Error: Navigation failure before scraping"
            return consecutive_timeouts

    while retry_count <= NAVIGATE_MAX_RETRIES and not content_found:
        try:
            # Check if we're on an about:blank page, which indicates navigation issue
            if page.url == "about:blank" or not page.url:
                console.print("[yellow]About:blank detected, attempting to recover...[/yellow]")
                if not ensure_original_page(page, original_url, config, scroll_position):
                    retry_count += 1
                    console.print(
                        "[red]Failed to recover from about:blank, trying next retry[/red]"
                    )
                    continue

            if retry_count > 0:
                console.print(
                    f"[yellow]Retry attempt {retry_count}/{NAVIGATE_MAX_RETRIES}[/yellow]"
                )
                # Ensure we're back on the original page before retry
                if not ensure_original_page(page, original_url, config, scroll_position):
                    retry_count += 1
                    console.print(
                        "[red]Failed to return to original page for retry, continuing[/red]"
                    )
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
                console.print("[yellow]Failed to navigate to item, attempting retry[/yellow]")
                # Ensure we're back at the original page for the next attempt
                ensure_original_page(page, original_url, config, scroll_position)
                continue

            content_found, new_consecutive_timeouts = extract_and_save_content(
                page, item, config, consecutive_timeouts
            )
            consecutive_timeouts = new_consecutive_timeouts

        except Exception as e:
            console.print(f"[red]Error during deep scraping: {str(e)}[/red]")
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
                item[MARKDOWN_FIELD_NAME] = f"Error: {str(e)}"

    # Always attempt to return to the original page before exiting
    if not ensure_original_page(page, original_url, config, scroll_position):
        # If we couldn't get back to the original page, try a more aggressive approach
        try:
            console.print("[yellow]Final attempt to return to original page...[/yellow]")
            page.goto(original_url, wait_until="domcontentloaded")  # Less strict wait condition
            if page.url == original_url:
                # Try to restore scroll position one last time
                if scroll_position > 0:
                    page.evaluate(f"window.scrollTo(0, {scroll_position})")
                    console.print(f"[dim]Restored scroll position: {scroll_position}px[/dim]")
            else:
                console.print(
                    f"[red]Failed to return to original page after all attempts. Currently at: {page.url}[/red]"
                )
        except Exception as e:
            console.print(f"[red]Fatal navigation error: {str(e)}[/red]")

    return consecutive_timeouts


def navigate_to_item(page: Page, config: ExtractFeedConfig, item_position: int) -> bool:
    """Navigate to a specific item's detail page.

    Returns:
        bool: True if navigation was successful, False otherwise
    """
    if not config.navigate_options or not config.container_selector:
        return False

    try:
        # First check if we can find the containers
        visible_containers = page.query_selector_all(config.container_selector)

        # Log what we found for debugging
        console.print(f"[dim]Found {len(visible_containers)} containers to navigate[/dim]")

        if not visible_containers or item_position >= len(visible_containers):
            console.print(
                f"[yellow]Container at position {item_position} not found (total: {len(visible_containers)})[/yellow]"
            )
            return False

        container = visible_containers[item_position]

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
            console.print("[yellow]URL field not found in schema[/yellow]")
            return False

        # Find the clickable element
        clickable = container.query_selector(url_field.selector)
        if not clickable:
            console.print(
                f"[yellow]Clickable element not found with selector: {url_field.selector}[/yellow]"
            )
            return False

        # Log that we're about to navigate
        try:
            href = clickable.get_attribute("href")
            console.print(f"[dim]Navigating to: {href}[/dim]")
        except Exception as e:
            console.print(f"[dim]Navigating to item (href not available): {e}[/dim]")

        # Perform the click
        clickable.click()

        # Wait for navigation to complete
        if config.navigate_options.wait_networkidle:
            try:
                page.wait_for_load_state("networkidle", timeout=config.network_idle_timeout_ms)
            except TimeoutError:
                # If networkidle times out, check if we at least have domcontentloaded
                page.wait_for_load_state("domcontentloaded", timeout=2000)
        else:
            # At minimum, wait for domcontentloaded to ensure page is usable
            page.wait_for_load_state("domcontentloaded", timeout=5000)

        # Add a brief random delay to ensure page is ready
        random_delay_with_jitter(
            NAVIGATE_RETRY_DELAY_MIN_MS,
            NAVIGATE_RETRY_DELAY_MAX_MS,
            DEFAULT_JITTER_FACTOR,
        )

        # Verify we're not at about:blank (which would indicate navigation failure)
        if page.url == "about:blank" or not page.url:
            console.print("[yellow]Navigation resulted in about:blank page[/yellow]")
            return False

        return True

    except Exception as e:
        console.print(f"[yellow]Navigation error: {str(e)}[/yellow]")
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

    # Handle about:blank case explicitly
    if page.url == "about:blank" or not page.url:
        console.print(
            "[yellow]Detected about:blank page, navigating directly to original URL[/yellow]"
        )
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
                console.print("[green]Successfully returned to original page[/green]")
                # Restore scroll position with verification
                if scroll_position > 0:
                    _restore_scroll_with_verification(page, scroll_position)
                return True
            else:
                console.print(
                    f"[red]Failed to return to original page. Currently at: {page.url}[/red]"
                )
                return False
        except (TimeoutError, PlaywrightError) as e:
            console.print(f"[red]Failed navigation to original URL: {str(e)}[/red]")
            return False

    # Try using browser history first
    try:
        console.print("[dim]Attempting to use browser history to return to original page...[/dim]")
        page.go_back()
        random_delay(0.5, 0.1)  # Brief delay to let the navigation complete

        # If back button worked, we're done
        if page.url == original_url:
            # Restore scroll position with verification
            if scroll_position > 0:
                _restore_scroll_with_verification(page, scroll_position)
            return True

        # Otherwise try direct navigation
        console.print(
            "[yellow]Browser history navigation failed, trying direct navigation...[/yellow]"
        )
        page.goto(
            original_url,
            wait_until="networkidle"
            if config.navigate_options.wait_networkidle
            else "domcontentloaded",
            timeout=config.network_idle_timeout_ms * 2,  # More generous timeout for recovery
        )

        # Verify we're actually back at the original URL
        if page.url == original_url:
            console.print("[green]Successfully returned to original page[/green]")
            # Restore scroll position with verification
            if scroll_position > 0:
                _restore_scroll_with_verification(page, scroll_position)
            return True
        else:
            console.print(f"[red]Failed to return to original page. Currently at: {page.url}[/red]")
            return False

    except (TimeoutError, PlaywrightError) as e:
        console.print(f"[red]Failed all navigation attempts: {str(e)}[/red]")
        return False


def _restore_scroll_with_verification(
    page: Page, target_position: int, max_attempts: int = 3
) -> None:
    """Restore scroll position with verification and fallbacks.

    Args:
        page: The current page
        target_position: Target scroll position in pixels
        max_attempts: Maximum number of attempts to restore scroll position
    """
    # First attempt: standard scrollTo
    page.evaluate(f"window.scrollTo(0, {target_position})")
    console.print(f"[dim]Attempted to restore scroll position: {target_position}px[/dim]")
    time.sleep(0.3)  # Brief delay for scroll to take effect

    # Verify if scroll position was actually restored
    current_position = page.evaluate("window.scrollY")

    if abs(current_position - target_position) < 500:  # Allow small differences
        console.print(f"[green]Verified scroll position restored: {current_position}px[/green]")
        return

    # If scroll position wasn't restored correctly, try alternative approaches
    console.print(
        f"[yellow]Scroll position not restored correctly. Got {current_position}px, expected ~{target_position}px[/yellow]"
    )

    for attempt in range(max_attempts):
        if attempt == 0:
            # Try smooth scrolling
            console.print("[dim]Trying smooth scroll restoration...[/dim]")
            page.evaluate(f"""
                window.scrollTo({{
                    top: {target_position},
                    left: 0,
                    behavior: 'smooth'
                }})
            """)
        elif attempt == 1:
            # Try scrolling in steps
            console.print("[dim]Trying step-by-step scroll restoration...[/dim]")
            step_size = target_position / 4
            for step in range(1, 5):
                page.evaluate(f"window.scrollTo(0, {int(step_size * step)})")
                time.sleep(0.1)
        else:
            # Last resort: scroll to bottom then partially back up
            console.print("[dim]Force-scrolling to bottom of page then adjusting...[/dim]")
            # First scroll all the way to bottom
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.3)

            # If target is not at the very bottom, adjust up slightly
            if target_position < page.evaluate("document.body.scrollHeight"):
                # Scroll back up 20% from the bottom if needed
                page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.8)")

        time.sleep(0.3)  # Wait for scroll to take effect
        current_position = page.evaluate("window.scrollY")

        if abs(current_position - target_position) < 500:  # Allow small differences
            console.print(
                f"[green]Scroll position restored on attempt {attempt + 1}: {current_position}px[/green]"
            )
            return

    console.print(
        "[yellow]Could not precisely restore scroll position after multiple attempts[/yellow]"
    )
    # As a last resort, just make sure we're not at the top of the page
    if current_position < 500:
        console.print("[yellow]Emergency scroll to middle/bottom of page[/yellow]")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.8)")


def handle_scrolling(
    page: Page,
    new_items: int,
    consecutive_same_height: int,
    config: ExtractFeedConfig,
    all_items_seen: bool = False,
    consecutive_all_seen: int = 0,
    is_turbo_mode: bool = False,
) -> tuple[int, int, int, bool]:
    """Handle scrolling logic and return updated metrics.

    Args:
        page: The current page
        new_items: Number of new items found in this iteration
        consecutive_same_height: Number of consecutive scrolls with same page height
        config: Feed configuration
        all_items_seen: Whether all items in the current view were already seen
        consecutive_all_seen: Number of consecutive scrolls where all items were seen
        is_turbo_mode: Whether turbo mode is currently active

    Returns:
        Tuple containing updated consecutive_same_height, last_height, consecutive_all_seen, and is_turbo_mode
    """
    current_height = page.evaluate("document.documentElement.scrollHeight")
    last_height = page.evaluate("document.documentElement.scrollHeight")

    # Turbo mode - after many consecutive scrolls with only seen items and continuously finding more
    # containers, enter a super-fast mode to get to the bottom as quickly as possible
    if is_turbo_mode:
        console.print("[yellow]Continuing turbo mode to reach unseen content faster...[/yellow]")
        # In turbo mode, use more aggressive scrolling - jump directly to the very bottom
        # with a larger scroll to ensure we're going far down the page
        page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight * 2)")

        # Also do a second aggressive scroll after a minimal delay
        time.sleep(0.1)  # Ultra-minimal delay
        page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight * 2)")

        # Use minimal delay and skip additional wait times
        time.sleep(0.2)
        return 0, current_height, consecutive_all_seen, True  # Keep turbo mode active

    # Activate turbo mode after seeing only seen items for several consecutive scrolls
    if all_items_seen and consecutive_all_seen >= 5:
        console.print("[yellow]Entering turbo mode to reach unseen content faster...[/yellow]")
        # Initial turbo mode - multiple aggressive scrolls
        # First scroll to the very bottom
        page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight * 2)")
        time.sleep(0.1)
        # Then do another aggressive scroll to ensure we're going as far as possible
        page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight * 2)")
        # Use minimal delay
        time.sleep(0.2)
        return 0, current_height, consecutive_all_seen, True  # Activate turbo mode

    # Jump directly to bottom after several consecutive all-seen scrolls
    if all_items_seen and consecutive_all_seen >= 3:
        console.print(
            "[yellow]Multiple scrolls with only seen items, jumping to bottom of page...[/yellow]"
        )
        # Scroll to very bottom of page
        page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        time.sleep(0.5)  # Reduced wait time from 1.0 to 0.5

        # Check if we reached actual bottom by seeing if scroll position is near page height
        scroll_pos = page.evaluate("window.scrollY")
        page_height = page.evaluate("document.documentElement.scrollHeight")
        viewport_height = page.evaluate("window.innerHeight")

        if (page_height - (scroll_pos + viewport_height)) < 200:  # We're at the bottom
            # Use shorter wait times when we've been in this mode a while
            wait_time = 1.0 if consecutive_all_seen < 6 else 0.3
            console.print(
                f"[green]Reached bottom of page, waiting {wait_time}s for new content to load...[/green]"
            )
            time.sleep(wait_time)

            # Scroll up slightly and back down to trigger possible lazy loading
            # Only do this occasionally to speed up the loop
            if consecutive_all_seen % 3 == 0:
                page.evaluate(f"window.scrollBy(0, -{viewport_height / 3})")
                time.sleep(0.2)
                page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                time.sleep(0.2)

        return (
            0,
            page_height,
            consecutive_all_seen,
            False,
        )  # Reset consecutive_same_height

    # Calculate scroll multiplier based on how many consecutive scrolls had all seen items
    scroll_multiplier = 1.0
    if all_items_seen:
        # Exponentially increase scroll distance when we keep seeing only seen items
        # Start with 1.5x, then 2.0x, 2.5x, 3.0x, etc. up to 5x
        scroll_multiplier = min(5.0, 1.5 + (consecutive_all_seen * 0.5))

    if current_height == last_height:
        consecutive_same_height += 1
        if consecutive_same_height >= config.scroll_config.max_consecutive_same_height:
            if consecutive_same_height % 2 == 0:
                # When stuck at same height for a while, try a dramatic jump to bottom
                console.print("[dim]Stuck at same height, jumping to bottom of page...[/dim]")
                # Instead of scrolling up and down, go directly to bottom
                page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                random_delay(0.5, 0.2)  # Reduced delay from 1.0 to 0.5
            else:
                human_scroll(page, ScrollPattern.FAST, scroll_multiplier)
            consecutive_same_height = 0
        # When all items are seen, prefer faster scrolling patterns
        elif all_items_seen and consecutive_all_seen > 1:
            human_scroll(page, ScrollPattern.FAST, scroll_multiplier)
        else:
            human_scroll(page, random.choice(list(ScrollPattern)), scroll_multiplier)
    else:
        consecutive_same_height = 0
        if all_items_seen and consecutive_all_seen > 2:
            # Page height changed but still all seen - scroll faster toward bottom
            console.print("[dim]Page height changed, continuing fast scroll to bottom...[/dim]")
            human_scroll(page, ScrollPattern.FAST, scroll_multiplier)
        else:
            human_scroll(page, random.choice(list(ScrollPattern)), scroll_multiplier)

    # Adaptive delays - much shorter when we're continually seeing already seen items
    if new_items > 0:
        random_delay(0.3, 0.2)  # Normal delay when finding new items
    elif all_items_seen:
        # Use progressively shorter delays the longer we've been seeing only seen items
        delay_base = max(0.05, 0.2 - (consecutive_all_seen * 0.02))
        time.sleep(delay_base)  # Minimal delay for repeated all-seen cases
    elif consecutive_same_height > 0:
        random_delay(0.5, 0.2)  # Reduced from 1.0 to 0.5
    else:
        random_delay(0.3, 0.2)  # Reduced from 0.5 to 0.3

    # Return updated metrics and turbo mode state (stays False here)
    return consecutive_same_height, last_height, consecutive_all_seen, False


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
        console.print(f"[red]Timeout waiting for {PROGRESS_LABEL} to load: {str(e)}[/red]")
        return

    # Initialize storage if configured
    storage = None
    if config.use_storage:
        # Import here to avoid circular imports
        from brocc_li.doc_db import DocDB

        storage = DocDB(config.storage_path)
        console.print(f"[dim]Using document storage: {storage.db_path}[/dim]")

    # Get seen URLs if using storage
    seen_urls: set[str] = set()
    if storage:
        # Always load the seen URLs that have been seen for this source (across all locations)
        seen_urls = storage.get_seen_urls(source=config.source)
        console.print(f"[dim]Found {len(seen_urls)} previously seen URLs for {config.source}[/dim]")

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
    last_container_count = 0  # Track the last container count for turbo mode optimization

    while (
        (config.max_items is None or items_yielded < config.max_items)
        and no_new_items_count < config.scroll_config.max_no_new_items
        and not date_cutoff_reached
    ):
        # If we've experienced significant rate limiting, abort the extraction
        if consecutive_timeouts >= RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD * 2:
            console.print(
                f"[red]Aborting extraction due to persistent rate limiting ({consecutive_timeouts} timeouts)[/red]"
            )
            return

        # Log the current consecutive timeouts count if it's non-zero
        if consecutive_timeouts > 0:
            console.print(f"[yellow]Current consecutive timeouts: {consecutive_timeouts}[/yellow]")

        # Skip expandable elements in turbo mode to speed things up
        if not is_turbo_mode and config.expand_item_selector:
            for element in page.query_selector_all(config.expand_item_selector):
                try:
                    if element.is_visible():
                        element.click()
                        page.wait_for_timeout(config.click_wait_timeout_ms)
                except Exception as e:
                    console.print(f"[red]Failed to expand element: {str(e)}[/red]")

        # In turbo mode, use a simpler extraction approach - just check how many containers we have
        # but don't process them individually yet - speeds up the loop significantly
        if is_turbo_mode:
            # Just get the container count in turbo mode without full extraction
            current_containers = page.query_selector_all(config.container_selector)
            current_container_count = len(current_containers)

            if current_container_count > last_container_count:
                console.print(
                    f"[dim]Turbo mode: Found {current_container_count} containers (vs {last_container_count} previously)[/dim]"
                )
                last_container_count = current_container_count
                consecutive_same_height = (
                    0  # Reset same height counter when finding more containers
                )

                # Periodically check for unseen content - check every 50 containers or when growth is slow
                should_check_content = (
                    current_container_count % 50 == 0  # Check periodically
                    or (current_container_count - last_container_count) < 10  # Growth slowing down
                )

                if should_check_content:
                    console.print(
                        f"[yellow]Turbo mode: Checking for unseen content at {current_container_count} containers[/yellow]"
                    )
                    # Extract a sample of the latest containers to check for unseen URLs
                    # Take the 10 most recent containers to check
                    sample_containers = (
                        current_containers[-10:]
                        if len(current_containers) > 10
                        else current_containers
                    )

                    # Check if any of these containers have unseen URLs
                    for container in sample_containers:
                        try:
                            # Find URL element using the schema's URL field selector
                            url_field = next(
                                (
                                    field
                                    for field_name, field in config.feed_schema.__dict__.items()
                                    if isinstance(field, ExtractField) and field_name == URL_FIELD
                                ),
                                None,
                            )

                            if url_field and url_field.selector:
                                url_element = container.query_selector(url_field.selector)
                                if url_element:
                                    if url_field.attribute:
                                        url = url_element.get_attribute(url_field.attribute)
                                    else:
                                        url = url_element.inner_text()

                                    # Apply transform if available
                                    if url_field.transform and url:
                                        url = url_field.transform(url)

                                    # Check if this URL is unseen
                                    if url and url not in seen_urls:
                                        console.print(
                                            f"[green]Found unseen URL in turbo mode: {url}[/green]"
                                        )
                                        console.print(
                                            "[green]Exiting turbo mode to process new content[/green]"
                                        )
                                        is_turbo_mode = False

                                        # Instead of just breaking out, let's force a full content extraction now
                                        console.print(
                                            "[yellow]Performing full extraction of current content[/yellow]"
                                        )
                                        # Don't break - instead continue checking other containers to find all unseen content

                        except Exception as e:
                            # Just log and continue if there's an error extracting URL
                            console.print(
                                f"[dim]Error checking container URL in turbo mode: {str(e)}[/dim]"
                            )

                    # If we've exited turbo mode, fully process the current containers
                    if not is_turbo_mode:
                        console.print(
                            f"[yellow]Processing {len(current_containers)} containers for new content[/yellow]"
                        )
                        # Process the current containers immediately to extract the unseen content
                        normal_items = scrape_schema(
                            page, config.feed_schema, config.container_selector, config
                        )
                        console.print(f"[green]Found {len(normal_items)} items to process[/green]")

                        last_container_count = len(normal_items)
                        new_items = 0
                        skipped_items = 0

                        # Process these items
                        for idx, item in enumerate(normal_items):
                            # Check if this item's date is past our cutoff - same check as in main loop
                            if (
                                config.stop_after_date
                                and "created_at" in item
                                and item["created_at"]
                            ):
                                try:
                                    item_date = item["created_at"]
                                    # Handle both string dates and datetime objects
                                    if isinstance(item_date, str):
                                        # Try parsing from ISO format first
                                        try:
                                            item_date = datetime.fromisoformat(
                                                item_date.replace("Z", "+00:00")
                                            )
                                        except ValueError:
                                            # Fall back to more flexible parsing if needed
                                            from dateutil.parser import parse

                                            item_date = parse(item_date)

                                    if item_date < config.stop_after_date:
                                        console.print(
                                            f"[yellow]Reached date cutoff: item from {item_date} is older than {config.stop_after_date}[/yellow]"
                                        )
                                        date_cutoff_reached = True
                                        break
                                except Exception as e:
                                    console.print(f"[yellow]Error parsing date: {str(e)}[/yellow]")

                            url = item.get(URL_FIELD)
                            if not url:
                                continue

                            # Skip already seen URLs
                            if url in seen_urls:
                                skipped_items += 1
                                total_skipped += 1
                                continue

                            # Add to seen URLs to avoid duplicates
                            seen_urls.add(url)
                            item_position = idx

                            # Process this unseen item
                            if config.navigate_options and url:
                                new_consecutive_timeouts = handle_deep_scraping(
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
                                    source_location_identifier=config.source_location,
                                )
                                doc_dict = doc.model_dump()
                                storage.store_document(doc_dict)

                            # Yield the item
                            yield item
                            items_yielded += 1
                            new_items += 1

                        if new_items > 0:
                            console.print(
                                f"[green]Successfully extracted {new_items} new items after exiting turbo mode[/green]"
                            )
                        elif skipped_items > 0:
                            console.print(
                                f"[yellow]All {skipped_items} items were already seen[/yellow]"
                            )
                        else:
                            console.print(
                                "[yellow]No items found in the current containers[/yellow]"
                            )

                        # If we've reached date cutoff, we should exit the entire extraction loop
                        if date_cutoff_reached:
                            console.print(
                                f"[yellow]Stopping extraction as date cutoff {config.stop_after_date} has been reached[/yellow]"
                            )
                            # We'll break out of the main loop on the next iteration when it checks date_cutoff_reached

                        # Continue with the next iteration of the main loop to resume normal extraction
                        continue

                # If we're still in turbo mode, continue scrolling
                if is_turbo_mode:
                    # Use super aggressive scrolling in turbo mode
                    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight * 2)")
                    time.sleep(0.5)

                    # Do a second scroll for even faster movement
                    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight * 2)")
                    time.sleep(1)

                    continue  # Skip the rest of the loop in turbo mode
            else:
                # No new containers found
                consecutive_same_height += 1
                if consecutive_same_height >= 5:
                    # Only exit turbo mode if we've tried multiple times with no progress
                    console.print(
                        f"[yellow]No progress in turbo mode after {consecutive_same_height} attempts, checking for content...[/yellow]"
                    )
                    # Don't exit turbo mode yet, just proceed to content examination
                else:
                    # Try again with even more aggressive scrolling
                    console.print(
                        f"[yellow]No new containers in turbo mode, trying more aggressive scrolling (attempt {consecutive_same_height}/5)[/yellow]"
                    )
                    # Use increasingly aggressive scrolling based on attempt number
                    scroll_multiplier = 2 + consecutive_same_height
                    page.evaluate(
                        f"window.scrollTo(0, document.documentElement.scrollHeight * {scroll_multiplier})"
                    )
                    time.sleep(1)
                    continue

        # Normal extraction mode
        current_items = scrape_schema(page, config.feed_schema, config.container_selector, config)
        last_container_count = len(current_items)  # Update container count
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
                        console.print(
                            f"[yellow]Reached date cutoff: item from {item_date} is older than {config.stop_after_date}[/yellow]"
                        )
                        date_cutoff_reached = True
                        break
                except Exception as e:
                    console.print(f"[yellow]Error parsing date: {str(e)}[/yellow]")

            url = item.get(URL_FIELD)
            if not url:
                continue

            # Check if we've seen this URL before
            if url in seen_urls:
                skipped_items += 1
                total_skipped += 1

                # If continue_on_seen is False, we should STOP extraction when we hit a seen URL
                if not config.continue_on_seen:
                    console.print(f"[yellow]Found already seen URL: {url}[/yellow]")
                    console.print(
                        "[yellow]Stopping extraction as continue_on_seen is False[/yellow]"
                    )
                    return  # Stop the generator immediately

                # Otherwise, skip this item and continue
                continue

            # Found an unseen URL - if we're in turbo mode, exit it to process content properly
            if is_turbo_mode:
                console.print(
                    "[green]Found unseen content, exiting turbo mode to process it properly[/green]"
                )
                is_turbo_mode = False

            # Add to seen URLs to avoid duplicates in this session
            seen_urls.add(url)
            item_position = idx  # Use the position in the current items list, not items_yielded

            # Process this unseen item - but skip deep scraping in turbo mode
            if should_do_deep_scraping and config.navigate_options and url:
                new_consecutive_timeouts = handle_deep_scraping(
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
                    source_location_identifier=config.source_location,
                )
                doc_dict = doc.model_dump()
                storage.store_document(doc_dict)

            # Yield the item
            yield item
            items_yielded += 1
            new_items += 1

            # If we've found some unseen content, exit turbo mode
            if new_items > 0 and is_turbo_mode:
                console.print("[green]Found new items, exiting turbo mode[/green]")
                is_turbo_mode = False

        if skipped_items > 0:
            console.print(f"[dim]Skipped {skipped_items} already seen items[/dim]")

        # Track if all items in this batch were already seen
        all_items_seen = skipped_items > 0 and skipped_items == len(current_items)

        # Update the counter for consecutive all-seen scrolls
        if all_items_seen:
            consecutive_all_seen += 1
            if consecutive_all_seen > 3 and not is_turbo_mode:
                console.print(
                    "[yellow]Multiple scrolls with only seen items, using fast-scroll mode...[/yellow]"
                )
        else:
            consecutive_all_seen = 0
            # If we find new items, exit turbo mode
            if new_items > 0 and is_turbo_mode:
                console.print("[green]Found new items, exiting turbo mode[/green]")
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
                console.print(
                    "[dim]No new items this scroll, but continuing to look for unseen content...[/dim]"
                )

        # NEW: Track container count to detect when we've truly reached the end of the feed
        previous_container_count = len(current_items)

        # Handle scrolling when not in turbo mode
        if not is_turbo_mode:
            (
                consecutive_same_height,
                last_height,
                consecutive_all_seen,
                should_enter_turbo,
            ) = handle_scrolling(
                page,
                new_items,
                consecutive_same_height,
                config,
                all_items_seen,
                consecutive_all_seen,
                is_turbo_mode,
            )

            # Only enter turbo mode if handle_scrolling suggests it and we're continuously seeing only seen items
            if should_enter_turbo and not is_turbo_mode and all_items_seen:
                is_turbo_mode = True
                consecutive_same_height = 0
                console.print(
                    "[yellow]Entering turbo mode to reach unseen content faster...[/yellow]"
                )
        # When in turbo mode, we manage scrolling directly in the turbo mode section

        # NEW: Check if we've reached the true end of the feed by seeing if more containers appear
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
                console.print(
                    f"[yellow]Reached end of feed: No new containers after {no_new_items_count} scrolls[/yellow]"
                )
                break  # Exit loop - we've truly reached the end

            # If we're getting more containers but they're all seen, be persistent and keep scrolling
            if len(new_containers) > previous_container_count:
                console.print(
                    f"[dim]Found more containers ({len(new_containers)} vs {previous_container_count}), continuing to scroll...[/dim]"
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
            console.print(
                f"[yellow]Stopping extraction as items older than {config.stop_after_date} have been reached[/yellow]"
            )
            break
