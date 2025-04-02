from collections.abc import Callable
from typing import Any

from pydantic import BaseModel


class ExtractField(BaseModel):
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
    attribute: str | None = None

    # Function to transform the extracted value (e.g. strip whitespace, format URL)
    transform: Callable[[Any], Any] | None = None

    # Nested fields to extract from this element
    children: dict[str, "ExtractField"] | None = None

    # Custom extraction function for complex cases. Takes precedence over all other options.
    # Type: Callable[[Any, SchemaField], Any]
    # - First arg: The element to extract from (Any because it could be a Playwright ElementHandle or other type)
    # - Second arg: The SchemaField instance itself (useful for accessing field metadata)
    # - Returns: Any type of extracted value
    extract: Callable[[Any, "ExtractField"], Any] | None = None

    # Whether to extract multiple elements matching the selector (e.g. list of images)
    multiple: bool = False

    # Whether this field is the container selector for the schema
    is_container: bool = False
