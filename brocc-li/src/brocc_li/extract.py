from typing import List, Dict, Any, Optional, Callable, Set, Tuple
from pydantic import BaseModel
from rich.console import Console
import random
import time
from html_to_markdown import convert_to_markdown
import os
import urllib.parse
import re
from dataclasses import dataclass
from enum import Enum
from playwright.sync_api import TimeoutError, Error as PlaywrightError, Page

console = Console()


class ScrollPattern(Enum):
    NORMAL = "normal"
    FAST = "fast"
    SLOW = "slow"
    BOUNCE = "bounce"


@dataclass
class ScrollConfig:
    min_delay: float = 0.5
    max_delay: float = 2.0
    jitter_factor: float = 0.3
    max_no_new_items: int = 3
    max_consecutive_same_height: int = 3
    random_pause_interval: Tuple[int, int] = (15, 25)


# Constants for deep scraping
MARKDOWN_FIELD_NAME = "markdown_content"
MARKDOWN_FOLDER = "debug"
URL_FIELD = "url"
PROGRESS_LABEL = "items"

# Timeout constants (in milliseconds)
INITIAL_LOAD_TIMEOUT_MS = 10000
CONTENT_EXTRACTION_TIMEOUT_MS = 3000
CLICK_WAIT_TIMEOUT_MS = 500
NETWORK_IDLE_TIMEOUT_MS = 5000

# Delay constants (in milliseconds)
DEFAULT_MIN_DELAY_MS = 1000
DEFAULT_MAX_DELAY_MS = 3000
DEFAULT_JITTER_FACTOR = 0.3

# Content extraction constants
MIN_CONTENT_LENGTH = 100
DEFAULT_CONTENT_SELECTOR = "article"
DEFAULT_BODY_SELECTOR = "body"

# Deep scraping retry constants
DEEP_SCRAPE_MAX_RETRIES = 2
DEEP_SCRAPE_RETRY_DELAY_MIN_MS = 1000
DEEP_SCRAPE_RETRY_DELAY_MAX_MS = 2000

# Scroll constants
SCROLL_PATTERN_CONFIGS = {
    ScrollPattern.NORMAL: (0.8, 1.2),
    ScrollPattern.FAST: (1.5, 2.5),
    ScrollPattern.SLOW: (0.5, 0.8),
    ScrollPattern.BOUNCE: (1.2, 1.5),
}
BOUNCE_SCROLL_UP_RATIO_MIN = 0.3
BOUNCE_SCROLL_UP_RATIO_MAX = 0.5
BOUNCE_SCROLL_PAUSE_MIN = 0.2
BOUNCE_SCROLL_PAUSE_MAX = 0.4


class DeepScrapeOptions(BaseModel):
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

    # Whether to save markdown content to files
    save_markdown: bool = False


class SchemaField(BaseModel):
    """A field in the schema that defines both data structure and selectors.

    Field extraction follows this order:
    1. If extract() is provided, use it to get the value directly (ignores all other options)
    2. If children is provided, extract nested fields from the element
    3. If multiple is True, get all matching elements and apply steps 4-6 to each
    4. Find element(s) using selector
    5. If attribute is provided, get that attribute's value
    6. Otherwise get element's inner_text()
    7. If transform is provided, apply it to the final value

    Note: The extract() function takes precedence over all other options. When extract() is provided,
    selector, attribute, transform, and children are ignored. This is because extract() provides
    complete control over the extraction process.
    """

    # CSS selector to find the element (e.g. '[data-testid="tweet"]')
    selector: str = ""

    # Attribute to extract from the element (e.g. 'href', 'src', 'datetime')
    attribute: Optional[str] = None

    # Function to transform the extracted value (e.g. strip whitespace, format URL)
    transform: Optional[Callable[[Any], Any]] = None

    # Nested fields to extract from this element
    children: Optional[Dict[str, "SchemaField"]] = None

    # Custom extraction function for complex cases. Takes precedence over all other options.
    # Type: Callable[[Any, SchemaField], Any]
    # - First arg: The element to extract from (Any because it could be a Playwright ElementHandle or other type)
    # - Second arg: The SchemaField instance itself (useful for accessing field metadata)
    # - Returns: Any type of extracted value
    extract: Optional[Callable[[Any, "SchemaField"], Any]] = None

    # Whether to extract multiple elements matching the selector (e.g. list of images)
    multiple: bool = False

    # Whether this field is the container selector for the schema
    is_container: bool = False


def extract_field(element: Any, field: SchemaField, parent_key: str = "") -> Any:
    """Extract data from an element based on a schema field."""
    if field.extract:
        return field.extract(element, field)

    if field.children:
        container = (
            element.query_selector(field.selector) if field.selector else element
        )
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
            value = (
                el.get_attribute(field.attribute)
                if field.attribute
                else el.inner_text()
            )
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

    value = (
        element.get_attribute(field.attribute)
        if field.attribute
        else element.inner_text()
    )
    return field.transform(value) if field.transform else value


def scrape_schema(
    page: Page, schema: type[BaseModel], container_selector: str
) -> List[Dict[str, Any]]:
    """Scrape data using a schema definition."""
    try:
        # Find container selector from schema if not provided
        if not container_selector:
            for field_name, field in schema.__dict__.items():
                if isinstance(field, SchemaField) and field.is_container:
                    container_selector = field.selector
                    break
            if not container_selector:
                raise ValueError("No container selector found in schema")

        containers = page.query_selector_all(container_selector)
        console.print(f"[dim]Found {len(containers)} containers[/dim]")

        items = []
        for i, container in enumerate(containers):
            try:
                if not container.is_visible():
                    console.print(f"[dim]Container {i} is not visible, skipping[/dim]")
                    continue

                data = {}
                for field_name, field in schema.__dict__.items():
                    if field_name != "container" and isinstance(field, SchemaField):
                        try:
                            data[field_name] = extract_field(
                                container, field, field_name
                            )
                        except Exception as e:
                            console.print(
                                f"[red]Failed to extract field {field_name}: {str(e)}[/red]"
                            )
                            data[field_name] = None
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


def human_scroll(page: Page, pattern: ScrollPattern) -> None:
    """Simulate human-like scrolling behavior."""
    viewport_height = page.evaluate("window.innerHeight")

    if pattern == ScrollPattern.BOUNCE:
        down_amount = int(
            viewport_height * random.uniform(*SCROLL_PATTERN_CONFIGS[pattern])
        )
        up_amount = int(
            down_amount
            * random.uniform(BOUNCE_SCROLL_UP_RATIO_MIN, BOUNCE_SCROLL_UP_RATIO_MAX)
        )
        page.evaluate(f"window.scrollBy(0, {down_amount})")
        time.sleep(random.uniform(BOUNCE_SCROLL_PAUSE_MIN, BOUNCE_SCROLL_PAUSE_MAX))
        page.evaluate(f"window.scrollBy(0, -{up_amount})")
    else:
        scroll_amount = int(
            viewport_height * random.uniform(*SCROLL_PATTERN_CONFIGS[pattern])
        )
        page.evaluate(f"window.scrollBy(0, {scroll_amount})")


def random_delay_with_jitter(
    min_ms: int, max_ms: int, jitter_factor: float = 0.3
) -> None:
    """Add a random delay with jitter to make scraping more human-like."""
    min_delay = min_ms / 1000
    max_delay = max_ms / 1000
    base_delay = random.uniform(min_delay, max_delay)
    jitter = base_delay * jitter_factor * random.choice([-1, 1])
    final_delay = min(max_delay, max(0.1, base_delay + jitter))
    console.print(f"[dim]Waiting for {final_delay:.2f} seconds...[/dim]")
    time.sleep(final_delay)


def extract_content_from_page(page: Page, options: DeepScrapeOptions) -> Optional[str]:
    """Extract content from a page using the provided selector."""
    selector = options.content_selector.strip()

    try:
        page.wait_for_selector(selector, timeout=options.content_timeout_ms)
        console.print(f"[green]Found content with selector: '{selector}'[/green]")

        content_elements = page.query_selector_all(selector)
        if not content_elements:
            return None

        largest_content = max(
            (el.inner_html() for el in content_elements), key=len, default=""
        )

        if len(largest_content) > MIN_CONTENT_LENGTH:
            console.print(
                f"[green]Selected content from '{selector}' ({len(largest_content)} chars)[/green]"
            )
            return largest_content

    except Exception as e:
        console.print(f"[yellow]Error with selector '{selector}': {str(e)}[/yellow]")
        return None

    return None


def save_markdown(item: Dict[str, Any]) -> str:
    """Save post content to a markdown file and return the filepath."""
    if not all(
        [
            MARKDOWN_FIELD_NAME in item,
            item.get(MARKDOWN_FIELD_NAME),
            "url" in item,
            item.get("url"),
        ]
    ):
        return ""

    os.makedirs(MARKDOWN_FOLDER, exist_ok=True)
    filename = slugify(item.get("url", ""))
    filepath = os.path.join(MARKDOWN_FOLDER, filename)

    content = item.get(MARKDOWN_FIELD_NAME, "")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath


def slugify(url: str) -> str:
    """Convert a URL to a slugified filename."""
    parsed_url = urllib.parse.urlparse(url)
    path = parsed_url.path.strip("/")
    path = os.path.splitext(path)[0]
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", path).strip("-").lower()

    if not slug:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", parsed_url.netloc).strip("-").lower()

    return f"{slug}.md"


class FeedConfig(BaseModel):
    """Unified configuration for feed extraction.

    This class combines all configuration options needed for feed extraction,
    including schema definition, deep scraping options, and runtime behavior.
    """

    # Schema definition
    feed_schema: type[BaseModel]

    # Deep scraping configuration
    deep_scrape: Optional[DeepScrapeOptions] = None

    # Runtime behavior
    max_items: int = 5
    expand_item_selector: Optional[str] = None
    container_selector: Optional[str] = None

    # Scroll behavior
    scroll_pattern: ScrollPattern = ScrollPattern.NORMAL
    scroll_config: ScrollConfig = ScrollConfig()

    # Timeouts (in milliseconds)
    initial_load_timeout_ms: int = INITIAL_LOAD_TIMEOUT_MS
    network_idle_timeout_ms: int = NETWORK_IDLE_TIMEOUT_MS
    click_wait_timeout_ms: int = CLICK_WAIT_TIMEOUT_MS


def handle_deep_scraping(
    page: Page,
    item: Dict[str, Any],
    config: FeedConfig,
    item_position: int,
    original_url: str,
) -> None:
    """Handle deep scraping for a single item."""
    if not config.deep_scrape:
        return

    retry_count = 0
    content_found = False

    while retry_count <= DEEP_SCRAPE_MAX_RETRIES and not content_found:
        try:
            if retry_count > 0:
                console.print(
                    f"[yellow]Retry attempt {retry_count}/{DEEP_SCRAPE_MAX_RETRIES}[/yellow]"
                )
                page.go_back()
                random_delay_with_jitter(
                    config.deep_scrape.min_delay_ms,
                    config.deep_scrape.max_delay_ms,
                    DEFAULT_JITTER_FACTOR,
                )

            if not navigate_to_item(page, config, item_position):
                retry_count += 1
                continue

            content_found = extract_and_save_content(page, item, config)

        except Exception as e:
            console.print(f"[red]Error during deep scraping: {str(e)}[/red]")
            retry_count += 1
            if retry_count <= DEEP_SCRAPE_MAX_RETRIES:
                page.go_back()
                random_delay_with_jitter(
                    config.deep_scrape.min_delay_ms,
                    config.deep_scrape.max_delay_ms,
                    DEFAULT_JITTER_FACTOR,
                )
            else:
                item[MARKDOWN_FIELD_NAME] = f"Error: {str(e)}"

    ensure_original_page(page, original_url, config)


def navigate_to_item(page: Page, config: FeedConfig, item_position: int) -> bool:
    """Navigate to a specific item's detail page."""
    if not config.deep_scrape or not config.container_selector:
        return False

    visible_containers = page.query_selector_all(config.container_selector)
    if not visible_containers or item_position >= len(visible_containers):
        return False

    container = visible_containers[item_position]
    url_field = next(
        (
            field
            for field_name, field in config.feed_schema.__dict__.items()
            if isinstance(field, SchemaField) and field_name == URL_FIELD
        ),
        None,
    )

    if not url_field:
        return False

    clickable = container.query_selector(url_field.selector)
    if not clickable:
        return False

    clickable.click()
    if config.deep_scrape.wait_networkidle:
        page.wait_for_load_state("networkidle", timeout=config.network_idle_timeout_ms)
    random_delay_with_jitter(
        DEEP_SCRAPE_RETRY_DELAY_MIN_MS,
        DEEP_SCRAPE_RETRY_DELAY_MAX_MS,
        DEFAULT_JITTER_FACTOR,
    )
    return True


def extract_and_save_content(
    page: Page, item: Dict[str, Any], config: FeedConfig
) -> bool:
    """Extract and save content from the detail page."""
    if not config.deep_scrape:
        return False

    html_content = extract_content_from_page(page, config.deep_scrape)
    if html_content:
        markdown_content = convert_to_markdown(html_content)
        item[MARKDOWN_FIELD_NAME] = markdown_content

        if config.deep_scrape.save_markdown:
            filepath = save_markdown(item)
            if filepath:
                console.print(f"[green]Saved markdown to: {filepath}[/green]")
        return True

    # Fallback to body content
    body_element = page.query_selector(DEFAULT_BODY_SELECTOR)
    if body_element:
        body_html = body_element.inner_html()
        item[MARKDOWN_FIELD_NAME] = convert_to_markdown(body_html)
        return True

    item[MARKDOWN_FIELD_NAME] = "No content found"
    return True


def ensure_original_page(page: Page, original_url: str, config: FeedConfig) -> None:
    """Ensure we're back at the original page."""
    if not config.deep_scrape:
        return

    if page.url != original_url:
        try:
            page.go_back()
            if page.url != original_url:
                page.goto(
                    original_url,
                    wait_until="networkidle"
                    if config.deep_scrape.wait_networkidle
                    else None,
                )
        except (TimeoutError, PlaywrightError) as e:
            console.print(f"[red]Failed all navigation attempts: {str(e)}[/red]")


def handle_scrolling(
    page: Page, new_items: int, consecutive_same_height: int, config: FeedConfig
) -> Tuple[int, int]:
    """Handle scrolling logic and return updated metrics."""
    current_height = page.evaluate("document.documentElement.scrollHeight")
    last_height = page.evaluate("document.documentElement.scrollHeight")

    if current_height == last_height:
        consecutive_same_height += 1
        if consecutive_same_height >= config.scroll_config.max_consecutive_same_height:
            if consecutive_same_height % 2 == 0:
                page.evaluate(
                    "window.scrollTo(0, document.documentElement.scrollHeight)"
                )
                random_delay(0.5, 0.3)
                page.evaluate("window.scrollTo(0, 0)")
                random_delay(0.5, 0.3)
            else:
                human_scroll(page, ScrollPattern.FAST)
            consecutive_same_height = 0
        else:
            human_scroll(page, random.choice(list(ScrollPattern)))
    else:
        consecutive_same_height = 0
        human_scroll(page, random.choice(list(ScrollPattern)))

    # Adaptive delays
    if new_items > 0:
        random_delay(0.3, 0.2)
    elif consecutive_same_height > 0:
        random_delay(1.0, 0.3)
    else:
        random_delay(0.5, 0.2)

    return consecutive_same_height, last_height


def scroll_and_extract(page: Page, config: FeedConfig) -> List[Dict[str, Any]]:
    """Main function to scroll through a page and extract items."""
    try:
        if config.container_selector is None:
            for field_name, field in config.feed_schema.__dict__.items():
                if isinstance(field, SchemaField) and field.is_container:
                    config.container_selector = field.selector
                    break
            if config.container_selector is None:
                raise ValueError("No container selector found in schema")

        page.wait_for_selector(
            config.container_selector, timeout=config.initial_load_timeout_ms
        )
    except Exception as e:
        console.print(
            f"[red]Timeout waiting for {PROGRESS_LABEL} to load: {str(e)}[/red]"
        )
        return []

    seen_urls: Set[str] = set()
    all_items: List[Dict[str, Any]] = []
    no_new_items_count = 0
    consecutive_same_height = 0
    original_url = page.url

    while (
        len(all_items) < config.max_items
        and no_new_items_count < config.scroll_config.max_no_new_items
    ):
        if config.expand_item_selector:
            for element in page.query_selector_all(config.expand_item_selector):
                try:
                    if element.is_visible():
                        element.click()
                        page.wait_for_timeout(config.click_wait_timeout_ms)
                except Exception as e:
                    console.print(f"[red]Failed to expand element: {str(e)}[/red]")

        current_items = scrape_schema(
            page, config.feed_schema, config.container_selector
        )
        new_items = 0

        for item in current_items:
            if len(all_items) >= config.max_items:
                break

            url = item.get(URL_FIELD)
            if url and url not in seen_urls:
                seen_urls.add(url)
                item_position = len(all_items)

                if config.deep_scrape and url:
                    handle_deep_scraping(
                        page, item, config, item_position, original_url
                    )

                all_items.append(item)
                new_items += 1

        if new_items == 0:
            no_new_items_count += 1
        else:
            no_new_items_count = 0

        consecutive_same_height, _ = handle_scrolling(
            page, new_items, consecutive_same_height, config
        )

        if (
            len(all_items) % random.randint(*config.scroll_config.random_pause_interval)
            == 0
        ):
            random_delay(2.0, 0.5)

    return all_items
