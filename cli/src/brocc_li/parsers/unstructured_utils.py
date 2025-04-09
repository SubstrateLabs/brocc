from typing import Callable, List, Optional, Tuple

from unstructured.documents.elements import Element, Title

from brocc_li.parsers.linkedin_utils import is_noisy
from brocc_li.utils.logger import logger


def is_element_noisy(
    element: Element,
    specific_noise_patterns: Optional[List[str]] = None,
    debug: bool = False,
    special_conditions: Optional[Callable[[Element, str], bool]] = None,
) -> bool:
    """
    Generalized function to check if an element contains noise.

    Args:
        element: The element to check
        specific_noise_patterns: Optional list of page-specific noise patterns
        debug: Whether to output debug logs
        special_conditions: Optional callable that returns True if element should be kept
                          despite matching noise patterns (e.g., keeping follower counts)

    Returns:
        True if the element contains noise and should be filtered out
    """
    element_text = str(element)

    # First, check if special conditions apply to keep this element
    if special_conditions and special_conditions(element, element_text):
        if debug:
            logger.debug(f"Element kept due to special condition: {element_text[:50]}...")
        return False

    # Check for general noise patterns first
    if is_noisy(element_text, debug=debug):
        return True

    # Check for specific noise patterns if provided
    if specific_noise_patterns:
        text_lower = element_text.lower().strip()

        for pattern in specific_noise_patterns:
            if pattern.lower() == text_lower or pattern.lower() in text_lower:
                if debug:
                    logger.debug(f"Specific noise: matched '{pattern}' in '{element_text[:50]}...'")
                return True

    return False


def extract_section_by_title(
    elements: List[Element], title_text: str, start_idx: int = 0, debug: bool = False
) -> Tuple[List[Element], int]:
    """
    Extract section elements based on section title.
    Returns the section elements and the index where the section ends.

    Args:
        elements: List of elements to search through
        title_text: Text to look for in a Title element to mark section start
        start_idx: Optional index to start searching from
        debug: Whether to output debug logs

    Returns:
        Tuple of (section_elements, end_index) where end_index is where the section ends
    """
    section_elements = []
    in_section = False
    end_idx = len(elements)

    for i, element in enumerate(elements[start_idx:], start=start_idx):
        element_text = str(element).strip()

        # Look for section title
        if isinstance(element, Title) and title_text.lower() in element_text.lower():
            in_section = True
            if debug:
                logger.debug(f"Found section '{title_text}' at element {i}: {element_text}")
            continue

        # Add elements while in section
        if in_section:
            # Stop if we find another section title
            if isinstance(element, Title) and len(element_text) < 30 and i > start_idx + 1:
                end_idx = i
                if debug:
                    logger.debug(f"End of section '{title_text}' at element {i}: {element_text}")
                break

            section_elements.append(element)

    if debug and section_elements:
        logger.debug(f"Extracted {len(section_elements)} elements for section '{title_text}'")

    return section_elements, end_idx
