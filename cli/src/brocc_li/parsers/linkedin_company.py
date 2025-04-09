from typing import Any, Dict, List, Optional, Tuple

from unstructured.documents.elements import Element, NarrativeText, Text, Title
from unstructured.partition.html import partition_html

from brocc_li.parsers.linkedin_utils import extract_company_metadata, is_noisy
from brocc_li.utils.logger import logger

# LinkedIn company-specific noise patterns
COMPANY_NOISE_PATTERNS = [
    "Sign in",
    "Follow",
    "Report this company",
    "Get the LinkedIn app",
    "Like",
    "Comment",
    "Share",
    "Send",
    "Similar pages",
    "See all",
    "View all",
    "Home",
    "Get the app",
    "Join now",
]


def is_company_noise(text: str, debug: bool = False) -> bool:
    """Check if text is LinkedIn company profile-specific noise."""
    if not text:
        return True

    text_lower = text.lower().strip()

    # Exact matches or patterns indicating noise
    for pattern in COMPANY_NOISE_PATTERNS:
        if pattern.lower() == text_lower or pattern.lower() in text_lower:
            if debug:
                logger.debug(f"Company noise: matched '{pattern}' in '{text[:50]}...'")
            return True

    # Filter short, likely metadata/UI elements by length and digits
    if len(text_lower) < 10 and any(char.isdigit() for char in text_lower):
        if debug:
            logger.debug(f"Company noise: short text with digit '{text}'")
        return True

    return False


def _is_element_noise(element: Element, debug: bool = False) -> bool:
    """Check if an element contains general or company-specific noise."""
    element_text = str(element)

    # Special case: keep follower and employee count for company metadata
    if ("followers" in element_text or "employees" in element_text) and len(element_text) < 30:
        return False

    # Keep funding stats even if short
    if any(keyword in element_text.lower() for keyword in ["series", "total investors"]):
        return False

    if is_noisy(element_text, debug=debug):
        return True
    if is_company_noise(element_text, debug=debug):
        return True
    return False


def _extract_section_by_title(
    elements: List[Element], title_text: str, start_idx: int = 0, debug: bool = False
) -> Tuple[List[Element], int]:
    """
    Extract section elements based on section title.
    Returns the section elements and the index where the section ends.
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


def _extract_overview_section(elements: List[Element], debug: bool = False) -> Optional[str]:
    """Extract the Overview section text from elements."""
    overview_elements, _ = _extract_section_by_title(elements, "Overview", debug=debug)

    overview_text = []
    for element in overview_elements:
        if isinstance(element, NarrativeText) and len(str(element)) > 30:
            text = str(element).strip()
            overview_text.append(text)
            if debug:
                logger.debug(f"Added Overview content: {text[:50]}...")

    if overview_text:
        return "\n\n".join(overview_text)
    return None


def _extract_contact_info(elements: List[Element], debug: bool = False) -> Dict[str, Optional[str]]:
    """Extract contact information from the Contact info section."""
    contact_info: Dict[str, Optional[str]] = {
        "website": None,
        "phone": None,
        "email": None,
        "address": None,
    }

    contact_elements, _ = _extract_section_by_title(elements, "Contact info", debug=debug)

    for element in contact_elements:
        text = str(element).strip()

        # Website typically contains http/https or www
        if (
            isinstance(element, Text)
            and not contact_info["website"]
            and ("http:" in text.lower() or "https:" in text.lower() or "www." in text.lower())
        ):
            contact_info["website"] = text
            if debug:
                logger.debug(f"Found contact website: {text}")

        # Phone typically contains digits and dashes/parentheses
        elif (
            isinstance(element, Text)
            and not contact_info["phone"]
            and any(char.isdigit() for char in text)
            and ("+" in text or "-" in text or "(" in text)
        ):
            contact_info["phone"] = text
            if debug:
                logger.debug(f"Found contact phone: {text}")

        # Email typically contains @
        elif isinstance(element, Text) and not contact_info["email"] and "@" in text:
            contact_info["email"] = text
            if debug:
                logger.debug(f"Found contact email: {text}")

        # Address typically has commas and location keywords
        elif (
            isinstance(element, Text)
            and not contact_info["address"]
            and "," in text
            and any(loc in text for loc in ["Street", "Ave", "Boulevard", "Rd", "Suite"])
        ):
            contact_info["address"] = text
            if debug:
                logger.debug(f"Found contact address: {text}")

    return contact_info


def _extract_funding_info(elements: List[Element], debug: bool = False) -> Dict[str, Optional[str]]:
    """Extract funding information."""
    funding_info: Dict[str, Optional[str]] = {
        "stage": None,
        "amount": None,
        "investors": None,
    }

    funding_elements, _ = _extract_section_by_title(elements, "Funding", debug=debug)

    for element in funding_elements:
        text = str(element).strip()

        # Funding stage (Seed, Series A, etc.)
        if isinstance(element, Text) and not funding_info["stage"] and "Series" in text:
            funding_info["stage"] = text
            if debug:
                logger.debug(f"Found funding stage: {text}")

        # Funding amount (usually contains currency symbols or digits)
        elif (
            isinstance(element, Text)
            and not funding_info["amount"]
            and ("$" in text or "€" in text or "£" in text)
        ):
            funding_info["amount"] = text
            if debug:
                logger.debug(f"Found funding amount: {text}")

        # Investor count
        elif (
            isinstance(element, Text)
            and not funding_info["investors"]
            and "investors" in text.lower()
        ):
            funding_info["investors"] = text
            if debug:
                logger.debug(f"Found investors info: {text}")

    return funding_info


def _extract_people_highlights(elements: List[Element], debug: bool = False) -> Dict[str, Any]:
    """Extract people highlights."""
    people_highlights: Dict[str, Any] = {
        "key_people": [],
        "connections": None,
        "location_highlights": None,
    }

    people_elements, _ = _extract_section_by_title(elements, "People highlights", debug=debug)

    # Look for location-based groupings
    for _i, element in enumerate(people_elements):
        if isinstance(element, Title) and "employees work in" in str(element).lower():
            people_highlights["location_highlights"] = str(element).strip()
            if debug:
                logger.debug(f"Found location highlight: {str(element)}")

        # Look for connection counts
        elif isinstance(element, Title) and "Connection" in str(element):
            people_highlights["connections"] = str(element).strip()
            if debug:
                logger.debug(f"Found connections: {str(element)}")

        # Capture employee names
        elif (
            isinstance(element, Text)
            and len(str(element)) > 3
            and not any(char.isdigit() for char in str(element))
        ):
            # Skip noise text like "Show all people highlights"
            if "show all" not in str(element).lower():
                people_highlights["key_people"].append(str(element).strip())
                if debug:
                    logger.debug(f"Added key person: {str(element)}")

    return people_highlights


def linkedin_company_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        elements: List[Element] = partition_html(text=html)
        logger.info(f"unstructured found {len(elements)} raw elements for company profile.")
        if debug:
            logger.debug("Raw company profile elements:")
            for i, element in enumerate(elements):
                logger.debug(
                    f"  Raw Element {i + 1}: {type(element).__name__} - {str(element)[:100]}..."
                )

        if not elements:
            logger.warning("unstructured.partition_html returned no elements for company profile.")
            return "<!-- unstructured found no elements -->"

        # --- Filter Noise --- #
        filtered_elements: List[Element] = []
        for element in elements:
            if _is_element_noise(element, debug=debug):
                continue
            filtered_elements.append(element)

        logger.info(f"Kept {len(filtered_elements)} elements after filtering company noise.")

        if debug:
            logger.debug("Filtered company profile elements:")
            for i, element in enumerate(filtered_elements):
                logger.debug(
                    f"  Filtered Element {i + 1}: {type(element).__name__} - {str(element)[:100]}..."
                )

        if not filtered_elements:
            logger.warning("No elements remaining after filtering company noise.")
            return "<!-- No elements remaining after filtering noise -->"

        # --- Extract Company Metadata --- #
        company_metadata = extract_company_metadata(filtered_elements, debug=debug)

        # --- Extract Additional Sections --- #
        overview_section = _extract_overview_section(filtered_elements, debug=debug)
        contact_info = _extract_contact_info(filtered_elements, debug=debug)
        funding_info = _extract_funding_info(filtered_elements, debug=debug)
        people_highlights = _extract_people_highlights(filtered_elements, debug=debug)

        # --- Create Markdown Output --- #

        # Company header
        result_md = f"# {company_metadata['name'] or 'Company Profile'}\n\n"

        if company_metadata["logo_url"]:
            result_md += f"![Company Logo]({company_metadata['logo_url']})\n\n"

        if company_metadata["description"]:
            result_md += f"{company_metadata['description']}\n\n"

        # Metadata details as a list
        metadata_items = []
        if company_metadata["industry"]:
            metadata_items.append(f"**Industry:** {company_metadata['industry']}")
        if company_metadata["location"]:
            metadata_items.append(f"**Location:** {company_metadata['location']}")
        if company_metadata["website"]:
            metadata_items.append(f"**Website:** {company_metadata['website']}")
        if company_metadata["followers"]:
            metadata_items.append(f"**Followers:** {company_metadata['followers']}")
        if company_metadata["employees"]:
            metadata_items.append(f"**Size:** {company_metadata['employees']}")

        if metadata_items:
            result_md += "\n".join(metadata_items) + "\n\n"

        # Overview section if available
        if overview_section:
            result_md += "## Overview\n\n" + overview_section + "\n\n"

        # Contact information
        contact_items = []
        for key, value in contact_info.items():
            if value:
                contact_items.append(f"**{key.capitalize()}:** {value}")

        if contact_items:
            result_md += "## Contact Information\n\n" + "\n".join(contact_items) + "\n\n"

        # Funding information
        funding_items = []
        for key, value in funding_info.items():
            if value:
                funding_items.append(f"**{key.capitalize()}:** {value}")

        if funding_items:
            result_md += "## Funding\n\n" + "\n".join(funding_items) + "\n\n"

        # People highlights
        if any(value for value in people_highlights.values() if value):
            result_md += "## People Highlights\n\n"

            if people_highlights["location_highlights"]:
                result_md += f"{people_highlights['location_highlights']}\n\n"

            if people_highlights["connections"]:
                result_md += f"{people_highlights['connections']}\n\n"

            if people_highlights["key_people"]:
                result_md += "Notable people:\n"
                for person in people_highlights["key_people"]:
                    result_md += f"- {person}\n"
                result_md += "\n"

        logger.info("Successfully extracted company profile information.")
        if debug:
            logger.debug(f"Final markdown structure contains {len(result_md.splitlines())} lines")

        return result_md.strip()

    except Exception as e:
        logger.error(
            "Error processing LinkedIn company HTML with unstructured",
            exc_info=True,
        )
        return f"Error processing LinkedIn company HTML with unstructured: {e}"
