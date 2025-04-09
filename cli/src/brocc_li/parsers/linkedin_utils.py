import re
from typing import Any, Dict, List, Optional, Tuple

from unstructured.documents.elements import Element, Image, NarrativeText, Text, Title

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
    # "Follow", # Removed - check handled more specifically in is_noisy
    # Add more patterns as needed
]

# Regex for playback speeds like 0.5x, 1x, 1.25x etc.
PLAYBACK_SPEED_REGEX = re.compile(r"^\d+(\.\d+)?x(,\s*selected)?$")
# Regex for timestamps like 0:56
TIMESTAMP_REGEX = re.compile(r"^\d+:\d{2}$")
# Regex for short time indicators like 23h, 1d, 2w (with optional space)
TIME_INDICATOR_REGEX = re.compile(r"^\d{1,2}\s?[hdwmy]$")


def is_noisy(element_text: str, debug: bool = False) -> bool:
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


def find_first_link(
    block_elements: List[Element], debug: bool = False
) -> Optional[Tuple[str, str, Element]]:
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

                    if debug:
                        logger.debug(f"Found profile link: {text} -> {url}")

                    return text.strip(), url, element  # Ensure final strip

    if debug:
        logger.debug("No suitable profile links found in block elements")

    return None


def check_block_type(block_elements: List[Element], debug: bool = False) -> Optional[str]:
    """Check if block text indicates a repost or comment."""
    for element in block_elements:
        if isinstance(element, (Text, NarrativeText)):
            text_lower = str(element).lower()
            if "reposted this" in text_lower:
                if debug:
                    logger.debug(f"Detected repost: '{str(element)[:50]}...'")
                return "(Repost)"
            if "commented on this" in text_lower:
                if debug:
                    logger.debug(f"Detected comment: '{str(element)[:50]}...'")
                return "(Comment)"

    if debug:
        logger.debug("No specific block type (repost/comment) detected")

    return None


def extract_company_metadata(
    elements: List[Element],
    max_elements: int = 15,
    include_end_idx: bool = False,
    debug: bool = False,
) -> Any:
    """
    Generic company metadata extraction from LinkedIn HTML elements.

    Args:
        elements: List of unstructured elements
        max_elements: Maximum number of elements to check for metadata (default: 15)
        include_end_idx: Whether to return the index where metadata ends (for posts)
        debug: Whether to output debug logs

    Returns:
        Dict with metadata or Tuple of (Dict, int) if include_end_idx is True
    """
    metadata: Dict[str, Optional[str]] = {
        "name": None,
        "description": None,
        "logo_url": None,
        "industry": None,
        "location": None,
        "website": None,
        "followers": None,
        "employees": None,
        "company_size": None,
        "type": None,
        "founded": None,
        "specialties": None,
    }

    # Typically, company info is among the first elements
    max_metadata_idx = min(max_elements, len(elements))
    end_idx = 0

    for i, element in enumerate(elements[:max_metadata_idx]):
        text = str(element).strip()
        text_lower = text.lower()

        # Company name is likely a Title near the top
        if isinstance(element, Title) and not metadata["name"] and i < 3:
            metadata["name"] = text
            if debug:
                logger.debug(f"Found company name: {text}")

        # Logo is likely an Image with the company name in it
        elif isinstance(element, Image) and not metadata["logo_url"] and i < 3:
            if element.metadata and element.metadata.image_url:
                metadata["logo_url"] = element.metadata.image_url
                if debug:
                    logger.debug("Found company logo URL")

        # Description is usually a NarrativeText after the name/logo
        elif isinstance(element, NarrativeText) and not metadata["description"] and i < 10:
            if len(text) > 30:  # Likely a description if it's long enough
                metadata["description"] = text
                if debug:
                    logger.debug(f"Found company description: {text[:50]}...")

        # Website typically contains http/https or www
        elif (
            isinstance(element, Text)
            and not metadata["website"]
            and any(x in text_lower for x in ["http:", "https:", "www.", ".com"])
        ):
            # Clean up website text if it has a label
            website_text = text
            if "website" in text_lower:
                website_text = text.replace("Website", "").replace("website", "").strip()
            metadata["website"] = website_text
            if debug:
                logger.debug(f"Found website: {website_text}")

        # Industry and Location are typically short Text elements
        elif isinstance(element, Text):
            # Industry detection
            if not metadata["industry"]:
                if "industry" in text_lower:
                    metadata["industry"] = (
                        text.replace("Industry", "").replace("industry", "").strip()
                    )
                    if debug:
                        logger.debug(f"Found labeled industry: {metadata['industry']}")
                elif any(
                    keyword in text_lower
                    for keyword in [
                        "software",
                        "technology",
                        "marketing",
                        "finance",
                        "healthcare",
                        "consulting",
                        "services",
                        "media",
                    ]
                ):
                    metadata["industry"] = text
                    if debug:
                        logger.debug(f"Found industry: {text}")

            # Location detection
            elif not metadata["location"] and any(
                loc in text for loc in ["CA", "NY", "TX", "San", "New York", "Boston", "Location"]
            ):
                metadata["location"] = text
                if debug:
                    logger.debug(f"Found location: {text}")

            # Followers and employees count
            elif not metadata["followers"] and "followers" in text_lower:
                metadata["followers"] = text
                if debug:
                    logger.debug(f"Found followers: {text}")

            elif not metadata["employees"] and "employees" in text_lower:
                metadata["employees"] = text
                metadata["company_size"] = text  # Store as both for compatibility
                if debug:
                    logger.debug(f"Found employees: {text}")

            # Company type
            elif not metadata["type"] and "type" in text_lower:
                metadata["type"] = text.replace("Type", "").replace("type", "").strip()
                if debug:
                    logger.debug(f"Found company type: {metadata['type']}")
            elif not metadata["type"] and any(
                company_type in text_lower
                for company_type in [
                    "public company",
                    "private company",
                    "nonprofit",
                    "government",
                    "self-employed",
                    "partnership",
                ]
            ):
                metadata["type"] = text
                if debug:
                    logger.debug(f"Found unlabeled company type: {text}")

            # Founded year
            elif not metadata["founded"] and "founded" in text_lower:
                metadata["founded"] = text.replace("Founded", "").replace("founded", "").strip()
                if debug:
                    logger.debug(f"Found founded: {metadata['founded']}")
            elif (
                not metadata["founded"]
                and text.isdigit()
                and len(text) == 4
                and 1900 < int(text) < 2100
            ):
                metadata["founded"] = text
                if debug:
                    logger.debug(f"Found potential founding year: {text}")

            # Specialties
            elif not metadata["specialties"] and "specialties" in text_lower:
                metadata["specialties"] = (
                    text.replace("Specialties", "").replace("specialties", "").strip()
                )
                if debug:
                    logger.debug(f"Found specialties: {metadata['specialties']}")

        # Stop when we find a post title (for company posts page)
        if include_end_idx and isinstance(element, Title) and "Feed post" in text:
            end_idx = i
            if debug:
                logger.debug(f"Stopping metadata extraction at element {i}: {text}")
            break

    # If we're including end_idx and didn't find a natural end
    if include_end_idx and end_idx == 0 and len(elements) > 10:
        end_idx = 10

    if include_end_idx:
        return metadata, end_idx
    return metadata
