import re
from typing import Optional, Tuple

from bs4 import Tag

from brocc_li.utils.logger import logger

from .twitter_utils import (
    extract_text_based_user_info,
    format_user_markdown_header,
    process_html_with_parser,
)


def extract_follower_info_from_text(
    text: str, debug: bool = False
) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract name and handle from the text content of follower elements.

    Args:
        text: Raw text from the follower element
        debug: Enable debug logging

    Returns:
        Tuple of (name, handle)
    """
    # Use the shared utility function with the same signature
    return extract_text_based_user_info(text, debug)


def extract_follower_bio_from_text(text: str, debug: bool = False) -> str:
    """
    Extract bio from the text content after removing name, handle, and action buttons.

    Args:
        text: Raw text from the follower element
        debug: Enable debug logging

    Returns:
        Bio text
    """
    # Try to extract bio after common action texts
    for action in ["Follow", "Following", "Follows you", "Click to Follow", "Click to Unfollow"]:
        if action in text:
            parts = text.split(action, 1)
            if len(parts) > 1:
                # The bio is likely after the action text
                potential_bio = parts[1].strip()

                # First clean up common Twitter UI text that might be included
                ui_texts_to_remove = [
                    "to Follow",
                    "Follow back",
                    "to Unfollow",
                    "Click to",
                    "youClick",
                    "you",
                    "Click",
                    "youFollowingClick",
                ]

                for ui_text in ui_texts_to_remove:
                    potential_bio = potential_bio.replace(ui_text, "").strip()

                # Remove handle repetition at the beginning
                # This pattern often appears at the start of bios after UI elements are removed
                handle_match = re.match(r"^([a-zA-Z0-9_]+)", potential_bio)
                if handle_match:
                    handle_text = handle_match.group(1)
                    # Only remove if it looks like a Twitter handle (not normal text)
                    if len(handle_text) > 3 and re.match(r"^[a-zA-Z0-9_]+$", handle_text):
                        potential_bio = potential_bio[len(handle_text) :].strip()

                # Clean up any remaining Twitter UI artifacts
                # Common patterns in bios that should be removed
                artifacts = [
                    r"^\s*\d+\s*$",  # Just numbers
                    r"^\s*$",  # Empty strings
                ]

                for pattern in artifacts:
                    if re.match(pattern, potential_bio):
                        potential_bio = ""
                        break

                # Skip if the bio is just an empty string after cleaning
                if potential_bio:
                    if debug:
                        logger.debug(
                            f"Extracted bio: '{potential_bio[:50]}{'...' if len(potential_bio) > 50 else ''}'"
                        )
                    return potential_bio

    if debug:
        logger.debug(f"Could not extract bio from: '{text[:50]}...'")
    return ""


def format_follower_markdown(name: Optional[str], handle: Optional[str], bio: str) -> str:
    """Format follower information into markdown."""
    markdown_parts = []

    # Use the shared format function for the header
    header = format_user_markdown_header(name, handle, handle_url=f"/{handle}" if handle else None)
    markdown_parts.append(header)

    # Add bio if available
    if bio:
        markdown_parts.append(bio)

    return "\n\n".join(markdown_parts)


def process_follower_element(follower_element: Tag, debug: bool = False) -> Optional[str]:
    """
    Process a single follower element and convert to markdown.
    Used as the processor function for process_html_with_parser.
    """
    # Extract text from the element
    element_text = follower_element.get_text(strip=True)

    # Skip if element has no text or is very short
    if not element_text or len(element_text) < 5:
        if debug:
            logger.debug(f"Element has no meaningful text: {element_text[:20]}")
        return None

    if debug:
        truncated_text = element_text[:100] + ("..." if len(element_text) > 100 else "")
        logger.debug(f"Element text: {truncated_text}")

    # Extract follower information from text
    name, handle = extract_follower_info_from_text(element_text, debug=debug)

    # Skip if we couldn't extract a name or handle
    if not name and not handle:
        if debug:
            logger.debug(f"Could not extract name or handle from: {element_text[:50]}...")
        return None

    # Extract bio from text
    bio = extract_follower_bio_from_text(element_text, debug=debug)

    # Format to markdown
    return format_follower_markdown(name, handle, bio)


def twitter_followers_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Convert Twitter followers HTML to markdown.

    Args:
        html: Raw HTML of Twitter followers page
        debug: Enable debug output

    Returns:
        Markdown string or None if parsing failed
    """
    # Use the shared HTML processing function
    return process_html_with_parser(
        html=html,
        element_selector='[data-testid="cellInnerDiv"]',
        processor_function=process_follower_element,
        join_str="\n\n",
        debug=debug,
    )
