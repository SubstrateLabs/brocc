from typing import List, Optional

from unstructured.documents.elements import Element
from unstructured.partition.html import partition_html

from brocc_li.parsers.unstructured_utils import is_element_noisy
from brocc_li.utils.logger import logger

# Extended noise patterns based on the debug output
MESSAGES_NOISE_PATTERNS = [
    "Sign in",
    "Home",
    "My Network",
    "Jobs",
    "Messaging",
    "Notifications",
    "LinkedIn Corporation",
    "Jump to active conversation details",
    "Press return to go to conversation details",
    "Active conversation",
    "Status is",  # Catches all status indicators
    "new notification",
    "View",  # Catches "View X's profile"
    "Search messages",
    "Focused",
    "Unread",
    "InMail",
    "Starred",
    "New messages in Other",  # Add this to prevent infinite loop
    "+ more",  # Filter out "+ more" messages
    "Write a message",  # Filter out message input prompts
    "Conversation List",  # Remove redundant header
]


def _clean_duplicate_dates(text: str) -> str:
    """Clean up repeated date patterns like 'Apr 8 Apr 8'"""
    # First, handle the obvious duplicates pattern "Apr 8 Apr 8"
    parts = text.split()
    if len(parts) >= 4:
        # Check for exact duplicates like "Apr 8 Apr 8"
        if parts[0] == parts[2] and parts[1] == parts[3]:
            return f"{parts[0]} {parts[1]}"

        # Check for date patterns like "Apr 8 - Apr 8"
        if parts[0] == parts[2] and parts[1] == parts[3] and "-" in parts:
            return f"{parts[0]} {parts[1]}"

    # Return a cleaner version for month day patterns
    if len(parts) >= 2:
        month_prefixes = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]
        if parts[0] in month_prefixes and parts[1].replace(",", "").isdigit():
            # Just return "Apr 8" from longer strings
            return f"{parts[0]} {parts[1]}"

    return text


def _is_date_element(text: str) -> bool:
    """Check if an element is likely a date marker"""
    # Strip any trailing punctuation
    text = text.rstrip(",:;.")

    parts = text.split()
    if not parts:
        return False

    # Check month prefix
    month_prefixes = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    if parts[0] in month_prefixes:
        # Format like "Apr 8"
        if len(parts) >= 2 and parts[1].replace(",", "").isdigit():
            return True

    # Also detect formats with full year
    if len(parts) >= 3 and parts[0] in month_prefixes and len(parts[2]) == 4 and parts[2].isdigit():
        return True

    return False


def _extract_date(elements: List[Element], current_idx: int) -> Optional[str]:
    """Look ahead to find a date element near the current one"""
    # Look at the next few elements for a date
    for i in range(current_idx + 1, min(current_idx + 3, len(elements))):
        text = str(elements[i]).strip()
        if _is_date_element(text):
            return _clean_duplicate_dates(text)

    # Also look at a couple previous elements
    for i in range(max(0, current_idx - 2), current_idx):
        text = str(elements[i]).strip()
        if _is_date_element(text):
            return _clean_duplicate_dates(text)

    return None


def _clean_message_text(text: str) -> str:
    """Clean up message text by removing duplicate lines that appear in long messages"""
    if len(text) < 100:
        return text

    lines = text.strip().split("\n")
    if len(lines) <= 1:
        return text

    # Many messages have the same content repeated with increasing length
    # Keep only the longest version of each prefix
    seen_starts = {}

    for line in lines:
        # Get the first 40 chars as prefix for comparison
        prefix = line[:40]

        # Find similar lines we've seen before
        found_match = False
        for start in seen_starts:
            # If this line starts the same as a line we've seen
            if prefix.startswith(start) or start.startswith(prefix):
                # Keep the longer version
                if len(line) > len(seen_starts[start]):
                    seen_starts[start] = line
                found_match = True
                break

        if not found_match:
            seen_starts[prefix] = line

    # Convert back to text
    return "\n".join(seen_starts.values())


def linkedin_messages_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Parses the HTML content of LinkedIn Messages into Markdown.

    This parser converts the unstructured output to markdown,
    with improved formatting and noise filtering.
    """
    logger.info("Starting LinkedIn Messages HTML processing...")
    try:
        # Partition the HTML using unstructured
        elements: List[Element] = partition_html(text=html)
        logger.info(f"unstructured found {len(elements)} raw elements.")

        if debug:
            logger.debug("Raw LinkedIn Messages elements:")
            for i, element in enumerate(elements[:20]):  # Limit to first 20 elements
                logger.debug(
                    f"  Raw Element {i + 1}: {type(element).__name__} - {str(element)[:50]}..."
                )
            if len(elements) > 20:
                logger.debug(f"  ... and {len(elements) - 20} more elements")

        if not elements:
            logger.warning("unstructured.partition_html returned no elements.")
            return "<!-- unstructured found no elements -->"

        # --- Filter Noise --- #
        filtered_elements: List[Element] = []
        seen_texts = set()  # Track texts we've already seen to prevent dupes

        for element in elements:
            # Skip empty elements
            element_text = str(element).strip()
            if not element_text:
                continue

            # Clean up duplicate dates immediately
            if _is_date_element(element_text):
                element_text = _clean_duplicate_dates(element_text)

            # Skip duplicate elements
            if element_text in seen_texts:
                if debug:
                    logger.debug(f"Skipping duplicate element: {element_text[:30]}...")
                continue

            # Check against noise patterns
            if is_element_noisy(element, MESSAGES_NOISE_PATTERNS, debug=debug):
                continue

            filtered_elements.append(element)
            seen_texts.add(element_text)

        logger.info(f"Kept {len(filtered_elements)} elements after filtering noise.")

        if debug:
            logger.debug("Filtered LinkedIn Messages elements:")
            for i, element in enumerate(filtered_elements[:20]):  # Limit to first 20
                element_text = str(element).strip()
                logger.debug(
                    f"  Filtered Element {i + 1}: {type(element).__name__} - {element_text[:50]}..."
                )
            if len(filtered_elements) > 20:
                logger.debug(f"  ... and {len(filtered_elements) - 20} more elements")

        if not filtered_elements:
            logger.warning("No elements remaining after filtering noise.")
            return "<!-- No elements remaining after filtering noise -->"

        # --- Convert to Markdown (Improved Heading Structure) --- #
        markdown_parts = []

        # Add a title
        markdown_parts.append("# LinkedIn Messages\n")

        # First pass: gather names and dates
        conversation_data = {}  # name -> date mapping
        message_data = {}  # name -> message content

        # Collect all dates to avoid duplicating them
        processed_dates = set()

        # Process all elements to capture names with their dates
        for i, element in enumerate(filtered_elements):
            element_text = str(element).strip()

            # Skip very short elements
            if len(element_text) <= 3:
                continue

            # Handle dates separately to avoid duplicate headers
            if _is_date_element(element_text):
                clean_date = _clean_duplicate_dates(element_text)
                processed_dates.add(clean_date)
                continue

            # Look for person names (shorter elements that look like names)
            if len(element_text) < 40 and " " in element_text:
                words = element_text.split()
                # Check if this looks like a name (at least 2 words with first capitalized)
                if (
                    len(words) >= 2
                    and words[0][0].isupper()
                    and not element_text.startswith("Ben <")
                ):
                    # This might be a person's name
                    name = element_text

                    # Try to find a date associated with this name
                    date = _extract_date(filtered_elements, i)
                    if date:
                        conversation_data[name] = date
                        processed_dates.add(date)  # Mark this date as processed
                    else:
                        conversation_data[name] = None

                    # Initialize message content collection
                    if name not in message_data:
                        message_data[name] = []

                    continue

            # Check if this is a message from the current person
            if len(element_text) > 50:
                # Find which person this message belongs to
                for name in conversation_data:
                    # Simple heuristic: assign to most recently seen name
                    if name not in message_data or not message_data[name]:
                        message_data[name] = [element_text]
                        break
                    if (
                        len(message_data) > 0
                        and len(message_data[list(message_data.keys())[-1]]) == 0
                    ):
                        message_data[list(message_data.keys())[-1]] = [element_text]
                        break

        # Second pass: generate the markdown with combined headers
        for name, date in conversation_data.items():
            # Create combined header
            if date:
                header = f"## {name} - {date}"
            else:
                header = f"## {name}"
            markdown_parts.append(header)

            # Add messages for this person
            if name in message_data and message_data[name]:
                # Clean up duplicate content in messages
                cleaned_messages = _clean_message_text("\n".join(message_data[name]))

                # Format based on message length
                if len(cleaned_messages) > 100:
                    markdown_parts.append(f"```\n{cleaned_messages}\n```")
                else:
                    markdown_parts.append(cleaned_messages)

        # Third pass: add any orphaned elements (not assigned to a person)
        for element in filtered_elements:
            element_text = str(element).strip()

            # Skip very short meaningless elements and ones we've already processed
            if len(element_text) <= 5:
                continue

            # Skip person names and dates we've already handled
            if element_text in conversation_data:
                continue

            # Skip dates we've already processed
            if (
                _is_date_element(element_text)
                and _clean_duplicate_dates(element_text) in processed_dates
            ):
                continue

            # Skip elements that are part of messages we've already handled
            message_found = False
            for msgs in message_data.values():
                if msgs and any(element_text in msg for msg in msgs):
                    message_found = True
                    break
            if message_found:
                continue

            # Add this as a standalone element with appropriate formatting
            if _is_date_element(element_text):
                # Format dates nicely
                cleaned_date = _clean_duplicate_dates(element_text)
                markdown_parts.append(f"### {cleaned_date}")
            elif "sent the following message" in element_text:
                # Format message notifications
                markdown_parts.append(f"### {element_text}")
            elif element_text in [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]:
                # Format days of week
                markdown_parts.append(f"### {element_text}")
            else:
                # Default formatting
                markdown_parts.append(f"- {element_text}")

        # Join all parts with double newlines for better readability
        result_md = "\n\n".join(markdown_parts)

        # Remove any duplicate adjacent lines
        lines = result_md.split("\n")
        unique_lines = []
        prev_line = None
        for line in lines:
            if line != prev_line:
                unique_lines.append(line)
            prev_line = line
        result_md = "\n".join(unique_lines)

        logger.info("Successfully processed LinkedIn Messages HTML.")
        if debug:
            logger.debug(f"Final markdown structure contains {len(result_md.splitlines())} lines")

        return result_md.strip()

    except Exception as e:
        logger.error(
            "Error processing LinkedIn Messages HTML with unstructured",
            exc_info=True,
        )
        return f"Error processing LinkedIn Messages HTML: {e}"
