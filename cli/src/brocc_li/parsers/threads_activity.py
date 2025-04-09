from typing import List, Optional

from unstructured.documents.elements import Element
from unstructured.partition.html import partition_html

from brocc_li.parsers.threads_utils import (
    clean_username,
    is_profile_picture,
    is_timestamp,
)
from brocc_li.utils.logger import logger


def partition_threads_activity_html(html: str, debug: bool = False) -> List[Element]:
    """Partitions Threads activity HTML using unstructured and applies basic filtering."""
    try:
        if debug:
            logger.debug("Starting HTML partitioning for Threads activity...")

        elements = partition_html(text=html)

        if debug:
            logger.debug(f"Initial partition yielded {len(elements)} elements.")

        # --- Basic Filtering (Keep minimal for now) ---
        filtered_elements = []
        for element in elements:
            element_text = str(element).strip()
            if not element_text:
                if debug:
                    logger.debug("Filtering empty element")
                continue

            filtered_elements.append(element)

        if debug:
            logger.debug(f"{len(filtered_elements)} elements remain after basic filtering.")

        return filtered_elements

    except Exception:
        logger.error("Error during Threads activity HTML partitioning", exc_info=True)
        return []  # Return empty list on error


def threads_activity_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
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
            if is_profile_picture(element) and current_item_elements:
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
                if is_profile_picture(element) and not profile_pic_skipped:
                    # Extract username if possible, might be in the next element too
                    extracted_user = clean_username(element_text)
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
                if is_timestamp(element, debug=debug):
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

            # Format username as a link (https://www.threads.net/@username)
            username_link = f"[{username}](https://www.threads.net/@{username})"

            # Heading: Action by User with username as a link
            heading = f"### {action_text or 'Activity'} by {username_link}"
            item_markdown.append(heading)

            # Content - Deduplicated
            unique_content_lines = []
            seen_content = set()
            if content:
                # Deduplicate based on the first N characters to handle minor variations
                # and ignore very short lines that are likely fragments
                dedup_length = 50  # Consider first 50 chars for uniqueness
                min_length = 10  # Ignore lines shorter than 10 chars

                for line in content:
                    trimmed_line = line.strip()
                    if len(trimmed_line) < min_length:
                        continue
                    # Check based on a prefix to catch element splitting
                    line_prefix = trimmed_line[:dedup_length]
                    if line_prefix not in seen_content:
                        unique_content_lines.append(trimmed_line)
                        seen_content.add(line_prefix)
                        if debug:
                            logger.debug(f"    Adding unique content line: {trimmed_line[:80]}...")
                    elif debug:
                        logger.debug(f"    Skipping duplicate content line: {trimmed_line[:80]}...")

            if unique_content_lines:
                item_markdown.append("")  # Add an empty line after heading
                item_markdown.append("\n".join(unique_content_lines))

            # Metrics section - Includes timestamp and stats
            metrics = []

            # Add timestamp as a metric
            if timestamp:
                metrics.append(f"*   {timestamp}")

            # Stats - Deduplicated
            unique_stats = []
            seen_stats = set()
            if stats:
                for stat in stats:
                    if stat not in seen_stats:
                        unique_stats.append(stat)
                        seen_stats.add(stat)

                # Add stats as metrics
                if len(unique_stats) >= 2:
                    metrics.append(f"*   {unique_stats[0]} likes")
                    metrics.append(f"*   {unique_stats[1]} replies")

            # Add metrics if we have any
            if metrics:
                item_markdown.append("")  # Add an empty line before metrics
                item_markdown.extend(metrics)

            # Only add the block if it has more than just the header and timestamp
            # Avoid adding items that only have a header/timestamp (like disco_stevo's)
            if len(item_markdown) > 1:  # Header always present
                if unique_content_lines or unique_stats:  # Ensure there's *some* detail
                    markdown_blocks.append("\n".join(item_markdown))
                elif debug:
                    logger.debug(
                        f"Skipping item {item_idx} (username: {username}) as it lacks unique content/stats beyond header/timestamp."
                    )
            elif debug:
                logger.debug(f"Skipping item {item_idx} (username: {username}) as it seems empty.")

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
