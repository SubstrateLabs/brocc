from typing import List, Dict, Any, Optional, Callable, Set
from pydantic import BaseModel
from rich.console import Console
import random
import time
from html_to_markdown import convert_to_markdown
import os
import urllib.parse
import re
from datetime import datetime

console = Console()


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
        result = {}
        for key, child in field.children.items():
            result[key] = extract_field(container, child, f"{parent_key}.{key}")
        return result

    if field.multiple:
        elements = element.query_selector_all(field.selector)
        results = []
        for el in elements:
            if field.attribute:
                value = el.get_attribute(field.attribute)
            else:
                value = el.inner_text()
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

    if field.attribute:
        value = element.get_attribute(field.attribute)
    else:
        value = element.inner_text()

    if field.transform:
        value = field.transform(value)

    return value


def scrape_schema(
    page: Any, schema: type[BaseModel], container_selector: str
) -> List[Dict[str, Any]]:
    """Scrape data using a schema definition."""
    try:
        # Get all container elements
        containers = page.query_selector_all(container_selector)
        console.print(f"[dim]Found {len(containers)} containers[/dim]")

        # Extract data from each container
        items = []
        for i, container in enumerate(containers):
            try:
                # Debug: Check if container is still valid
                if not container.is_visible():
                    console.print(f"[dim]Container {i} is not visible, skipping[/dim]")
                    continue

                # Extract all fields except container
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


def human_scroll(page: Any, scroll_type: str = "normal") -> None:
    """Simulate human-like scrolling behavior."""
    if scroll_type == "normal":
        # Random scroll amount between 80-120% of viewport height
        scroll_amount = int(
            page.evaluate("window.innerHeight") * random.uniform(0.8, 1.2)
        )
        page.evaluate(f"window.scrollBy(0, {scroll_amount})")
    elif scroll_type == "fast":
        # Faster scroll with more variation
        scroll_amount = int(
            page.evaluate("window.innerHeight") * random.uniform(1.5, 2.5)
        )
        page.evaluate(f"window.scrollBy(0, {scroll_amount})")
    elif scroll_type == "slow":
        # Slower, more precise scroll
        scroll_amount = int(
            page.evaluate("window.innerHeight") * random.uniform(0.5, 0.8)
        )
        page.evaluate(f"window.scrollBy(0, {scroll_amount})")
    elif scroll_type == "bounce":
        # Scroll down and up slightly like a human might do
        down_amount = int(
            page.evaluate("window.innerHeight") * random.uniform(1.2, 1.5)
        )
        up_amount = int(down_amount * random.uniform(0.3, 0.5))
        page.evaluate(f"window.scrollBy(0, {down_amount})")
        time.sleep(random.uniform(0.2, 0.4))
        page.evaluate(f"window.scrollBy(0, -{up_amount})")


def random_delay_with_jitter(
    min_ms: int, max_ms: int, jitter_factor: float = 0.3
) -> None:
    """Add a random delay with jitter to make scraping more human-like and avoid rate limits.

    Args:
        min_ms: Minimum delay time in milliseconds
        max_ms: Maximum delay time in milliseconds
        jitter_factor: Factor for random jitter (0.0-1.0)
    """
    # Convert to seconds
    min_delay = min_ms / 1000
    max_delay = max_ms / 1000

    # Base delay from the range
    base_delay = random.uniform(min_delay, max_delay)

    # Add jitter, but ensure we don't exceed max_delay
    jitter = base_delay * jitter_factor * random.choice([-1, 1])
    final_delay = min(
        max_delay, max(0.1, base_delay + jitter)
    )  # Ensure delay is at least 0.1 second and at most max_delay

    console.print(f"[dim]Waiting for {final_delay:.2f} seconds...[/dim]")
    time.sleep(final_delay)


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
    seen_urls: Set[str] = set()
    all_items: List[Dict[str, Any]] = []
    last_height = 0
    no_new_items_count = 0
    max_no_new_items = 3
    consecutive_same_height = 0
    max_consecutive_same_height = 3
    scroll_patterns = ["normal", "slow", "fast", "bounce"]

    # Use default options if not provided
    if deep_scrape_options is None:
        deep_scrape_options = DeepScrapeOptions(enabled=False)

    # Store original URL for navigation back after deep scraping
    original_url = page.url

    while len(all_items) < max_items and no_new_items_count < max_no_new_items:
        # Click any matching elements before extracting
        if click_selector:
            elements = page.query_selector_all(click_selector)
            console.print(f"[dim]Found {len(elements)} elements to click[/dim]")
            for i, element in enumerate(elements):
                try:
                    if not element.is_visible():
                        console.print(
                            f"[dim]Click element {i} is not visible, skipping[/dim]"
                        )
                        continue
                    element.click()
                    console.print(
                        f"[dim]Clicked element {i} matching '{click_selector}'[/dim]"
                    )
                    page.wait_for_timeout(500)  # Small delay after click
                except Exception as e:
                    console.print(f"[red]Failed to click element {i}: {str(e)}[/red]")
                    pass  # Element might have disappeared or become stale

        # Extract current visible items
        current_items = scrape_schema(page, schema, container_selector)
        console.print(f"[dim]Extracted {len(current_items)} current items[/dim]")

        # Process new items and perform deep scraping if enabled
        new_items = 0
        for item in current_items:
            # Stop processing if we've reached the maximum number of items
            if len(all_items) >= max_items:
                console.print(
                    f"[green]Reached maximum of {max_items} items, stopping extraction[/green]"
                )
                break

            url = item.get(url_field)
            if url and url not in seen_urls:
                seen_urls.add(url)

                # Get the position in feed of this item to find it later for clicking
                item_position = len(all_items)

                # Perform deep scraping if enabled
                if deep_scrape_options.enabled and url:
                    try:
                        console.print(
                            f"[cyan]Deep scraping content for item #{item_position + 1} ({len(all_items) + 1}/{max_items})[/cyan]"
                        )

                        # Single delay before scraping to avoid rate limits
                        random_delay_with_jitter(
                            deep_scrape_options.min_delay_ms,
                            deep_scrape_options.max_delay_ms,
                            deep_scrape_options.jitter_factor,
                        )

                        # Store current position for scrolling back
                        scroll_y = (
                            page.evaluate("window.scrollY")
                            if deep_scrape_options.restore_scroll
                            else 0
                        )

                        # Find the current visible container elements
                        visible_containers = page.query_selector_all(container_selector)

                        # Only proceed if we have containers to work with
                        if visible_containers and item_position < len(
                            visible_containers
                        ):
                            # Get the specific container for this item
                            container = visible_containers[item_position]

                            # Find and click the clickable link in the container
                            clickable = container.query_selector("a.reader2-inbox-post")
                            if clickable:
                                console.print(
                                    f"[cyan]Clicking on post to navigate to content...[/cyan]"
                                )
                                # Click the element to navigate
                                clickable.click()

                                # Wait for navigation and page load (single wait)
                                page.wait_for_load_state("networkidle")

                                # Only one delay after page is loaded
                                random_delay_with_jitter(
                                    1000, 2000, deep_scrape_options.jitter_factor
                                )

                                # Let page fully render
                                console.print(
                                    f"[cyan]Loaded page at: {page.url}[/cyan]"
                                )

                                # Handle multiple selectors separated by commas
                                selectors = deep_scrape_options.content_selector.split(
                                    ","
                                )
                                content_found = False
                                html_content = ""

                                # Try each selector until we find content
                                for selector in selectors:
                                    selector = selector.strip()
                                    try:
                                        # Wait for this specific selector
                                        try:
                                            page.wait_for_selector(
                                                selector,
                                                timeout=deep_scrape_options.timeout_ms
                                                // len(selectors),
                                            )
                                            console.print(
                                                f"[green]Found content with selector: '{selector}'[/green]"
                                            )
                                        except Exception as e:
                                            console.print(
                                                f"[dim]Selector '{selector}' not found, trying next...[/dim]"
                                            )
                                            continue

                                        # Get all elements matching this selector
                                        content_elements = page.query_selector_all(
                                            selector
                                        )
                                        if (
                                            content_elements
                                            and len(content_elements) > 0
                                        ):
                                            # If multiple elements match, try to find the largest one
                                            # which is likely the main content
                                            largest_len = 0
                                            largest_content = ""

                                            for el in content_elements:
                                                current_content = el.inner_html()
                                                if len(current_content) > largest_len:
                                                    largest_len = len(current_content)
                                                    largest_content = current_content

                                            if (
                                                largest_len > 100
                                            ):  # Arbitrary minimum content length
                                                html_content = largest_content
                                                content_found = True
                                                console.print(
                                                    f"[green]Selected content from '{selector}' ({largest_len} chars)[/green]"
                                                )
                                                break
                                            else:
                                                console.print(
                                                    f"[yellow]Content from '{selector}' too short ({largest_len} chars)[/yellow]"
                                                )
                                    except Exception as selector_error:
                                        console.print(
                                            f"[yellow]Error with selector '{selector}': {str(selector_error)}[/yellow]"
                                        )

                                # Process the content if found
                                if content_found and html_content:
                                    # Convert HTML to markdown using html-to-markdown
                                    markdown_content = convert_to_markdown(html_content)
                                    # Add markdown content to the item
                                    item[deep_scrape_options.markdown_field_name] = (
                                        markdown_content
                                    )
                                    console.print(
                                        f"[green]Successfully extracted markdown content ({len(markdown_content)} chars)[/green]"
                                    )

                                    # Save markdown file if enabled
                                    if deep_scrape_options.save_markdown:
                                        filepath = save_markdown(
                                            item, deep_scrape_options
                                        )
                                        if filepath:
                                            console.print(
                                                f"[green]Saved markdown to: {filepath}[/green]"
                                            )
                                else:
                                    # Last resort: try to get the whole page content
                                    try:
                                        body_element = page.query_selector("body")
                                        if body_element:
                                            body_html = body_element.inner_html()
                                            console.print(
                                                f"[yellow]Using full page body as fallback ({len(body_html)} chars)[/yellow]"
                                            )
                                            markdown_content = convert_to_markdown(
                                                body_html
                                            )
                                            item[
                                                deep_scrape_options.markdown_field_name
                                            ] = markdown_content

                                            # Save markdown file if enabled
                                            if deep_scrape_options.save_markdown:
                                                filepath = save_markdown(
                                                    item, deep_scrape_options
                                                )
                                                if filepath:
                                                    console.print(
                                                        f"[green]Saved markdown to: {filepath}[/green]"
                                                    )
                                        else:
                                            console.print(
                                                f"[red]No content found with any selector[/red]"
                                            )
                                            item[
                                                deep_scrape_options.markdown_field_name
                                            ] = "No content found"
                                    except Exception as body_error:
                                        console.print(
                                            f"[red]Error extracting body content: {str(body_error)}[/red]"
                                        )
                                        item[
                                            deep_scrape_options.markdown_field_name
                                        ] = f"Error: {str(body_error)}"

                        # Single delay before navigating back
                        random_delay_with_jitter(
                            deep_scrape_options.min_delay_ms // 2,  # Reduced delay
                            deep_scrape_options.max_delay_ms // 2,  # Reduced delay
                            deep_scrape_options.jitter_factor,
                        )

                        # Navigate back using browser's back button
                        console.print(
                            f"[cyan]Navigating back to original page using back button...[/cyan]"
                        )
                        page.go_back(
                            wait_until="networkidle"
                            if deep_scrape_options.wait_networkidle
                            else None
                        )

                        # Single delay after navigation with restore scroll
                        if deep_scrape_options.restore_scroll and scroll_y > 0:
                            random_delay_with_jitter(
                                500, 1000, deep_scrape_options.jitter_factor
                            )
                            page.evaluate(f"window.scrollTo(0, {scroll_y})")
                            console.print(
                                f"[dim]Restored scroll position to {scroll_y}[/dim]"
                            )

                    except Exception as e:
                        console.print(
                            f"[red]Error during deep scraping: {str(e)}[/red]"
                        )
                        item[deep_scrape_options.markdown_field_name] = (
                            f"Error: {str(e)}"
                        )

                        # Make sure we're back at the original page by using back button
                        try:
                            if page.url != original_url:
                                console.print(
                                    f"[yellow]Attempting to navigate back to {original_url}[/yellow]"
                                )
                                page.go_back(
                                    wait_until="networkidle"
                                    if deep_scrape_options.wait_networkidle
                                    else None
                                )

                                # If still not back at the original URL, try direct navigation as fallback
                                if page.url != original_url:
                                    console.print(
                                        f"[yellow]Back button didn't work, trying direct navigation...[/yellow]"
                                    )
                                    if deep_scrape_options.wait_networkidle:
                                        page.goto(
                                            original_url, wait_until="networkidle"
                                        )
                                    else:
                                        page.goto(original_url)

                                page.wait_for_timeout(1000)
                        except Exception as nav_error:
                            console.print(
                                f"[red]Navigation error: {str(nav_error)}[/red]"
                            )
                            # Last resort: direct navigation
                            try:
                                page.goto(original_url)
                            except:
                                console.print(
                                    f"[red]Failed all navigation attempts![/red]"
                                )

                # Add the item to our collection
                all_items.append(item)
                new_items += 1
                console.print(f"[dim]Found new item with URL: {url}[/dim]")

        # Update no_new_items counter
        if new_items == 0:
            no_new_items_count += 1
            console.print(
                f"[dim]No new items found (attempt {no_new_items_count}/{max_no_new_items})[/dim]"
            )
        else:
            no_new_items_count = 0
            console.print(f"[dim]Found {new_items} new items[/dim]")

        # Smart scrolling logic with randomization
        current_height = page.evaluate("document.documentElement.scrollHeight")
        console.print(f"[dim]Current page height: {current_height}[/dim]")

        if current_height == last_height:
            consecutive_same_height += 1
            if consecutive_same_height >= max_consecutive_same_height:
                # Try different scroll strategies when stuck
                if consecutive_same_height % 2 == 0:
                    console.print("[dim]Trying scroll to bottom and back up[/dim]")
                    page.evaluate(
                        "window.scrollTo(0, document.documentElement.scrollHeight)"
                    )
                    random_delay(0.5, 0.3)
                    page.evaluate("window.scrollTo(0, 0)")
                    random_delay(0.5, 0.3)
                else:
                    console.print("[dim]Trying fast scroll[/dim]")
                    human_scroll(page, "fast")
                consecutive_same_height = 0
            else:
                # Random scroll pattern
                pattern = random.choice(scroll_patterns)
                console.print(f"[dim]Using scroll pattern: {pattern}[/dim]")
                human_scroll(page, pattern)
        else:
            consecutive_same_height = 0
            # Random scroll pattern
            pattern = random.choice(scroll_patterns)
            console.print(f"[dim]Using scroll pattern: {pattern}[/dim]")
            human_scroll(page, pattern)

        last_height = current_height

        # Adaptive delay with randomization
        if new_items > 0:
            random_delay(0.3, 0.2)  # Fast when finding items
        elif consecutive_same_height > 0:
            random_delay(1.0, 0.3)  # Slower when stuck
        else:
            random_delay(0.5, 0.2)  # Normal speed

        # Update progress
        console.print(
            f"[dim]Found {len(all_items)} unique {progress_label}... (stuck: {consecutive_same_height}/{max_consecutive_same_height})[/dim]"
        )

        # Random pause every 15-25 items
        if len(all_items) % random.randint(15, 25) == 0:
            random_delay(2.0, 0.5)  # Longer random pause

    if no_new_items_count >= max_no_new_items:
        console.print(
            f"[dim]No new {progress_label} found after multiple attempts. Reached end of feed.[/dim]"
        )

    return all_items


def slugify(url: str) -> str:
    """Convert a URL to a slugified filename."""
    # Parse the URL and extract the path
    parsed_url = urllib.parse.urlparse(url)
    path = parsed_url.path.strip("/")

    # Remove file extension if present
    path = os.path.splitext(path)[0]

    # Replace special characters with hyphens
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", path)

    # Remove leading and trailing hyphens and convert to lowercase
    slug = slug.strip("-").lower()

    # Ensure the slug is not empty
    if not slug:
        # Use netloc (domain) if path is empty
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", parsed_url.netloc).strip("-").lower()

    # Add .md extension
    return f"{slug}.md"


def save_markdown(item: Dict[str, Any], options: DeepScrapeOptions) -> str:
    """Save post content to a markdown file and return the filepath."""
    if (
        options.markdown_field_name not in item
        or not item[options.markdown_field_name]
        or "url" not in item
        or not item["url"]
    ):
        return ""

    # Create folder if it doesn't exist
    os.makedirs(options.markdown_folder, exist_ok=True)

    # Create a filename from the URL
    filename = slugify(item["url"])
    filepath = os.path.join(options.markdown_folder, filename)

    # Get content
    content = item[options.markdown_field_name]

    # Format the content with frontmatter if enabled
    if options.include_frontmatter:
        title = item.get("title", "Untitled")
        pub_name = item.get("publication", {}).get("name", "Unknown Publication")
        author = item.get("author", "Unknown Author")
        date = item.get("date", "")

        formatted_content = f"""---
title: "{title}"
publication: "{pub_name}"
author: "{author}"
date: {date}
url: {item["url"]}
---

{content}
"""
    else:
        formatted_content = content

    # Write to file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(formatted_content)

    return filepath
