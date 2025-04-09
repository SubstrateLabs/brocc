from typing import Dict, List, Optional, Set

from unstructured.documents.elements import Element, Image, NarrativeText, Title
from unstructured.partition.html import partition_html

from brocc_li.parsers.linkedin_utils import extract_profile_url, format_profile_header
from brocc_li.parsers.unstructured_utils import is_element_noisy
from brocc_li.utils.logger import logger

# Minimal initial noise patterns - we'll refine this after seeing debug logs
FOLLOWERS_NOISE_PATTERNS = [
    "Sign in",
    "Home",
    "My Network",
    "Jobs",
    "Messaging",
    "Notifications",
    "LinkedIn Corporation",
    "Followers",
    "Following",
    "Filter followers",
    "Search followers",
    "All filters",
    "People also viewed",  # Usually noise on followers page
    "Premium",
    "people are following you",  # Filter out follower count
]

# Patterns that indicate a section separator rather than a profile
SECTION_SEPARATOR_PATTERNS = [
    "others you know followed",
    "you both know",
    "mutual connections",
    "also follow",
    "recently followed",
]


def _debug_element_details(element: Element, prefix: str = "") -> None:
    """Helper to debug print element details"""
    metadata = getattr(element, "metadata", None)
    logger.debug(f"{prefix}  Type: {type(element).__name__}")
    if metadata:
        # Print link-related metadata if present
        link_texts = getattr(metadata, "link_texts", [])
        link_urls = getattr(metadata, "link_urls", [])
        if link_texts or link_urls:
            logger.debug(f"{prefix}  Links:")
            for i, (text, url) in enumerate(zip(link_texts or [], link_urls or [], strict=False)):
                logger.debug(f"{prefix}    {i + 1}. Text: {text}")
                logger.debug(f"{prefix}       URL: {url}")

        # Print other potentially useful metadata like tag
        tag = getattr(metadata, "tag", None)
        if tag:
            logger.debug(f"{prefix}  Tag: {tag}")


def _is_section_separator(text: str) -> bool:
    """Check if text is likely a section separator rather than a profile"""
    text_lower = text.lower()
    for pattern in SECTION_SEPARATOR_PATTERNS:
        if pattern in text_lower:
            return True
    return False


def _extract_profile_info(elements: List[Element], debug: bool = False) -> List[Dict]:
    """Extract structured profile information from filtered elements"""
    profiles = []
    current_profile = None
    section_title = None

    # Iterate through elements to group by profile
    for _i, element in enumerate(elements):
        element_text = str(element).strip()
        if not element_text:
            continue

        # Check if this is a profile name with link
        # We don't need the metadata directly, we're using extract_profile_url instead
        profile_url = extract_profile_url(element)

        # Section separators create new sections
        if _is_section_separator(element_text) and isinstance(element, NarrativeText):
            section_title = element_text
            if debug:
                logger.debug(f"Found section separator: {element_text}")
            continue

        # Profile names typically have LinkedIn profile links
        if profile_url and "linkedin.com/in/" in profile_url:
            # Save previous profile if exists
            if current_profile:
                profiles.append(current_profile)

            # Start new profile
            current_profile = {
                "name": element_text,
                "url": profile_url,
                "description": [],
                "section": section_title,
            }
            if debug:
                logger.debug(f"New profile: {element_text} ({profile_url})")

        # Otherwise add as description to current profile
        elif current_profile is not None:
            # Skip duplicate name entries (LinkedIn often has image and text for same name)
            if element_text != current_profile["name"]:
                current_profile["description"].append(element_text)
                if debug:
                    logger.debug(f"Added description to {current_profile['name']}: {element_text}")

    # Don't forget the last profile
    if current_profile:
        profiles.append(current_profile)

    return profiles


def linkedin_followers_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Parses the HTML content of a LinkedIn Followers page into structured Markdown.

    This version groups followers with their descriptions and properly formats links.
    """
    logger.info("Starting LinkedIn Followers HTML processing...")
    try:
        # Partition the HTML using unstructured
        elements: List[Element] = partition_html(text=html)
        logger.info(f"unstructured found {len(elements)} raw elements.")

        if debug:
            logger.debug("Raw LinkedIn Followers elements:")
            for i, element in enumerate(elements[:30]):  # Limit debug output
                element_text = str(element).strip()
                logger.debug(
                    f"  Raw Element {i + 1}: {element_text[:70]}{'...' if len(element_text) > 70 else ''}"
                )
                _debug_element_details(element, prefix="    ")
            if len(elements) > 30:
                logger.debug(f"  ... and {len(elements) - 30} more elements")

        if not elements:
            logger.warning("unstructured.partition_html returned no elements.")
            return "<!-- unstructured found no elements -->"

        # --- Minimal Noise Filtering --- #
        filtered_elements: List[Element] = []
        seen_texts: Set[str] = set()  # Basic duplicate prevention

        # Extract page title first (usually at the top)
        page_title = None
        if elements and isinstance(elements[0], Title):
            page_title = str(elements[0]).strip()

        for element in elements:
            element_text = str(element).strip()
            if not element_text:
                continue

            # Simple duplicate check
            if element_text in seen_texts:
                if debug:
                    logger.debug(f"Skipping duplicate: {element_text[:30]}...")
                continue

            # Skip images for now in this basic version
            if isinstance(element, Image):
                if debug:
                    img_alt = getattr(element.metadata, "alt_text", "No alt text")
                    logger.debug(f"Skipping image element. Alt text: {img_alt}")
                continue

            # Check against noise patterns
            if is_element_noisy(element, FOLLOWERS_NOISE_PATTERNS, debug=debug):
                continue

            filtered_elements.append(element)
            seen_texts.add(element_text)

        logger.info(f"Kept {len(filtered_elements)} elements after initial filtering.")

        if debug:
            logger.debug("Filtered LinkedIn Followers elements:")
            for i, element in enumerate(filtered_elements[:30]):  # Limit debug output
                element_text = str(element).strip()
                logger.debug(
                    f"  Filtered Element {i + 1}: {element_text[:70]}{'...' if len(element_text) > 70 else ''}"
                )
                _debug_element_details(element, prefix="    ")
            if len(filtered_elements) > 30:
                logger.debug(f"  ... and {len(filtered_elements) - 30} more elements")

        if not filtered_elements:
            logger.warning("No elements remaining after filtering noise.")
            return "<!-- No elements remaining after filtering noise -->"

        # --- Extract structured profile information --- #
        profiles = _extract_profile_info(filtered_elements, debug=debug)

        # --- Convert to Markdown --- #
        markdown_parts = ["# LinkedIn Followers"]

        # Add page title if found and different from default
        if page_title and page_title != "LinkedIn Followers":
            markdown_parts.append(f"## {page_title}")

        # Group by sections if present
        current_section = None

        for profile in profiles:
            # Add section headers when they change
            if profile["section"] != current_section and profile["section"]:
                current_section = profile["section"]
                markdown_parts.append(f"### {current_section}")

            # Add profile with link using the common utility
            markdown_parts.append(format_profile_header(profile["name"], profile["url"], level=2))

            # Add descriptions as bullet points
            for desc in profile["description"]:
                markdown_parts.append(f"- {desc}")

            # Add a blank line between profiles for readability
            markdown_parts.append("")

        result = "\n".join(markdown_parts).strip()

        logger.info("Successfully processed LinkedIn Followers HTML with structured output.")
        if debug:
            logger.debug(f"Final markdown structure contains {len(result.splitlines())} lines")

        return result

    except Exception as e:
        logger.error(
            "Error processing LinkedIn Followers HTML with unstructured",
            exc_info=True,
        )
        return f"Error processing LinkedIn Followers HTML: {e}"
