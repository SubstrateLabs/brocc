from typing import List, Optional

from unstructured.documents.elements import Element, NarrativeText, Text, Title

from brocc_li.parsers.instagram_utils import (
    clean_element_text,
    format_timestamp,
    is_profile_picture,
    is_section_header,
    is_timestamp,
    partition_instagram_html,
)
from brocc_li.utils.logger import logger


def _format_thread(elements: List[Element], debug: bool = False) -> Optional[str]:
    """Formats a list of elements representing a conversation thread preview."""
    if not elements:
        return None

    username = None
    snippet = None
    timestamp = None
    status = []  # Can have multiple statuses like "Unread", "Active"

    if debug:
        logger.debug(f"Formatting thread with {len(elements)} elements:")
        for el in elements:
            logger.debug(f"  - Type: {type(el).__name__}, Text: '{str(el)}'")

    # Simple extraction logic based on observed patterns
    # Assumes order: Username, Snippet, Timestamp, Statuses
    element_texts = [str(el).strip() for el in elements if str(el).strip()]

    if not element_texts:
        return None

    # First non-empty text is likely username
    username = element_texts[0]
    remaining_texts = element_texts[1:]

    # Look for timestamp among remaining texts
    for i, text in enumerate(remaining_texts):
        if is_timestamp(Text(text=text)):
            timestamp = text
            # Assume snippet is everything before timestamp
            snippet = " ".join(remaining_texts[:i])
            # Statuses are everything after
            status = [s for s in remaining_texts[i + 1 :] if s]
            break
    else:
        # If no timestamp found, assume the rest is the snippet
        snippet = " ".join(remaining_texts)

    # Clean the snippet text
    if snippet:
        snippet = clean_element_text(snippet)

    # Assemble the markdown line
    line = f"* **{username}**"
    if snippet:
        line += f": {snippet}"
    if timestamp:
        line += f" {format_timestamp(timestamp)}"
    if status:
        line += f" [{', '.join(status)}]"

    if debug:
        logger.debug(f"Formatted thread: {line}")

    return line


def instagram_inbox_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Converts Instagram Inbox HTML to Markdown using unstructured.
    Formats each conversation thread as a markdown list item.

    Args:
        html: The HTML content of the Instagram Inbox page.
        debug: If True, enables detailed debug logging.

    Returns:
        A string containing the Markdown representation of the inbox,
        or None if an error occurs or no content is found.
    """
    logger.info("Starting Instagram Inbox HTML to Markdown conversion...")
    try:
        elements: List[Element] = partition_instagram_html(html, debug=debug)

        if not elements:
            logger.warning("No elements found by unstructured for Inbox HTML.")
            return "<!-- No elements found by unstructured -->"

        formatted_threads = []
        current_thread_elements: List[Element] = []

        for i, element in enumerate(elements):
            element_text = str(element).strip()
            if debug:
                logger.debug(
                    f"Inbox Element {i + 1}: Type={type(element).__name__}, Text='{element_text[:100]}...'"
                )

            # Skip section headers - we're making a flat list
            if is_section_header(element):
                continue

            # Detect thread start (usually follows an avatar image)
            if is_profile_picture(element):
                # Format the previous thread
                if current_thread_elements:
                    formatted = _format_thread(current_thread_elements, debug=debug)
                    if formatted:
                        formatted_threads.append(formatted)
                current_thread_elements = []  # Reset for the new thread
                if debug:
                    logger.debug(f"Detected potential thread start after avatar at element {i + 1}")
                continue  # Skip the avatar itself

            # Filter out noisy elements we don't want in threads
            if isinstance(element, Title) and "vprtwn" in element_text:  # Skip header title
                continue
            if isinstance(element, Text) and element_text == "Active":  # Skip standalone "Active"
                continue
            if isinstance(element, Title) and "Your messages" in element_text:  # Skip footer
                continue
            if (
                isinstance(element, NarrativeText) and "Send a message" in element_text
            ):  # Skip footer
                continue
            if isinstance(element, Text) and "Send message" in element_text:  # Skip footer button
                continue

            # Add element to current thread
            current_thread_elements.append(element)

        # Process the last thread
        if current_thread_elements:
            formatted = _format_thread(current_thread_elements, debug=debug)
            if formatted:
                formatted_threads.append(formatted)

        if not formatted_threads:
            logger.warning("unstructured parsing resulted in no markdown lines after formatting.")
            return "<!-- unstructured parsing completed, but resulted in empty output -->"

        markdown = "\n".join(formatted_threads)
        logger.info(
            f"Instagram Inbox HTML to markdown conversion completed. Found {len(formatted_threads)} threads."
        )
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error processing Instagram Inbox HTML with unstructured",
            exc_info=True,
        )
        return f"Error processing Instagram Inbox HTML with unstructured: {e}"
