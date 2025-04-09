import re
from typing import Optional, Tuple

from bs4 import Tag

from brocc_li.utils.logger import logger

# TODO: Refactor utils if they stabilize


def extract_text_based_user_info(
    text: str, debug: bool = False
) -> Tuple[Optional[str], Optional[str]]:
    """Finds the first '@' symbol and assumes the word before it is the name
    and the word after it (including '@') is the handle.
    Needs adaptation for Bluesky structure.
    """
    logger.debug(f"Attempting to extract user info from text: '{text[:100]}...'" if debug else None)
    handle_match = re.search(r"(@[a-zA-Z0-9.-]+\.[a-zA-Z]+)", text)
    if handle_match:
        handle = handle_match.group(1)
        # Find the position of the handle
        handle_pos = handle_match.start()
        # Assume name is the text immediately before the handle, clean it
        name = text[:handle_pos].replace("\u202a", "").replace("\u202c", "").strip()
        # Clean up potential artifacts if name is just handle repeated
        if name.endswith(handle):
            name = name[: -len(handle)].strip()
        # If name is empty after stripping handle, maybe it was just the handle
        if not name:
            name = None  # Or maybe set name = handle? Needs review.

        logger.debug(f"Extracted handle: {handle}, name: {name}" if debug else None)
        return name, handle
    else:
        # Fallback: maybe only name is present?
        # Or maybe the structure is different. This is a basic fallback.
        logger.warning(
            f"Could not find handle pattern in text: '{text[:50]}...'" if debug else None
        )
        # Attempt to extract name based on common patterns or just return text as name?
        # For now, assume the first significant part is name if no handle.
        lines = text.split("\n")
        first_significant_line = next((line.strip() for line in lines if line.strip()), None)
        if first_significant_line:
            logger.debug(
                f"No handle found, using first line as name: {first_significant_line}"
                if debug
                else None
            )
            return first_significant_line, None

    logger.debug("Could not extract name/handle reliably." if debug else None)
    return None, None


def format_user_markdown_header(
    name: Optional[str],
    handle: Optional[str],
    handle_url: Optional[str] = None,
    platform: str = "Bluesky",
    debug: bool = False,
) -> str:
    """Formats the user name and handle into a markdown header.
    Uses handle for the link if URL is provided.
    """
    if debug:
        logger.debug(f"Formatting header for Name: {name}, Handle: {handle}, URL: {handle_url}")
    parts = []
    display_name = name if name else handle
    if not display_name:
        return "### [Unknown User]"

    # Clean display name for link text (take first line, strip whitespace)
    link_text = display_name.split("\n")[0].strip()

    if not link_text:
        return "### [Invalid User Profile Link]"  # Avoid empty links

    if handle_url:
        parts.append(f"### [{link_text}](https://bsky.app{handle_url})")
    else:
        parts.append(f"### {link_text}")  # No link if no URL

    if handle:
        parts.append(f"({handle})")

    header = " ".join(parts)
    if debug:
        logger.debug(f"Formatted header: {header}")
    return header


def process_html_with_parser(
    html: str,
    element_selector: str,
    processor_function,  # Takes (element: Tag, debug: bool) -> Optional[str]
    join_str: str = "\n\n",
    debug: bool = False,
) -> Optional[str]:
    """Generic HTML processor using BeautifulSoup.
    Selects elements, processes each with processor_function, joins results.
    """
    from bs4 import BeautifulSoup  # Local import

    if debug:
        logger.debug(f"Processing HTML (length: {len(html)}) with selector '{element_selector}'")

    try:
        soup = BeautifulSoup(html, "html.parser")
        if debug:
            logger.debug(
                f"HTML parsed successfully. Searching for elements with selector '{element_selector}'..."
            )

        elements = soup.select(element_selector)
        if debug:
            logger.debug(f"Found {len(elements)} elements matching selector '{element_selector}'.")
            if not elements:
                logger.warning(
                    f"No elements found for selector '{element_selector}'. Check selector and HTML structure."
                )
                # Log a snippet of the HTML for context
                html_snippet = html[:500] + ("..." if len(html) > 500 else "")
                logger.debug(f"HTML start: {html_snippet}")

        if not elements:
            return None  # Or maybe an empty string? None indicates potential failure.

        markdown_parts = []
        for i, element in enumerate(elements):
            if debug:
                element_html_snippet = str(element)[:200] + (
                    "..." if len(str(element)) > 200 else ""
                )
                logger.debug(f"--- Processing element {i + 1}/{len(elements)} ---")
                logger.debug(f"Element HTML: {element_html_snippet}")

            processed_element = processor_function(element, debug=debug)
            if processed_element:
                markdown_parts.append(processed_element)
                if debug:
                    logger.debug(f"Element {i + 1} processed successfully.")
            elif debug:
                logger.debug(f"Element {i + 1} skipped (processor returned None).")

        if debug:
            logger.debug(f"Finished processing elements. Joining {len(markdown_parts)} parts.")

        return join_str.join(markdown_parts)

    except Exception as e:
        logger.error(f"Error processing HTML: {e}", exc_info=True)
        return f"Error converting HTML: {e}"


# End copied utils


def extract_bsky_follower_info(
    element: Tag, debug: bool = False
) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts name and handle from a Bluesky follower element (<a> tag).
    Assumes specific nested div structure.
    """
    name = None
    handle = None

    if debug:
        logger.debug(f"Extracting Bsky info from element: {str(element)[:150]}...")

    # Structural approach: Find direct div children of the <a> tag
    direct_divs = element.select(":scope > div")
    info_container = None

    if len(direct_divs) >= 2:
        # Assume the second direct div contains name/handle
        info_container = direct_divs[1]
        if debug:
            logger.debug("Found potential info container structurally (second direct div).")
    elif debug:
        logger.warning(
            f"Expected at least 2 direct divs for info container, found {len(direct_divs)}. Will rely on fallback."
        )

    if isinstance(info_container, Tag):  # Check it's a Tag before using select_one
        if debug:
            logger.debug(f"Processing info container: {str(info_container)[:100]}...")

        # Name is the first div inside the container
        name_element = info_container.select_one("div:nth-of-type(1)")
        if name_element:
            name = name_element.get_text(strip=True)
            # Clean unicode marks
            name = name.replace("\u202a", "").replace("\u202c", "").strip()
            if debug:
                logger.debug(f"Extracted name: '{name}'")
        elif debug:
            logger.warning("Could not find name element within info container.")

        # Handle is the second div inside the container
        handle_element = info_container.select_one("div:nth-of-type(2)")
        if handle_element:
            handle = handle_element.get_text(strip=True)
            # Clean the '\u202a' LTR mark sometimes present
            handle = handle.replace("\u202a", "").replace("\u202c", "").strip()
            if debug:
                logger.debug(f"Extracted handle: '{handle}'")
        elif debug:
            logger.warning("Could not find handle element within info container.")
    elif info_container:  # It exists but is not a Tag
        if debug:
            logger.warning(
                f"Info container found via sibling logic was not a Tag: {type(info_container)}"
            )
    else:  # It is None
        if debug:
            logger.warning("Did not find a suitable info container structurally.")

    # Fallback using the text-based extraction if structure parsing fails
    if not name and not handle:
        if debug:
            logger.debug("Structural parsing failed, falling back to text-based extraction.")
        element_text = element.get_text(strip=True, separator="\n")
        name, handle = extract_text_based_user_info(element_text, debug)

    return name, handle


def extract_bsky_follower_bio(element: Tag, debug: bool = False) -> str:
    """
    Extracts the bio from a Bluesky follower element (<a> tag).
    Assumes it's in the last relevant div.
    """
    bio = ""
    if debug:
        logger.debug("Extracting Bsky bio...")

    # Structural approach: Find direct div children
    direct_divs = element.select(":scope > div")
    bio_element = None

    if len(direct_divs) >= 3:
        # Assume the third direct div contains the bio
        bio_element = direct_divs[2]
        if debug:
            logger.debug("Found potential bio container structurally (third direct div).")
    elif debug:
        logger.debug(
            f"Expected at least 3 direct divs for bio container, found {len(direct_divs)}. Assuming no bio."
        )

    if bio_element:
        bio = bio_element.get_text(strip=True)
        if debug:
            logger.debug(f"Extracted potential bio structurally: '{bio[:100]}...'")
    elif debug:
        pass  # Already logged lack of element above

    if not bio and debug:
        logger.debug("Could not find bio via structural analysis.")
        # Could add a text-based fallback here if needed

    return bio


def format_bsky_follower_markdown(
    name: Optional[str], handle: Optional[str], bio: str, debug: bool = False
) -> str:
    """Format Bluesky follower information into markdown.
    Uses the generic header formatter.
    """
    markdown_parts = []
    # Extract just the handle part like 'handle.bsky.social' from '@handle.bsky.social'
    # Ensure handle is cleaned before stripping @
    cleaned_handle = handle.replace("\u202a", "").replace("\u202c", "").strip() if handle else None
    plain_handle = cleaned_handle.lstrip("@") if cleaned_handle else None
    handle_url = f"/profile/{plain_handle}" if plain_handle else None

    # Pass debug flag down
    header = format_user_markdown_header(
        name, cleaned_handle, handle_url=handle_url, platform="Bluesky", debug=debug
    )
    markdown_parts.append(header)

    if bio:
        markdown_parts.append(bio)

    result = "\n\n".join(markdown_parts)
    if debug:
        logger.debug(f"Formatted Markdown:\n---START---\n{result}\n---END---")
    return result


def process_bsky_follower_element(element: Tag, debug: bool = False) -> Optional[str]:
    """
    Processes a single Bluesky follower element (an <a> tag) and converts it to markdown.
    Used as the processor function for process_html_with_parser.
    """
    if debug:
        logger.debug(f"Processing Bluesky follower element: {str(element)[:150]}...")

    name, handle = extract_bsky_follower_info(element, debug=debug)

    if not name and not handle:
        if debug:
            logger.warning("Skipping element: Could not extract name or handle.")
        return None

    bio = extract_bsky_follower_bio(element, debug=debug)

    # Format to markdown
    markdown = format_bsky_follower_markdown(name, handle, bio, debug=debug)
    return markdown


def bsky_followers_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Convert Bluesky followers HTML to markdown.

    Args:
        html: Raw HTML of Bluesky followers page
        debug: Enable debug output

    Returns:
        Markdown string or None if parsing failed
    """
    if debug:
        logger.debug("--- Starting Bluesky HTML to Markdown Conversion ---")

    # The selector needs to target the container for each follower.
    # Based on the provided HTML, this seems to be the <a> tag wrapping each user entry.
    # Let's refine selector: Direct children 'a' tags of the list container seems appropriate.
    # The list container seems to be the FOURTH div inside the main screen div.
    # Selector: Target <a> tags starting with /profile/ that are children of the FOURTH nested div
    selector = 'div[data-testid="profileFollowersScreen"] > div > div > div > a[href^="/profile/"]'

    if debug:
        logger.debug(f"Using element selector: {selector}")

    markdown_output = process_html_with_parser(
        html=html,
        element_selector=selector,
        processor_function=process_bsky_follower_element,
        join_str="\n\n",
        debug=debug,
    )

    if debug:
        logger.debug("--- Finished Bluesky HTML to Markdown Conversion ---")

    return markdown_output
