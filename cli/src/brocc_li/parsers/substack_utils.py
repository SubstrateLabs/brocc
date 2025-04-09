import re
from datetime import datetime
from typing import Optional, Tuple

import dateparser
from unstructured.documents.elements import Element, Image


def extract_element_url(element: Element, url_type: str = "any") -> Optional[str]:
    """
    Extract a URL from an Element's metadata.

    Args:
        element: The unstructured Element to extract URL from
        url_type: Type of URL to extract - "any", "image", or "link"

    Returns:
        URL string if found, None otherwise
    """
    if not hasattr(element, "metadata"):
        return None

    if url_type == "image" or url_type == "any":
        # Check for image URLs
        if hasattr(element.metadata, "image_url") and element.metadata.image_url:
            return element.metadata.image_url

    if url_type == "link" or url_type == "any":
        # Check for link URLs
        if hasattr(element.metadata, "link_urls") and element.metadata.link_urls:
            if isinstance(element.metadata.link_urls, list) and len(element.metadata.link_urls) > 0:
                return element.metadata.link_urls[0]
            elif isinstance(element.metadata.link_urls, str):
                return element.metadata.link_urls

    # Check for generic url attribute
    if hasattr(element.metadata, "url") and element.metadata.url:
        return element.metadata.url

    return None


def parse_substack_relative_time(text: str) -> Tuple[str, str]:
    """
    Parse a Substack relative time string into action and timestamp components.

    Examples:
        "John liked this 5h ago" -> ("John liked this", "5h ago")
        "Sarah subscribed Jan 5" -> ("Sarah subscribed", "Jan 5")

    Args:
        text: The text string to parse

    Returns:
        Tuple of (action_text, timestamp)
    """
    # Look for common time patterns - these help us identify where to split the string
    time_patterns = [
        r"(\d+h)",  # 5h
        r"(\d+d)",  # 3d
        r"(\d+w)",  # 2w
        r"(\d+m)",  # 6m
        r"(\d+y)",  # 1y
        r"ago",  # "ago" suffix
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(\s+\d{1,2})?",  # Jan 5
        r"(\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))",  # 5 Jan
    ]

    # First try to find where to split the string
    for pattern in time_patterns:
        match = re.search(pattern, text)
        if match:
            # Find the start position of the timestamp
            start_idx = match.start()

            # Some cleanup - look for last word boundary before match
            # This helps with cases where the match might be part of a word
            text_before = text[:start_idx].strip()
            words_before = text_before.split()

            if words_before:
                # Try to guess a good split position
                action_text = " ".join(words_before)
                timestamp_text = text[start_idx:].strip()

                # Now try to parse the timestamp with dateparser
                # Keep original if parsing fails
                parsed_date = dateparser.parse(
                    timestamp_text, settings={"RELATIVE_BASE": datetime.now()}
                )

                if parsed_date:
                    # Use the original text to preserve Substack's relative time format
                    # This is often more descriptive than a fully parsed date
                    return action_text, timestamp_text
                else:
                    # Fallback to original split if dateparser can't handle it
                    return action_text, timestamp_text

    # If we couldn't find a clear pattern to split on,
    # try parsing the whole text with dateparser as a last resort
    try:
        parsed_date = dateparser.parse(text)
        if parsed_date:
            # If we can parse the whole text as a date, it's probably just a date with no action
            return "", text
    except Exception:
        pass

    # If no pattern is found, return the original text and empty timestamp
    return text, ""


def format_image_markdown(element: Image) -> Optional[str]:
    """
    Format an unstructured Image element as Markdown.

    Args:
        element: The Image element to format

    Returns:
        Markdown formatted image or None if no URL is found
    """
    if not isinstance(element, Image):
        return None

    # Get the image URL
    img_url = extract_element_url(element, url_type="image")
    if not img_url:
        return None

    # Get alt text
    alt_text = element.text if hasattr(element, "text") and element.text else "Image"

    # Format as markdown
    return f"![{alt_text}]({img_url})"
