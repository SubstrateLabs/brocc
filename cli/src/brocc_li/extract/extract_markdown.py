from html_to_markdown import convert_to_markdown
from playwright.sync_api import Page

from brocc_li.utils.logger import logger

# Minimum character length to consider extracted content valid
MIN_CONTENT_LENGTH = 100


def extract_markdown(page: Page, selector: str, min_length: int = MIN_CONTENT_LENGTH) -> str | None:
    """Extract HTML content from a page and convert it to markdown.

    Args:
        page: The page to extract content from
        selector: CSS selector to locate content
        min_length: Minimum length to consider content valid

    Returns:
        Converted markdown content or None if extraction failed
    """
    try:
        # Find all matching elements
        elements = page.query_selector_all(selector)
        if not elements:
            logger.warning(f"No elements found with selector: '{selector}'")
            return None

        # Get the largest content (by length)
        largest_content = max((el.inner_html() for el in elements), key=len, default="")

        # Validate content length
        if len(largest_content) < min_length:
            logger.warning(
                f"Content too short ({len(largest_content)} chars) with selector: '{selector}'"
            )
            return None

        # Convert to markdown
        content = convert_to_markdown(largest_content)
        logger.success(
            f"Successfully extracted content from '{selector}' ({len(largest_content)} chars)"
        )
        return content

    except Exception as e:
        logger.warning(f"Error extracting content with selector '{selector}': {str(e)}")
        return None
