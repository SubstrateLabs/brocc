import re
from typing import List, Optional, Tuple

from unstructured.documents.elements import Element, Image, ListItem, NarrativeText, Text, Title
from unstructured.partition.html import partition_html

from brocc_li.utils.logger import logger

# List of noisy text patterns to filter out
NOISE_PATTERNS = [
    "Media player modal window",
    "Visit profile for",
    "Drop your files here",
    "Drag your files here",
    "Discover free and easy ways",
    "Hi Ben, are you hiring?",
    "Write article",
    "feed updates",
    "Visible to anyone on or off LinkedIn",
    "Media is loading",
    "Loaded:",
    "Stream Type LIVE",
    "Remaining time",
    # "Follow", # Removed - check handled more specifically in _is_noisy
    # Add more patterns as needed
]

# Regex for playback speeds like 0.5x, 1x, 1.25x etc.
PLAYBACK_SPEED_REGEX = re.compile(r"^\d+(\.\d+)?x(,\s*selected)?$")
# Regex for timestamps like 0:56
TIMESTAMP_REGEX = re.compile(r"^\d+:\d{2}$")
# Regex for short time indicators like 23h, 1d, 2w (with optional space)
TIME_INDICATOR_REGEX = re.compile(r"^\d{1,2}\s?[hdwmy]$")


def _is_noisy(element_text: str, debug: bool = False) -> bool:
    """Check if element text matches any known noise patterns."""
    text_strip = element_text.strip()
    text_lower = text_strip.lower()

    if not text_lower:
        if debug:
            logger.debug("Noisy check: empty text")
        return True

    # Specific check for standalone "Follow" button text
    if text_lower == "follow":
        if debug:
            logger.debug("Noisy check: matched exact text 'follow'")
        return True

    for pattern in NOISE_PATTERNS:
        # Use text_strip here for case-sensitive patterns if needed in future
        if pattern.lower() in text_lower:
            if debug:
                logger.debug(
                    f"Noisy check: matched pattern '{pattern}' in '{element_text[:50]}...'"
                )
            return True

    if PLAYBACK_SPEED_REGEX.match(text_lower):
        if debug:
            logger.debug(f"Noisy check: matched PLAYBACK_SPEED_REGEX: '{element_text}'")
        return True
    if TIMESTAMP_REGEX.match(text_lower):
        if debug:
            logger.debug(f"Noisy check: matched TIMESTAMP_REGEX: '{element_text}'")
        return True
    if TIME_INDICATOR_REGEX.match(text_lower):
        if debug:
            logger.debug(f"Noisy check: matched time indicator regex: '{element_text}'")
        return True

    if text_lower == "..." or text_lower.isdigit():
        if debug:
            logger.debug(f"Noisy check: matched '...' or isdigit: '{element_text}'")
        return True

    return False


def _find_first_link(block_elements: List[Element]) -> Optional[Tuple[str, str, Element]]:
    """Find the first element with a likely profile/company link in its metadata."""
    for element in block_elements:
        metadata = getattr(element, "metadata", None)
        if not metadata:
            continue

        link_texts = getattr(metadata, "link_texts", None)
        link_urls = getattr(metadata, "link_urls", None)
        element_text = str(element).strip()

        if (
            link_texts
            and link_urls
            and isinstance(link_texts, list)
            and isinstance(link_urls, list)
        ):
            if link_texts[0] and link_urls[0]:  # Ensure they are not empty
                url = link_urls[0]
                text = link_texts[0].strip()

                # Prioritize profile/company links
                if "linkedin.com/in/" in url or "linkedin.com/company/" in url:
                    # Clean common noise from text
                    if text.endswith("'s profile photo"):
                        text = text[: -len("'s profile photo")]
                    elif text.endswith("'s profile photo"):
                        text = text[: -len("'s profile photo")]
                    text = (
                        text.replace("\u2022 1st", "")
                        .replace("\u2022 2nd", "")
                        .replace("\u2022 3rd+", "")
                        .strip()
                    )

                    # Attempt to deduplicate repeated names (e.g., "Name Name Title")
                    words = text.split()
                    if len(words) > 1 and words[0] == words[1]:
                        mid = len(text) // 2
                        first_half = text[:mid].strip()
                        second_half = text[mid:].strip()
                        if first_half == second_half:
                            text = first_half
                        # Consider element_text only if it *doesn't* contain the likely dirtier link_text
                        elif (
                            text not in element_text
                            and element_text.startswith(text)
                            and len(element_text) > len(text)
                        ):
                            text = element_text  # Less likely useful now?

                    # If cleaning results in empty text, skip
                    if not text:
                        continue

                    return text.strip(), url, element  # Ensure final strip
    return None


def _check_block_type(block_elements: List[Element]) -> Optional[str]:
    """Check if block text indicates a repost or comment."""
    for element in block_elements:
        if isinstance(element, (Text, NarrativeText)):
            text_lower = str(element).lower()
            if "reposted this" in text_lower:
                return "(Repost)"
            if "commented on this" in text_lower:
                return "(Comment)"
    return None


def linkedin_feed_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Parses LinkedIn feed HTML using unstructured, filters noise, groups by post markers,
    extracts profile links for headers, marks reposts/comments, attempts to dedupe text,
    and converts it to Markdown.

    Args:
        html: The HTML content of the LinkedIn feed page.
        debug: Enable verbose logging for debugging unstructured elements.

    Returns:
        A string containing the formatted Markdown, or None if parsing fails.
    """
    try:
        logger.info("Starting LinkedIn HTML parsing with unstructured...")
        elements: List[Element] = partition_html(text=html)
        logger.info(f"unstructured found {len(elements)} raw elements.")

        if not elements:
            logger.warning("unstructured.partition_html returned no elements.")
            return "<!-- unstructured found no elements -->"

        # --- Filter Noise --- #
        filtered_elements: List[Element] = []
        for _i, element in enumerate(elements):
            element_text = str(element)
            # Pass debug flag to _is_noisy
            if _is_noisy(element_text, debug=debug) or element_text == "...see more":
                # Logging now happens inside _is_noisy if debug is True
                # if debug: logger.debug(f"Filtering noisy element {i+1}: {element_text[:100]}...")
                continue
            filtered_elements.append(element)
        logger.info(f"Kept {len(filtered_elements)} elements after filtering.")

        if not filtered_elements:
            logger.warning("No elements remaining after filtering noise.")
            return "<!-- No elements remaining after filtering noise -->"

        # --- Group by Post Marker --- #
        post_blocks_elements: List[List[Element]] = []
        current_block_elements: List[Element] = []

        for element in filtered_elements:
            element_text = str(element)
            is_post_marker = isinstance(element, Title) and element_text.startswith(
                "Feed post number"
            )

            if is_post_marker and current_block_elements:
                post_blocks_elements.append(current_block_elements)
                current_block_elements = []  # Reset for the new post
            elif not is_post_marker:
                current_block_elements.append(element)

        if current_block_elements:
            post_blocks_elements.append(current_block_elements)
        logger.info(f"Grouped elements into {len(post_blocks_elements)} potential post blocks.")

        # --- Format Blocks with Headers --- #
        final_markdown_blocks = []
        for block_idx, block_elements in enumerate(post_blocks_elements):
            block_content_lines = []
            header = f"### Post {block_idx + 1}"  # Default header
            header_element = None
            block_type_marker = _check_block_type(block_elements) or ""

            link_info = _find_first_link(block_elements)
            if link_info:
                link_text, link_url, header_element = link_info
                header = f"### [{link_text}]({link_url}) {block_type_marker}".strip()
                if debug:
                    logger.debug(f"Using header for block {block_idx + 1}: {header}")
            elif debug:
                logger.debug(
                    f"No suitable profile link found for block {block_idx + 1}, using default header."
                )

            for element in block_elements:
                if element is header_element:
                    continue

                element_text = str(element).strip()
                formatted_line = ""

                # Deduplication check is now handled *after* formatting
                is_text_element = isinstance(element, (NarrativeText, Text))

                if isinstance(element, Title):
                    if header_element and element_text == getattr(header_element, "text", None):
                        continue
                elif is_text_element:
                    formatted_line = element_text
                elif isinstance(element, ListItem):
                    if header_element and element_text == getattr(header_element, "text", None):
                        continue
                    formatted_line = f"- {element_text}"
                elif isinstance(element, Image):
                    alt_text = element.text or "Image"
                    alt_text = alt_text.replace("'s profile photo", "").strip()
                    img_url = element.metadata.image_url
                    if img_url:
                        if header_element and alt_text == getattr(header_element, "text", None):
                            if debug:
                                logger.debug(
                                    f"Skipping image with alt text same as header: {alt_text}"
                                )
                            continue
                        formatted_line = f"![{alt_text}]({img_url})"
                    else:
                        if debug:
                            logger.debug(f"Skipping Image element with no URL: {alt_text}")
                        continue

                if formatted_line:
                    # De-duplication: Replace last line if current line is longer and starts with it
                    if (
                        is_text_element
                        and block_content_lines
                        and formatted_line.startswith(block_content_lines[-1])
                        and len(formatted_line) > len(block_content_lines[-1])
                    ):
                        if debug:
                            logger.debug(
                                f"Replacing previous line with longer text: {formatted_line[:100]}..."
                            )
                        block_content_lines[-1] = formatted_line  # Replace last line
                    elif block_content_lines and formatted_line == block_content_lines[-1]:
                        if debug:
                            logger.debug(
                                f"Skipping exact duplicate line: {formatted_line[:100]}..."
                            )
                        continue  # Skip exact duplicates too
                    else:
                        block_content_lines.append(formatted_line)

            if block_content_lines:
                final_block_md = header + "\n\n" + "\n\n".join(block_content_lines)
                final_markdown_blocks.append(final_block_md)
            elif debug:
                logger.debug(
                    f"Block {block_idx + 1} resulted in no content after formatting, skipping."
                )

        # Join the final blocks with triple newlines
        markdown = "\n\n\n".join(final_markdown_blocks)

        if not markdown.strip():
            logger.warning(
                "unstructured parsing resulted in empty markdown after all processing steps."
            )
            return "<!-- unstructured parsing completed, but resulted in empty output -->"

        logger.info("unstructured parsing, filtering, grouping, and header formatting successful.")
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error processing LinkedIn HTML with unstructured",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error processing LinkedIn HTML with unstructured: {e}"
