from typing import Optional
from playwright.sync_api import Page, ElementHandle
from brocc_li.utils.logger import logger


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
            logger.warning(f"No {description}s found with selector: '{selector}'")
            return None

        logger.debug(f"Found {len(containers)} {description}s")

        if index >= len(containers):
            logger.warning(
                f"{description.capitalize()} at position {index} not found (total: {len(containers)})"
            )
            return None

        return containers[index]
    except Exception as e:
        logger.error(f"Error finding {description} at index {index}: {str(e)}")
        return None
