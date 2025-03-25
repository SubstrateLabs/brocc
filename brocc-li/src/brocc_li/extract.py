from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel
from rich.console import Console

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

        # Print first container's HTML for debugging
        # console.print("\n[bold cyan]Sample Container HTML:[/bold cyan]")
        # console.print(containers[0].inner_html())
        # console.print("\n")

        # Extract data from each container
        posts = []
        for container in containers:
            try:
                # Extract all fields except container
                data = {}
                for field_name, field in schema.__dict__.items():
                    if field_name != "container" and isinstance(field, SchemaField):
                        data[field_name] = extract_field(container, field, field_name)
                posts.append(data)
            except Exception as e:
                console.print(f"[yellow]Failed to process container: {str(e)}[/yellow]")
                continue

        return posts
    except Exception as e:
        console.print(f"[red]Failed to scrape data: {str(e)}[/red]")
        return []
