from typing import Dict, Optional, cast

from bs4 import BeautifulSoup, Tag

from brocc_li.utils.logger import logger

from .twitter_utils import (
    extract_text_based_user_info,
    format_user_markdown_header,
)


def process_message_element(container: Tag, debug: bool = False) -> Optional[str]:
    """Process a single message element and convert to markdown."""
    # Extract message info from the container
    message_info = _extract_message_info(container, debug=debug)

    # Skip if no name or handle was found
    if not message_info.get("name") and not message_info.get("handle"):
        if debug:
            logger.debug("No name or handle found for this message")
        return None

    # Format the message to markdown
    return _format_message_markdown(message_info)


def twitter_inbox_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        soup = BeautifulSoup(html, "html.parser")
        if debug:
            logger.debug("Starting Twitter inbox HTML parsing")
            logger.debug(f"HTML length: {len(html)} characters")

            # Log the title to verify we're parsing the right page
            title = soup.title.text if soup.title else "No title found"
            logger.debug(f"Page title: '{title}'")

            # Log the first few divs to understand page structure
            logger.debug("First few divs in document:")
            for i, div in enumerate(soup.find_all("div", limit=5)):
                div = cast(Tag, div)
                div_id = div.get("id", "no-id")
                div_class = div.get("class", "no-class")
                logger.debug(f"  Div {i}: id='{div_id}', class='{div_class}'")

        output_blocks = []

        # Determine if this is a followers or following page
        header = soup.select_one("h1")
        if header:
            header_text = header.get_text(strip=True)
            if debug:
                logger.debug(f"Found header: '{header_text}'")
            # Skip the known useless header
            if header_text != "JavaScript is not available.":
                output_blocks.append(f"# {header_text}")
            elif debug:
                logger.debug(f"Skipping header: '{header_text}'")
        else:
            # Default header if we can't find one
            output_blocks.append("# Twitter Messages")
            if debug:
                logger.debug("No header found, using default")

                # Try to find other heading elements
                logger.debug("Looking for alternative headers:")
                for sel in ["h2", "h3", ".css-1qaijid", "[role='heading']"]:
                    alt_headers = soup.select(sel)
                    logger.debug(f"  Selector '{sel}' found {len(alt_headers)} elements")
                    for i, h in enumerate(alt_headers[:3]):  # Show first 3
                        logger.debug(f"    {i}: '{h.get_text(strip=True)}'")

        # Find all message containers
        message_containers = soup.select('div[data-testid="cellInnerDiv"]')

        if debug:
            logger.debug(f"Found {len(message_containers)} potential message containers")

            # Show details of first container
            if message_containers:
                logger.debug("First container details:")
                first_container = message_containers[0]
                logger.debug(f"  Tag name: {first_container.name}")
                logger.debug(f"  Attributes: {first_container.attrs}")

                # Show selectors for user info
                user_cells = first_container.select('div[data-testid="UserCell"]')
                logger.debug(f"  Contains {len(user_cells)} UserCell elements")

                user_names = first_container.select('div[data-testid="User-Name"]')
                logger.debug(f"  Contains {len(user_names)} User-Name elements")

                spans = first_container.find_all("span")
                logger.debug(f"  Contains {len(spans)} span elements")

                # Log all text content in the container
                text_content = first_container.get_text(strip=True)
                if len(text_content) > 200:
                    text_content = text_content[:200] + "..."
                logger.debug(f"  Text content: '{text_content}'")

        processed_messages = 0
        message_blocks = []

        for i, container in enumerate(message_containers):
            # Skip the first container if it's the "Message requests" header
            if i == 0 and "Message requests" in container.get_text():
                if debug:
                    logger.debug(f"Skipping container {i} (Message requests header)")
                continue

            markdown = process_message_element(container, debug=debug)
            if markdown:
                message_blocks.append(markdown)
                processed_messages += 1

        if debug:
            logger.debug(f"Successfully processed {processed_messages} messages")

        # Add header and then messages
        if message_blocks:
            output_blocks.extend(message_blocks)

        markdown = "\n\n".join(output_blocks)

        if not markdown:
            logger.warning("Inbox extraction resulted in empty markdown")
            return None

        logger.info("Twitter inbox conversion successful")
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error converting inbox HTML with BeautifulSoup",
            exc_info=True,
        )
        return f"Error converting inbox HTML with BeautifulSoup: {e}"


def _extract_message_info(container: Tag, debug: bool = False) -> Dict[str, Optional[str]]:
    """Extract information about a message from its container."""
    message_info: Dict[str, Optional[str]] = {
        "name": None,
        "handle": None,
        "message_preview": None,
        "timestamp": None,
    }

    try:
        # --- Name and Handle Extraction ---
        # Get text content to extract name/handle
        text = container.get_text(strip=True)
        name, handle = extract_text_based_user_info(text, debug=debug)
        message_info["name"] = name
        message_info["handle"] = handle

        # --- Timestamp Extraction ---
        time_element = container.select_one("time[datetime]")
        if time_element:
            message_info["timestamp"] = time_element.get_text(strip=True)
            if debug:
                logger.debug(f"Found timestamp: '{message_info['timestamp']}'")

        # --- Message Preview Extraction ---
        # Look for spans containing message text, excluding those used for name/handle/timestamp
        excluded_texts = {message_info["name"], message_info["handle"], message_info["timestamp"]}
        best_preview = None
        max_len = 0

        for span in container.select("span"):
            text = span.get_text(strip=True)
            # Skip if it's the name, handle, timestamp, or empty/short
            if text and text not in excluded_texts and len(text) > 2:
                # Prefer longer text as preview
                if len(text) > max_len:
                    best_preview = text
                    max_len = len(text)
                    if debug:
                        logger.debug(
                            f"Updating best preview: '{best_preview[:50]}...' (length: {max_len})"
                        )

        message_info["message_preview"] = best_preview
        if debug and best_preview:
            logger.debug(f"Final message preview selected: '{best_preview[:100]}...'")
        elif debug:
            logger.debug("No message preview found")

    except Exception as e:
        if debug:
            logger.error(f"Error extracting message info: {e}", exc_info=True)

    return message_info


def _format_message_markdown(message_info: Dict[str, Optional[str]]) -> str:
    """Format a message's information into markdown."""
    md_parts = []

    # Get user info
    name = message_info.get("name")
    handle = message_info.get("handle")
    timestamp = message_info.get("timestamp")

    # Use the shared header formatting function
    header = format_user_markdown_header(name, handle, timestamp)
    md_parts.append(header)

    # Add message preview if available
    preview = message_info.get("message_preview")
    if preview:
        # Indent preview for clarity
        md_parts.append(f"> {preview}")

    return "\n".join(md_parts)
