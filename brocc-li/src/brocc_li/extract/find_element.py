from typing import Optional, Union
from playwright.sync_api import Page, ElementHandle
from rich.console import Console

console = Console()


def find_element(
    parent: Union[Page, ElementHandle],
    selector: str,
    required: bool = False,
    description: str = "element",
) -> Optional[ElementHandle]:
    """Safely find a single element with proper error handling.

    Args:
        parent: The page or parent element to search within
        selector: CSS selector to locate the element
        required: Whether the element is required (error vs warning log)
        description: Human-readable description for logging

    Returns:
        The element or None if not found
    """
    try:
        element = parent.query_selector(selector)
        if element:
            return element

        log_level = "red" if required else "yellow"
        console.print(
            f"[{log_level}]{description.capitalize()} not found with selector: '{selector}'[/{log_level}]"
        )
        return None
    except Exception as e:
        console.print(f"[red]Error finding {description}: {str(e)}[/red]")
        return None
