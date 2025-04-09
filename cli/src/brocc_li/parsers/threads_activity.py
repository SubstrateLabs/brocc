from typing import List, Optional

from unstructured.documents.elements import Element
from unstructured.partition.html import partition_html

from brocc_li.utils.logger import logger


def partition_threads_activity_html(html: str, debug: bool = False) -> List[Element]:
    """Partitions Threads activity HTML using unstructured and applies basic filtering."""
    try:
        if debug:
            logger.debug("Starting HTML partitioning for Threads activity...")

        elements = partition_html(
            text=html,
            # Add any relevant partition_html arguments if needed, e.g.:
            # strategy="hi_res", # If dealing with complex layouts, might be useful later
            # hi_res_model_name="yolox", # Example model
            # languages=["eng"], # Specify language if known
            # include_page_breaks=False,
            # chunking_strategy="by_title", # Maybe useful later
            # max_characters=1500, # Default chunking settings
            # new_after_n_chars=1200,
            # combine_text_under_n_chars=200,
        )

        if debug:
            logger.debug(f"Initial partition yielded {len(elements)} elements.")
            # for i, element in enumerate(elements):
            #     logger.debug(f"  Element {i}: {type(element).__name__} - {str(element)[:100]}...")

        # --- Basic Filtering (Keep minimal for now) ---
        # We will add more filtering later based on debug output
        filtered_elements = []
        for element in elements:
            element_text = str(element).strip()
            if not element_text:
                if debug:
                    logger.debug("Filtering empty element")
                continue

            # Add very basic noise filtering if obvious patterns emerge early
            # Example (adjust based on actual HTML):
            # if element_text.lower() in ["notifications", "search", "profile"]:
            #     if debug:
            #         logger.debug(f"Filtering potential nav element: {element_text}")
            #     continue

            filtered_elements.append(element)

        if debug:
            logger.debug(f"{len(filtered_elements)} elements remain after basic filtering.")
            # for i, element in enumerate(filtered_elements):
            #     logger.debug(f"  Filtered Element {i}: {type(element).__name__} - {str(element)[:100]}...")

        return filtered_elements

    except Exception as e:
        logger.error("Error during Threads activity HTML partitioning", exc_info=True)
        return []  # Return empty list on error


def threads_activity_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Converts Threads activity HTML content to Markdown format.

    Args:
        html: The HTML content as a string.
        debug: If True, enables detailed debug logging.

    Returns:
        A string containing the Markdown representation of the Threads activity,
        or None if an error occurs or no content is found.
    """
    try:
        # Use the specific partitioning function
        elements = partition_threads_activity_html(html, debug=debug)

        if not elements:
            logger.warning("No elements found after partitioning Threads activity HTML.")
            return "<!-- No elements found after partitioning -->"

        if debug:
            logger.debug(f"Processing {len(elements)} elements for Markdown conversion.")

        # --- Group elements by activity item ---
        activity_items = []
        current_item_elements = []

        # Skip the first element if it's just "Activity"
        start_index = 1 if elements and str(elements[0]).strip().lower() == "activity" else 0

        for i, element in enumerate(elements[start_index:], start=start_index):
            element_text = str(element).strip()

            # Detect start of a new item based on profile picture text
            if "'s profile picture" in element_text and current_item_elements:
                if debug:
                    logger.debug(f"Detected new activity item start at index {i}: {element_text}")
                activity_items.append(current_item_elements)
                current_item_elements = [element]  # Start new item with the profile pic
            else:
                current_item_elements.append(element)

        # Add the last item
        if current_item_elements:
            activity_items.append(current_item_elements)

        if debug:
            logger.debug(f"Grouped elements into {len(activity_items)} activity items.")

        # --- Markdown Conversion ---
        markdown_blocks = []
        for item_idx, item_elements in enumerate(activity_items):
            if not item_elements:
                continue

            if debug:
                logger.debug(
                    f"Processing activity item {item_idx} with {len(item_elements)} elements."
                )

            # Extract key info: Username, timestamp, action, content, stats
            username = "Unknown User"
            timestamp = ""
            action_text = ""
            content = []
            stats = []
            profile_pic_skipped = False

            for elem_idx, element in enumerate(item_elements):
                element_text = str(element).strip()
                if not element_text:
                    continue

                if debug:
                    logger.debug(f"  Item {item_idx}, Elem {elem_idx}: {element_text[:80]}...")

                # 1. Profile picture - usually first element
                if "'s profile picture" in element_text and not profile_pic_skipped:
                    # Extract username if possible, might be in the next element too
                    extracted_user = element_text.replace("'s profile picture", "").strip()
                    if extracted_user:  # Basic check
                        username = extracted_user
                    if debug:
                        logger.debug(f"    Found profile pic, potential username: {username}")
                    profile_pic_skipped = True  # Only process the first profile pic line per item
                    continue

                # 2. Username - often follows profile picture
                if (
                    elem_idx == 1
                    and not timestamp
                    and not action_text
                    and username == "Unknown User"
                ):
                    # If the first element wasn't the profile pic OR username extraction failed,
                    # assume the second element is the username if it looks like one.
                    # Basic check: no spaces, maybe contains _ or .
                    if " " not in element_text and (
                        "_" in element_text or "." in element_text or element_text.isalnum()
                    ):
                        username = element_text
                        if debug:
                            logger.debug(f"    Assuming element {elem_idx} is username: {username}")
                        continue  # Move to next element

                # 3. Timestamp - usually short, ends with h, d, w, m, y
                if (
                    len(element_text) <= 5
                    and element_text[-1] in "hdwmy"
                    and element_text[:-1].isdigit()
                ):
                    timestamp = element_text
                    if debug:
                        logger.debug(f"    Found timestamp: {timestamp}")
                    continue

                # 4. Action Text - e.g., "Started a thread", "Followed you", "Liked your post"
                action_phrases = [
                    "started a thread",
                    "posted their first thread",
                    "followed you",
                    "liked your",
                    "replied to",
                    "mentioned you",
                    "picked for you",
                ]
                if any(phrase in element_text.lower() for phrase in action_phrases):
                    action_text = element_text
                    if debug:
                        logger.debug(f"    Found action text: {action_text}")
                    continue

                # 5. Stats - Numbers (possibly with K/M), could be likes, replies, etc.
                # Crude check: primarily digits, maybe with K/M/B suffix or commas
                stat_text = element_text.replace(",", "").replace(".", "")
                is_stat = False
                if stat_text.endswith(("K", "M", "B")) and stat_text[:-1].isdigit():
                    is_stat = True
                elif stat_text.isdigit():
                    is_stat = True

                if is_stat:
                    stats.append(element_text)
                    if debug:
                        logger.debug(f"    Found potential stat: {element_text}")
                    continue

                # 6. Content - Everything else
                # Skip redundant username mentions if we already have it
                if element_text != username:
                    content.append(element_text)
                    if debug:
                        logger.debug(f"    Adding to content: {element_text[:80]}...")

            # --- Assemble Markdown for the item ---
            item_markdown = []
            # Heading: Action by User
            heading = f"### {action_text or 'Activity'} by {username}"
            item_markdown.append(heading)

            # Metadata bullets
            if timestamp:
                item_markdown.append(f"*   Timestamp: {timestamp}")
            # Add more metadata if needed, e.g. if action_text was generic:
            # if action_text and action_text != "Activity":
            #    item_markdown.append(f"*   Action: {action_text}")

            # Content
            if content:
                item_markdown.append(
                    "\n" + "\n".join(content)
                )  # Add a newline before content block

            # Stats
            if stats:
                item_markdown.append("\n*   Stats: " + ", ".join(stats))

            if item_markdown:  # Only add if we generated something
                markdown_blocks.append("\n".join(item_markdown))

        # Join all blocks with triple newlines
        markdown = "\n\n\n".join(markdown_blocks)

        if not markdown.strip():
            logger.warning("unstructured parsing resulted in empty markdown after processing.")
            return "<!-- unstructured parsing completed, but resulted in empty output -->"

        logger.info("Threads activity HTML to markdown conversion completed successfully.")
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error processing Threads activity HTML with unstructured",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error processing Threads activity HTML with unstructured: {e}"
