from playwright.sync_api import ElementHandle, Page

from brocc_li.utils.logger import logger


def find_element(
    parent: Page | ElementHandle,
    selector: str,
    required: bool = False,
    description: str = "element",
) -> ElementHandle | None:
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

        if required:
            logger.error(f"{description.capitalize()} not found with selector: '{selector}'")
        else:
            logger.warning(f"{description.capitalize()} not found with selector: '{selector}'")
        return None
    except Exception as e:
        logger.error(f"Error finding {description}: {str(e)}")
        return None
