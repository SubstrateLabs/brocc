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


class DeepScrapeOptions(BaseModel):
    """Configuration options for deep scraping content.

    Provides a simple way to customize the behavior of deep scraping
    when navigating to individual content pages.
    """

    # Whether to enable deep scraping of content from detail pages
    enabled: bool = False

    # CSS selector to find the content element on the detail page
    content_selector: str = "article"

    # Field name where the extracted markdown content will be stored
    markdown_field_name: str = "markdown_content"

    # Whether to wait for network idle when navigating to pages
    wait_networkidle: bool = True

    # Maximum time in milliseconds to wait for content selector to appear
    timeout_ms: int = 5000

    # Whether to attempt restoring the original scroll position after returning
    restore_scroll: bool = True

    # Minimum delay in milliseconds between scraping actions
    min_delay_ms: int = 1000

    # Maximum delay in milliseconds between scraping actions
    max_delay_ms: int = 3000

    # Factor for random jitter (0.0-1.0) - higher means more randomness
    jitter_factor: float = 0.3

    # Whether to save markdown content to files
    save_markdown: bool = False

    # Folder to save markdown files in
    markdown_folder: str = "debug"

    # Whether to include frontmatter in saved markdown files
    include_frontmatter: bool = True


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
    page: Any, schema: type[BaseModel], container_selector: str
) -> List[Dict[str, Any]]:
    """Scrape data using a schema definition."""
    try:
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


def human_scroll(page: Any, pattern: ScrollPattern) -> None:
    """Simulate human-like scrolling behavior."""
    viewport_height = page.evaluate("window.innerHeight")

    scroll_configs = {
        ScrollPattern.NORMAL: (0.8, 1.2),
        ScrollPattern.FAST: (1.5, 2.5),
        ScrollPattern.SLOW: (0.5, 0.8),
        ScrollPattern.BOUNCE: (1.2, 1.5),
    }

    if pattern == ScrollPattern.BOUNCE:
        down_amount = int(viewport_height * random.uniform(*scroll_configs[pattern]))
        up_amount = int(down_amount * random.uniform(0.3, 0.5))
        page.evaluate(f"window.scrollBy(0, {down_amount})")
        time.sleep(random.uniform(0.2, 0.4))
        page.evaluate(f"window.scrollBy(0, -{up_amount})")
    else:
        scroll_amount = int(viewport_height * random.uniform(*scroll_configs[pattern]))
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


def extract_content_from_page(page: Any, options: DeepScrapeOptions) -> Optional[str]:
    """Extract content from a page using multiple selectors."""
    selectors = [s.strip() for s in options.content_selector.split(",")]

    for selector in selectors:
        try:
            page.wait_for_selector(
                selector, timeout=options.timeout_ms // len(selectors)
            )
            console.print(f"[green]Found content with selector: '{selector}'[/green]")

            content_elements = page.query_selector_all(selector)
            if not content_elements:
                continue

            largest_content = max(
                (el.inner_html() for el in content_elements), key=len, default=""
            )

            if len(largest_content) > 100:
                console.print(
                    f"[green]Selected content from '{selector}' ({len(largest_content)} chars)[/green]"
                )
                return largest_content

        except Exception as e:
            console.print(
                f"[yellow]Error with selector '{selector}': {str(e)}[/yellow]"
            )
            continue

    return None


def save_markdown(item: Dict[str, Any], options: DeepScrapeOptions) -> str:
    """Save post content to a markdown file and return the filepath."""
    if not all(
        [
            options.markdown_field_name in item,
            item[options.markdown_field_name],
            "url" in item,
            item["url"],
        ]
    ):
        return ""

    os.makedirs(options.markdown_folder, exist_ok=True)
    filename = slugify(item["url"])
    filepath = os.path.join(options.markdown_folder, filename)

    content = item[options.markdown_field_name]
    if options.include_frontmatter:
        frontmatter = {
            "title": item.get("title", "Untitled"),
            "publication": item.get("publication", {}).get(
                "name", "Unknown Publication"
            ),
            "author": item.get("author", "Unknown Author"),
            "date": item.get("date", ""),
            "url": item["url"],
        }
        content = f"""---
title: "{frontmatter["title"]}"
publication: "{frontmatter["publication"]}"
author: "{frontmatter["author"]}"
date: {frontmatter["date"]}
url: {frontmatter["url"]}
---

{content}
"""

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


def scroll_and_extract(
    page: Any,
    schema: type[BaseModel],
    container_selector: str,
    max_items: int = 5,
    click_selector: str | None = None,
    url_field: str = "url",
    progress_label: str = "items",
    deep_scrape_options: Optional[DeepScrapeOptions] = None,
) -> List[Dict[str, Any]]:
    """Scroll through a page and extract items based on the provided schema.

    This function implements a smart scrolling algorithm that handles page navigation,
    deduplication of items, and extraction based on a defined schema. It simulates
    human-like scrolling behavior with randomized patterns and delays.

    Parameters:
        page: The Playwright page object to perform actions on.

        schema: A Pydantic BaseModel class that defines the structure and selectors
               for extracting data. This should have SchemaField attributes that
               specify how to extract each piece of data.

        container_selector: CSS selector string that identifies each container element
                           (e.g., a post, tweet, or card) to extract data from.

        max_items: Maximum number of items to extract before stopping. Default is 5.

        click_selector: Optional CSS selector for elements to click while scrolling,
                       such as "Load more" buttons. If None, no clicking is performed.

        url_field: Name of the field in the schema that contains the URL or unique ID
                  used for deduplication. Default is "url".

        progress_label: Label to use in progress messages for better readability,
                       e.g., "tweets", "posts", etc. Default is "items".

        deep_scrape_options: Configuration options for deep scraping. If None, deep scraping
                            is disabled. See DeepScrapeOptions class for details.

    Returns:
        A list of dictionaries where each dictionary contains the extracted data
        for one item according to the provided schema.
    """
    # Initialize by waiting for container selector
    try:
        console.print(f"[cyan]Waiting for {progress_label} to load...[/cyan]")
        page.wait_for_selector(container_selector, timeout=10000)
        console.print(f"[green]Found initial {progress_label}[/green]")
    except Exception as e:
        console.print(
            f"[red]Timeout waiting for {progress_label} to load: {str(e)}[/red]"
        )
        return []

    # Wait a bit for any dynamic content
    page.wait_for_timeout(2000)

    seen_urls: Set[str] = set()
    all_items: List[Dict[str, Any]] = []
    last_height = 0
    no_new_items_count = 0
    consecutive_same_height = 0
    scroll_config = ScrollConfig()

    deep_scrape_options = deep_scrape_options or DeepScrapeOptions(enabled=False)
    original_url = page.url

    while (
        len(all_items) < max_items
        and no_new_items_count < scroll_config.max_no_new_items
    ):
        # Handle clickable elements
        if click_selector:
            for element in page.query_selector_all(click_selector):
                try:
                    if element.is_visible():
                        element.click()
                        page.wait_for_timeout(500)
                except Exception as e:
                    console.print(f"[red]Failed to click element: {str(e)}[/red]")

        # Extract current items
        current_items = scrape_schema(page, schema, container_selector)
        new_items = 0

        for item in current_items:
            if len(all_items) >= max_items:
                break

            url = item.get(url_field)
            if url and url not in seen_urls:
                seen_urls.add(url)
                item_position = len(all_items)

                # Deep scraping logic
                if deep_scrape_options.enabled and url:
                    try:
                        console.print(
                            f"[cyan]Deep scraping content for item #{item_position + 1} ({len(all_items) + 1}/{max_items})[/cyan]"
                        )

                        # Store scroll position
                        scroll_y = (
                            page.evaluate("window.scrollY")
                            if deep_scrape_options.restore_scroll
                            else 0
                        )

                        # Find and click content link
                        visible_containers = page.query_selector_all(container_selector)
                        if visible_containers and item_position < len(
                            visible_containers
                        ):
                            container = visible_containers[item_position]
                            clickable = container.query_selector("a.reader2-inbox-post")

                            if clickable:
                                clickable.click()
                                page.wait_for_load_state("networkidle")
                                random_delay_with_jitter(
                                    1000, 2000, deep_scrape_options.jitter_factor
                                )

                                # Extract content
                                html_content = extract_content_from_page(
                                    page, deep_scrape_options
                                )
                                if html_content:
                                    markdown_content = convert_to_markdown(html_content)
                                    item[deep_scrape_options.markdown_field_name] = (
                                        markdown_content
                                    )

                                    if deep_scrape_options.save_markdown:
                                        filepath = save_markdown(
                                            item, deep_scrape_options
                                        )
                                        if filepath:
                                            console.print(
                                                f"[green]Saved markdown to: {filepath}[/green]"
                                            )
                                else:
                                    # Fallback to body content
                                    body_element = page.query_selector("body")
                                    if body_element:
                                        body_html = body_element.inner_html()
                                        markdown_content = convert_to_markdown(
                                            body_html
                                        )
                                        item[
                                            deep_scrape_options.markdown_field_name
                                        ] = markdown_content
                                    else:
                                        item[
                                            deep_scrape_options.markdown_field_name
                                        ] = "No content found"

                        # Navigate back
                        random_delay_with_jitter(
                            deep_scrape_options.min_delay_ms // 2,
                            deep_scrape_options.max_delay_ms // 2,
                            deep_scrape_options.jitter_factor,
                        )

                        page.go_back(
                            wait_until="networkidle"
                            if deep_scrape_options.wait_networkidle
                            else None
                        )

                        if deep_scrape_options.restore_scroll and scroll_y > 0:
                            random_delay_with_jitter(
                                500, 1000, deep_scrape_options.jitter_factor
                            )
                            page.evaluate(f"window.scrollTo(0, {scroll_y})")

                    except Exception as e:
                        console.print(
                            f"[red]Error during deep scraping: {str(e)}[/red]"
                        )
                        item[deep_scrape_options.markdown_field_name] = (
                            f"Error: {str(e)}"
                        )

                        # Ensure we're back at the original page
                        if page.url != original_url:
                            try:
                                page.go_back(
                                    wait_until="networkidle"
                                    if deep_scrape_options.wait_networkidle
                                    else None
                                )
                                if page.url != original_url:
                                    page.goto(
                                        original_url,
                                        wait_until="networkidle"
                                        if deep_scrape_options.wait_networkidle
                                        else None,
                                    )
                            except Exception as nav_error:
                                console.print(
                                    f"[red]Navigation error: {str(nav_error)}[/red]"
                                )
                                try:
                                    page.goto(original_url)
                                except:
                                    console.print(
                                        "[red]Failed all navigation attempts![/red]"
                                    )

                all_items.append(item)
                new_items += 1

        # Update counters
        if new_items == 0:
            no_new_items_count += 1
            console.print(
                f"[dim]No new items found (attempt {no_new_items_count}/{scroll_config.max_no_new_items})[/dim]"
            )
        else:
            no_new_items_count = 0
            console.print(f"[dim]Found {new_items} new items[/dim]")

        # Smart scrolling
        current_height = page.evaluate("document.documentElement.scrollHeight")

        if current_height == last_height:
            consecutive_same_height += 1
            if consecutive_same_height >= scroll_config.max_consecutive_same_height:
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

        last_height = current_height

        # Adaptive delays
        if new_items > 0:
            random_delay(0.3, 0.2)
        elif consecutive_same_height > 0:
            random_delay(1.0, 0.3)
        else:
            random_delay(0.5, 0.2)

        # Progress update
        console.print(
            f"[dim]Found {len(all_items)} unique {progress_label}... (stuck: {consecutive_same_height}/{scroll_config.max_consecutive_same_height})[/dim]"
        )

        # Random pause
        if len(all_items) % random.randint(*scroll_config.random_pause_interval) == 0:
            random_delay(2.0, 0.5)

    if no_new_items_count >= scroll_config.max_no_new_items:
        console.print(
            f"[dim]No new {progress_label} found after multiple attempts. Reached end of feed.[/dim]"
        )

    return all_items
