from typing import Optional
from playwright.sync_api import Page, ElementHandle
from rich.console import Console

console = Console()


def find_container(
    page: Page, selector: str, index: int, description: str = "container"
) -> Optional[ElementHandle]:
    """Find a container at a specific index with validation.

    Args:
        page: The page to search
        selector: CSS selector for containers
        index: Index of the container to find
        description: Human-readable description for logging

    Returns:
        The container element or None if not found or invalid
    """
    try:
        containers = page.query_selector_all(selector)

        if not containers:
            console.print(
                f"[yellow]No {description}s found with selector: '{selector}'[/yellow]"
            )
            return None

        console.print(f"[dim]Found {len(containers)} {description}s[/dim]")

        if index >= len(containers):
            console.print(
                f"[yellow]{description.capitalize()} at position {index} not found (total: {len(containers)})[/yellow]"
            )
            return None

        return containers[index]
    except Exception as e:
        console.print(
            f"[red]Error finding {description} at index {index}: {str(e)}[/red]"
        )
        return None
