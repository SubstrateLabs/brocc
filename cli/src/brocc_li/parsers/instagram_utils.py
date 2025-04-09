from typing import List, Optional

from unstructured.documents.elements import Element, Image, Text
from unstructured.partition.html import partition_html

from brocc_li.utils.logger import logger


def partition_instagram_html(html: str, debug: bool = False) -> List[Element]:
    """Parse Instagram HTML with unstructured and apply basic filtering"""
    logger.info("Starting Instagram HTML parsing with unstructured...")
    elements: List[Element] = partition_html(text=html)
    logger.info(f"unstructured found {len(elements)} raw elements.")

    if not elements:
        logger.warning("unstructured.partition_html returned no elements.")
        return []

    # Apply minimal filtering initially
    filtered_elements: List[Element] = []
    for i, element in enumerate(elements):
        element_text = str(element)
        # Very minimal filtering initially
        if element_text.strip() == "":
            if debug:
                logger.debug(f"Filtering empty element {i + 1}")
            continue
        filtered_elements.append(element)
        if debug:
            logger.debug(
                f"Element {i + 1} type: {type(element).__name__}, text: {element_text[:100]}..."
            )

    logger.info(f"Kept {len(filtered_elements)} elements after minimal filtering.")
    return filtered_elements


def clean_element_text(text: str, max_length: Optional[int] = None) -> str:
    """Clean element text of common noise patterns found in Instagram HTML."""
    if not text:
        return ""

    # Remove common noise characters
    cleaned = text.replace("·", "").strip()

    # Truncate if needed
    if max_length and len(cleaned) > max_length:
        return cleaned[:max_length] + "..."

    return cleaned


def is_timestamp(element: Element) -> bool:
    """Check if an element is likely an Instagram timestamp."""
    if not isinstance(element, Text):
        return False

    text = str(element).strip()
    time_indicators = ["w", "h", "m", "d", "ago", "now"]

    # Instagram timestamps are typically short with time indicators
    return len(text) < 15 and any(ind in text for ind in time_indicators)


def format_timestamp(text: str) -> str:
    """Format an Instagram timestamp string consistently."""
    if not text:
        return ""

    # Strip and add parentheses if not already present
    formatted = text.strip()
    if not (formatted.startswith("(") and formatted.endswith(")")):
        formatted = f"({formatted})"

    return formatted


def is_profile_picture(element: Element) -> bool:
    """Check if an element is an Instagram profile picture."""
    return isinstance(element, Image) and (
        "profile picture" in str(element).lower() or "User avatar" in str(element)
    )


def is_section_header(element: Element, headers: Optional[List[str]] = None) -> bool:
    """Check if an element is a section header."""
    if headers is None:
        headers = ["Primary", "General", "Requests", "Posts", "Reels", "Tagged"]

    return isinstance(element, Text) and str(element).strip() in headers
