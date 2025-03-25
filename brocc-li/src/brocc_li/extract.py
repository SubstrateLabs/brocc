from typing import List, Dict, Any, Optional, Callable, Set
from pydantic import BaseModel
from rich.console import Console
import random
import time

console = Console()


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
                f"[yellow]Warning: No container found for {parent_key} with selector {field.selector}[/yellow]"
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
            f"[yellow]Warning: No element found for {parent_key} with selector {field.selector}[/yellow]"
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

        # Extract data from each container
        items = []
        for container in containers:
            try:
                # Extract all fields except container
                data = {}
                for field_name, field in schema.__dict__.items():
                    if field_name != "container" and isinstance(field, SchemaField):
                        data[field_name] = extract_field(container, field, field_name)
                items.append(data)
            except Exception as e:
                console.print(f"[yellow]Failed to process container: {str(e)}[/yellow]")
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


def scroll_and_extract(
    page: Any,
    schema: type[BaseModel],
    container_selector: str,
    max_items: int = 5,
    click_selector: str | None = None,
    url_field: str = "url",
    progress_label: str = "items",
) -> List[Dict[str, Any]]:
    """Scroll through the page and extract items, handling deduplication and rate limiting.

    Args:
        page: Playwright page object
        schema: Pydantic model defining the extraction schema
        container_selector: CSS selector for the container elements to extract
        max_items: Maximum number of items to extract
        click_selector: Optional CSS selector for elements to click before each extraction (e.g. "Show more" or "Load more" buttons)
        url_field: Field name in the schema that contains unique URLs for deduplication
        progress_label: Label to use in progress messages (e.g. "tweets", "posts", "items")
    """
    seen_urls: Set[str] = set()
    all_items: List[Dict[str, Any]] = []
    last_height = 0
    no_new_items_count = 0
    max_no_new_items = 3
    consecutive_same_height = 0
    max_consecutive_same_height = 3
    scroll_patterns = ["normal", "slow", "fast", "bounce"]

    while len(all_items) < max_items and no_new_items_count < max_no_new_items:
        # Click any matching elements before extracting (e.g. "Show more" or "Load more" buttons)
        if click_selector:
            elements = page.query_selector_all(click_selector)
            for element in elements:
                try:
                    element.click()
                    console.print(
                        f"[cyan]Clicked element matching '{click_selector}'[/cyan]"
                    )
                    page.wait_for_timeout(500)  # Small delay after click
                except Exception:
                    pass  # Element might have disappeared or become stale

        # Extract current visible items
        current_items = scrape_schema(page, schema, container_selector)

        # Process new items
        new_items = 0
        for item in current_items:
            url = item.get(url_field)
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_items.append(item)
                new_items += 1

        # Update no_new_items counter
        if new_items == 0:
            no_new_items_count += 1
        else:
            no_new_items_count = 0

        # Smart scrolling logic with randomization
        current_height = page.evaluate("document.documentElement.scrollHeight")

        if current_height == last_height:
            consecutive_same_height += 1
            if consecutive_same_height >= max_consecutive_same_height:
                # Try different scroll strategies when stuck
                if consecutive_same_height % 2 == 0:
                    # Try scrolling to bottom and back up with random delays
                    page.evaluate(
                        "window.scrollTo(0, document.documentElement.scrollHeight)"
                    )
                    random_delay(0.5, 0.3)
                    page.evaluate("window.scrollTo(0, 0)")
                    random_delay(0.5, 0.3)
                else:
                    # Try a larger scroll with random amount
                    human_scroll(page, "fast")
                consecutive_same_height = 0
            else:
                # Random scroll pattern
                human_scroll(page, random.choice(scroll_patterns))
        else:
            consecutive_same_height = 0
            # Random scroll pattern
            human_scroll(page, random.choice(scroll_patterns))

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
            f"[cyan]Found {len(all_items)} unique {progress_label}... (stuck: {consecutive_same_height}/{max_consecutive_same_height})[/cyan]"
        )

        # Random pause every 15-25 items
        if len(all_items) % random.randint(15, 25) == 0:
            random_delay(2.0, 0.5)  # Longer random pause

    if no_new_items_count >= max_no_new_items:
        console.print(
            f"[yellow]No new {progress_label} found after multiple attempts. Reached end of feed.[/yellow]"
        )

    return all_items
