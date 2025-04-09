import re
from typing import List, Optional, Tuple

from unstructured.documents.elements import Element, NarrativeText, Text

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
