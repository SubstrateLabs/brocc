from typing import List, Optional, Set

from unstructured.documents.elements import Element, Image
from unstructured.partition.html import partition_html

from brocc_li.parsers.linkedin_utils import extract_profile_url, format_profile_header
from brocc_li.parsers.unstructured_utils import is_element_noisy
from brocc_li.utils.logger import logger

# Extended noise patterns based on the debug output
SEARCH_CONNECTIONS_NOISE_PATTERNS = [
    "Sign in",
    "Home",
    "My Network",
    "Jobs",
    "Messaging",
    "Notifications",
    "LinkedIn Corporation",
    "Status is",  # Catches status indicators like "Status is offline"
    "Search with Recruiter",
    "additional advanced filters",
    "Are these results helpful",
    "Your feedback helps",
    "Page 1 of",
    "degree connection",  # Catches "2nd degree connection" patterns
    "Currently on the page",
    "search result pages",
]


def _clean_name(text: str) -> str:
    """Clean up name text by removing 'View X's profile' text"""
    # Handle cases where View is directly attached to the name
    if "View" in text:
        # Split on "View" and take the first part
        name = text.split("View")[0].strip()
        # Sometimes this leaves an extra space at the end
        return name.rstrip()
    return text


def _is_profile_name(text: str) -> bool:
    """Check if the element looks like a profile name"""
    # More robust profile name detection
    text_lower = text.lower()
    return ("view" in text_lower and "profile" in text_lower) or (
        "view" in text_lower and "'s" in text_lower
    )


def _debug_element_metadata(element: Element, prefix: str = "") -> None:
    """Helper to debug print element metadata"""
    metadata = getattr(element, "metadata", None)
    if metadata:
        logger.debug(f"{prefix}Element metadata:")
        # Print link-related metadata
        link_texts = getattr(metadata, "link_texts", [])
        link_urls = getattr(metadata, "link_urls", [])
        if link_texts or link_urls:
            logger.debug(f"{prefix}  Links:")
            for i, (text, url) in enumerate(zip(link_texts or [], link_urls or [], strict=False)):
                logger.debug(f"{prefix}    {i + 1}. Text: {text}")
                logger.debug(f"{prefix}       URL: {url}")

        # Print other potentially useful metadata
        for attr in ["tag", "tag_type", "tag_attrs", "text_as_html"]:
            value = getattr(metadata, attr, None)
            if value:
                logger.debug(f"{prefix}  {attr}: {value}")


def linkedin_search_connections_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Parses the HTML content of LinkedIn Search Connections into Markdown.

    This parser converts the unstructured output to markdown format
    with improved formatting for person profiles.
    """
    logger.info("Starting LinkedIn Search Connections HTML processing...")
    try:
        # Partition the HTML using unstructured
        elements: List[Element] = partition_html(text=html)
        logger.info(f"unstructured found {len(elements)} raw elements.")

        if debug:
            logger.debug("Raw LinkedIn Search Connections elements:")
            for i, element in enumerate(elements[:20]):  # Limit to first 20 elements
                element_text = str(element).strip()
                logger.debug(
                    f"  Raw Element {i + 1}: {type(element).__name__} - {element_text[:50]}..."
                )
                _debug_element_metadata(element, prefix="    ")
            if len(elements) > 20:
                logger.debug(f"  ... and {len(elements) - 20} more elements")

        if not elements:
            logger.warning("unstructured.partition_html returned no elements.")
            return "<!-- unstructured found no elements -->"

        # --- Filter Noise --- #
        filtered_elements: List[Element] = []
        seen_texts: Set[str] = set()  # Track texts we've already seen to prevent dupes
        seen_images: Set[str] = set()  # Track image alt texts

        for element in elements:
            # Skip empty elements
            element_text = str(element).strip()
            if not element_text:
                continue

            # Handle images specially
            if isinstance(element, Image):
                # Only keep one image per person (avoid duplicates)
                img_alt = element.metadata.alt_text if hasattr(element.metadata, "alt_text") else ""
                if img_alt and img_alt not in seen_images:
                    seen_images.add(img_alt)
                    filtered_elements.append(element)
                    if debug:
                        logger.debug(f"Keeping image with alt text: {img_alt}")
                        _debug_element_metadata(element, prefix="    ")
                continue

            # Skip duplicate elements
            if element_text in seen_texts:
                if debug:
                    logger.debug(f"Skipping duplicate element: {element_text[:30]}...")
                continue

            # Check against noise patterns
            if is_element_noisy(element, SEARCH_CONNECTIONS_NOISE_PATTERNS, debug=debug):
                continue

            filtered_elements.append(element)
            seen_texts.add(element_text)

        logger.info(f"Kept {len(filtered_elements)} elements after filtering noise.")

        if debug:
            logger.debug("Filtered LinkedIn Search Connections elements:")
            for i, element in enumerate(filtered_elements[:20]):  # Limit to first 20
                element_type = type(element).__name__
                element_text = str(element).strip()
                logger.debug(f"  Filtered Element {i + 1}: {element_type} - {element_text[:50]}...")
                # Print metadata for elements that might contain profile links
                if _is_profile_name(element_text):
                    logger.debug("  Profile element metadata:")
                    _debug_element_metadata(element, prefix="    ")
            if len(filtered_elements) > 20:
                logger.debug(f"  ... and {len(filtered_elements) - 20} more elements")

        if not filtered_elements:
            logger.warning("No elements remaining after filtering noise.")
            return "<!-- No elements remaining after filtering noise -->"

        # --- Simplified grouping approach --- #
        # Assuming profiles appear in order
        profiles = []
        markdown_parts = []  # Initialize markdown parts list early

        # Add a title
        markdown_parts.append("# LinkedIn Search Connections")

        # Find profile name elements (they contain "View X's profile")
        name_indices = []
        for i, element in enumerate(filtered_elements):
            element_text = str(element).strip()
            # Debug profile name detection
            if debug and _is_profile_name(element_text):
                logger.debug(f"Potential profile name candidate: {element_text}")

            if _is_profile_name(element_text):
                name_indices.append(i)
                if debug:
                    logger.debug(f"Found profile name at index {i}: {element_text}")

        if debug:
            logger.debug(f"Found {len(name_indices)} potential profile names")

        # Process based on name indices
        if name_indices:
            # For each name, collect following elements until next name
            for i, name_idx in enumerate(name_indices):
                # Define end boundary (next name or end of list)
                end_idx = (
                    name_indices[i + 1] if i + 1 < len(name_indices) else len(filtered_elements)
                )

                # Extract name and remove "View X's profile" suffix
                name_element = filtered_elements[name_idx]
                name_text = str(name_element).strip()
                clean_name = _clean_name(name_text)

                # Skip if we somehow got an empty name after cleaning
                if not clean_name:
                    continue

                # Get profile URL using the shared utility function
                profile_url = extract_profile_url(name_element)

                # Create profile with name, url and details
                profile = {"name": clean_name, "url": profile_url, "details": []}

                # Add all elements between this name and next name as details
                for j in range(name_idx + 1, end_idx):
                    if j < len(filtered_elements):  # Safety check
                        detail_text = str(filtered_elements[j]).strip()
                        # Skip if this detail looks like a profile name
                        if detail_text and not _is_profile_name(detail_text):
                            profile["details"].append(detail_text)

                profiles.append(profile)

            # Format each profile
            for profile in profiles:
                # Use the shared utility function to format headers
                markdown_parts.append(
                    format_profile_header(profile["name"], profile["url"], level=2)
                )

                # Short details first (likely job titles, locations)
                short_details = [d for d in profile["details"] if len(d) < 40]
                for detail in short_details:
                    markdown_parts.append(f"- {detail}")

                # Then longer details (descriptions, connections lists)
                long_details = [d for d in profile["details"] if len(d) >= 40]
                for detail in long_details:
                    markdown_parts.append(f"- {detail}")

                # Add a separator between profiles
                markdown_parts.append("")
        else:
            # Fallback to a simpler format if we couldn't detect profiles
            # Group elements heuristically - assume name, job, location pattern
            current_group = []
            groups = []

            for _, element in enumerate(filtered_elements):
                text = str(element).strip()
                if not text or len(text) <= 3:
                    continue

                # If this looks like a name (contains "View" and is not too long)
                if _is_profile_name(text):
                    # Save previous group if it exists
                    if current_group:
                        groups.append(current_group)

                    # Start a new group with this cleaned name
                    current_group = [_clean_name(text)]
                else:
                    # Add to current group
                    if current_group:
                        current_group.append(text)
                    else:
                        # If no current group, start one with cleaned text
                        current_group = [text]

            # Don't forget the last group
            if current_group:
                groups.append(current_group)

            # Format each group
            for group in groups:
                if not group:
                    continue

                # First element is treated as the name
                name = _clean_name(group[0])
                if not name:  # Skip if we somehow got an empty name
                    continue

                markdown_parts.append(f"## {name}")

                # Rest are details
                for detail in group[1:]:
                    if not _is_profile_name(detail):  # Skip any profile name text in details
                        markdown_parts.append(f"- {detail}")

                # Add a separator between profiles
                markdown_parts.append("")

        # If we somehow have no structured groups, just output the elements as a list
        if len(markdown_parts) <= 1:
            for element in filtered_elements:
                text = str(element).strip()
                if text and len(text) > 3:
                    markdown_parts.append(f"- {text}")

        result = "\n".join(markdown_parts).strip()

        logger.info("Successfully processed LinkedIn Search Connections HTML.")
        if debug:
            logger.debug(f"Final markdown structure contains {len(result.splitlines())} lines")

        return result

    except Exception as e:
        logger.error(
            "Error processing LinkedIn Search Connections HTML with unstructured",
            exc_info=True,
        )
        return f"Error processing LinkedIn Search Connections HTML: {e}"
