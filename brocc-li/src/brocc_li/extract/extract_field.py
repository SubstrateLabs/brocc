from typing import Any
from brocc_li.types.extract_field import ExtractField
from rich.console import Console


console = Console()


def extract_field(element: Any, field: ExtractField, parent_key: str = "") -> Any:
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
