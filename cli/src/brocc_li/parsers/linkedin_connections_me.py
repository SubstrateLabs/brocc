from typing import List, Optional

from unstructured.documents.elements import Element, NarrativeText, Text
from unstructured.partition.html import partition_html

from brocc_li.parsers.unstructured_utils import is_element_noisy
from brocc_li.utils.logger import logger

CONNECTIONS_NOISE_PATTERNS = [
    "Sign in",
    "Home",
    "My Network",
    "Jobs",
    "Messaging",
    "Notifications",
    "Me",  # Catches standalone "Me" and "Message" due to partial match
    "Work",
    "Try Premium for free",
    "Search",  # Catches "Search with filters"
    "Filter",
    "Sort by",
    "Add connections",
    "See all",
    "View profile",  # Often redundant on connection items
    # Footer/Misc Noise
    "About",
    "Accessibility",
    "Help Center",
    "Privacy & Terms",
    "Ad Choices",
    "Advertising",
    "Business Services",
    "Get the LinkedIn app",
    "More",
    "LinkedIn Corporation",  # Match copyright
    # Add more specific patterns as identified from real HTML
]


# --- Helper to identify potential connection name ---
# Very basic heuristic: Short text, likely capitalized words, not ending with '...'
# and not matching known noisy titles. Needs refinement.
def _is_potential_name(text: str) -> bool:
    if not text or len(text) > 50 or text.endswith("..."):
        return False
    # Avoid matching common titles/sections mistaken for names
    if text.lower() in ["recently added", "connections", "sort by:", "search with filters"]:
        return False
    # Check if it looks like a name (e.g., capitalized words)
    return all(word[0].isupper() or not word[0].isalpha() for word in text.split())


def linkedin_connections_me_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Parses the HTML content of a LinkedIn Connections or 'Me' page into Markdown.

    This is a simpler parser than linkedin_company, primarily focused on extracting
    text content and basic structure without deep semantic understanding.
    """
    logger.info("Starting LinkedIn Connections/Me HTML processing...")
    try:
        # Partition the HTML using unstructured
        elements: List[Element] = partition_html(text=html)
        logger.info(f"unstructured found {len(elements)} raw elements.")

        if debug:
            logger.debug("Raw Connections/Me elements:")
            for i, element in enumerate(elements):
                logger.debug(
                    f"  Raw Element {i + 1}: {type(element).__name__} - {str(element)[:100]}..."
                )

        if not elements:
            logger.warning("unstructured.partition_html returned no elements.")
            return "<!-- unstructured found no elements -->"

        # --- Filter Noise --- #
        filtered_elements: List[Element] = []
        for element in elements:
            # Use a generic noise filter or define specific patterns
            # Pass the specific patterns list now
            if is_element_noisy(element, CONNECTIONS_NOISE_PATTERNS, debug=debug):
                if debug:
                    logger.debug(f"Filtered out noisy element: {str(element)[:50]}...")
                continue
            filtered_elements.append(element)

        logger.info(f"Kept {len(filtered_elements)} elements after filtering noise.")

        if debug:
            logger.debug("Filtered Connections/Me elements:")
            for i, element in enumerate(filtered_elements):
                logger.debug(
                    f"  Filtered Element {i + 1}: {type(element).__name__} - {str(element)[:100]}..."
                )

        if not filtered_elements:
            logger.warning("No elements remaining after filtering noise.")
            return "<!-- No elements remaining after filtering noise -->"

        # --- Convert to Markdown (Structured Approach) --- #
        markdown_parts = []
        i = 0
        while i < len(filtered_elements):
            element = filtered_elements[i]
            text = str(element).strip()

            # Check for standalone info like 'X Connections' or 'Recently added'
            if i == 0 and "Connections" in text:
                markdown_parts.append(f"# {text}\n")
                i += 1
                continue
            if i == 1 and "Recently added" in text:  # Based on fixture output
                markdown_parts.append(f"## {text}\n")
                i += 1
                continue

            # Attempt to identify a connection block: Name, Title, Date
            # Heuristic: Look for a potential name (Text), followed by title (Text), then date (NarrativeText)
            is_name = isinstance(element, Text) and _is_potential_name(text)
            has_next_two_elements = i + 2 < len(filtered_elements)

            if is_name and has_next_two_elements:
                next_element = filtered_elements[i + 1]
                next_text = str(next_element).strip()
                next_next_element = filtered_elements[i + 2]
                next_next_text = str(next_next_element).strip()

                # Check if the following elements roughly match the expected pattern
                is_title = isinstance(next_element, Text) and next_text  # Title can be long
                is_date = (
                    isinstance(next_next_element, NarrativeText)
                    and "connected on" in next_next_text.lower()
                )

                if is_title and is_date:
                    # Found a connection block
                    markdown_parts.append(f"### {text}")  # Name
                    markdown_parts.append(f"- {next_text}")  # Title
                    markdown_parts.append(f"- {next_next_text}")  # Connection Date
                    if debug:
                        logger.debug(f"Processed connection: {text}")
                    i += 3  # Move past the 3 elements we just processed
                    continue
                elif is_title and not is_date:
                    # Handle cases like Morgante Pell with only Name + Description
                    # Check if the *next* element might be a name, indicating end of this block
                    is_next_title_a_name = (
                        i + 2 < len(filtered_elements)
                        and isinstance(filtered_elements[i + 2], Text)
                        and _is_potential_name(str(filtered_elements[i + 2]).strip())
                    )

                    if "connected on" not in next_text.lower() and is_next_title_a_name:
                        markdown_parts.append(f"### {text}")  # Name
                        markdown_parts.append(f"- {next_text}")  # Description
                        if debug:
                            logger.debug(f"Processed connection (Name/Desc only): {text}")
                        i += 2  # Move past Name and Description
                        continue

            # If it doesn't fit the connection pattern, just add the text (or skip?)
            # For now, let's skip elements that don't fit the pattern to reduce noise
            if debug:
                logger.debug(
                    f"Skipping element (doesn't fit pattern): {type(element).__name__} - {text[:50]}..."
                )
            i += 1

        # Join parts, adding extra newline between connection blocks
        result_md = "\n\n".join(markdown_parts)

        logger.info("Successfully processed LinkedIn Connections/Me HTML.")
        if debug:
            logger.debug(f"Final markdown structure contains {len(result_md.splitlines())} lines")

        return result_md.strip()

    except Exception as e:
        logger.error(
            "Error processing LinkedIn Connections/Me HTML with unstructured",
            exc_info=True,
        )
        return f"Error processing LinkedIn Connections/Me HTML: {e}"
