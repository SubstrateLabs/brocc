from typing import List, Optional

from unstructured.documents.elements import Element, NarrativeText, Text, Title
from unstructured.partition.html import partition_html

from brocc_li.parsers.substack_utils import (
    parse_substack_relative_time,
)
from brocc_li.utils.logger import logger


def substack_activity_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        logger.info("Starting Substack activity HTML parsing with unstructured...")
        elements: List[Element] = partition_html(text=html)
        logger.info(f"unstructured found {len(elements)} raw elements.")

        if not elements:
            logger.warning("unstructured.partition_html returned no elements.")
            return "<!-- unstructured found no elements -->"

        # --- Minimal Filtering --- #
        filtered_elements: List[Element] = []
        for i, element in enumerate(elements):
            element_text = str(element)

            # Minimal filtering initially - just empty/whitespace elements
            if not element_text.strip():
                if debug:
                    logger.debug(f"Filtering empty element {i + 1}")
                continue

            filtered_elements.append(element)
            if debug:
                logger.debug(
                    f"Element {i + 1}: {element.__class__.__name__} - {element_text[:100]}..."
                )

        logger.info(f"Kept {len(filtered_elements)} elements after minimal filtering.")

        if not filtered_elements:
            logger.warning("No elements remaining after filtering.")
            return "<!-- No elements remaining after filtering -->"

        # --- Process Activity Items --- #
        markdown_blocks = []
        activities = []

        # Skip the main "Activity" title if present
        start_idx = 0
        if (
            filtered_elements
            and isinstance(filtered_elements[0], Title)
            and "Activity" in str(filtered_elements[0])
        ):
            start_idx = 1

        # First pass: identify potential user names and activity items
        i = start_idx
        current_activity = None

        while i < len(filtered_elements):
            element = filtered_elements[i]
            element_text = str(element).strip()

            # Check if this could be a username (short text that's followed by an action)
            is_username = (
                isinstance(element, Text)
                and len(element_text) < 50
                and i + 1 < len(filtered_elements)
                and isinstance(filtered_elements[i + 1], NarrativeText)
                and not element_text.startswith("+")  # Skip "+5" type elements
                and not element_text.startswith("and")  # Skip "and" connectors
                and not any(
                    x in element_text.lower() for x in ["subscribed", "followed", "liked"]
                )  # Skip action texts
            )

            # Common action verbs that indicate the previous element is not a username
            action_words = ["subscribed", "followed", "liked", "is on", "others"]

            # Check if this is an action (indicates previous text might not be a username)
            is_action = isinstance(element, NarrativeText) and any(
                word in element_text.lower() for word in action_words
            )

            if is_username:
                # Start a new activity item
                if current_activity is not None:
                    activities.append(current_activity)

                current_activity = {"username": element_text, "actions": [], "description": ""}
                i += 1
            elif current_activity is not None:
                # This is part of the current activity
                if is_action:
                    current_activity["actions"].append(element_text)
                elif isinstance(element, (NarrativeText, Text)) and element_text:
                    # This could be a description or bio
                    if not any(word in element_text.lower() for word in action_words):
                        if current_activity["description"]:
                            current_activity["description"] += "\n\n" + element_text
                        else:
                            current_activity["description"] = element_text
                i += 1
            else:
                # Skip elements that don't fit our pattern
                i += 1

        # Add the last activity
        if current_activity is not None:
            activities.append(current_activity)

        # Format each activity
        for activity in activities:
            username = activity["username"]
            actions = activity["actions"]
            description = activity["description"]

            lines = [f"### {username}"]

            # Format actions
            for action in actions:
                # Use our utility function to parse time
                action_text, timestamp = parse_substack_relative_time(action)

                # Format the action line
                formatted_action = action_text.strip()
                if timestamp:
                    formatted_action += f" ({timestamp.strip()})"

                lines.append(f"**{formatted_action}**")

            # Add description if present
            if description:
                lines.append(description)

            markdown_blocks.append("\n\n".join(lines))

            if debug:
                logger.debug(f"Formatted activity for user: {username} with {len(actions)} actions")

        markdown = "\n\n".join(markdown_blocks)

        if not markdown.strip():
            logger.warning("Parsing resulted in empty markdown.")
            return "<!-- Parsing completed, but resulted in empty output -->"

        logger.info("Substack activity parsing successful.")
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error processing Substack activity HTML with unstructured",
            exc_info=True,
        )
        return f"Error processing Substack activity HTML with unstructured: {e}"


def format_activity_item(elements: List[Element], debug: bool = False) -> str:
    """Format a list of elements into a markdown activity item."""
    if not elements:
        return ""

    # Extract user name (first element)
    user_name = str(elements[0]).strip()

    # Initialize variables to collect activity data
    action = ""
    timestamp = ""
    description = ""

    # Process the activity details
    for i, element in enumerate(elements[1:], 1):
        if isinstance(element, NarrativeText):
            element_text = str(element).strip()

            # First narrative is usually the action with timestamp
            if i == 1:
                # Try to extract timestamp using our utility function
                action, timestamp = parse_substack_relative_time(element_text)
            # Additional narratives are descriptions
            elif element_text:
                if description:
                    description += "\n\n" + element_text
                else:
                    description = element_text

        # Handle Text elements that could be additional descriptions
        elif i > 1 and isinstance(element, Text) and str(element).strip():
            element_text = str(element).strip()
            if element_text and element_text != user_name:
                if description:
                    description += "\n\n" + element_text
                else:
                    description = element_text

    # Format markdown
    markdown_lines = []

    # Add user header
    markdown_lines.append(f"### {user_name}")

    # Add action and timestamp
    if action or timestamp:
        meta_text = action.strip()
        if timestamp:
            if meta_text:
                meta_text += f" ({timestamp.strip()})"
            else:
                meta_text = timestamp.strip()

        markdown_lines.append(f"**{meta_text}**")

    # Add description
    if description:
        markdown_lines.append(description)

    if debug:
        logger.debug(f"Formatted activity item: {user_name} - {action} {timestamp}")

    return "\n\n".join(markdown_lines)
