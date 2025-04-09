from typing import List, Optional

from unstructured.documents.elements import Element, NarrativeText, Text, Title
from unstructured.partition.html import partition_html

from brocc_li.parsers.linkedin_utils import extract_company_metadata, is_noisy
from brocc_li.utils.logger import logger

# LinkedIn company about page-specific noise patterns
ABOUT_NOISE_PATTERNS = [
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
    "About us",
    "See all details",
    "Manage your account and privacy",
    "Learn more about Recommended Content",
    "Get directions to",
]


def is_about_noise(text: str, debug: bool = False) -> bool:
    """Check if text is LinkedIn company about page-specific noise."""
    if not text:
        return True

    text_lower = text.lower().strip()

    # Exact matches or patterns indicating noise
    for pattern in ABOUT_NOISE_PATTERNS:
        if pattern.lower() == text_lower or pattern.lower() in text_lower:
            if debug:
                logger.debug(f"About noise: matched '{pattern}' in '{text[:50]}...'")
            return True

    # Filter short, likely metadata/UI elements by length and digits
    if len(text_lower) < 10 and any(char.isdigit() for char in text_lower):
        if debug:
            logger.debug(f"About noise: short text with digit '{text}'")
        return True

    return False


def _is_element_noise(element: Element, debug: bool = False) -> bool:
    """Check if an element contains general or about page-specific noise."""
    element_text = str(element)

    # Special case: keep company size and year founded info
    if any(keyword in element_text.lower() for keyword in ["employees", "founded", "headquarters"]):
        return False

    if is_noisy(element_text, debug=debug):
        return True
    if is_about_noise(element_text, debug=debug):
        return True
    return False


def _extract_overview_section(elements: List[Element], debug: bool = False) -> Optional[str]:
    """Extract the Overview/About section text from elements."""
    overview_text = []
    in_overview = False

    # The About section typically starts near the top and contains longer narrative text
    for i, element in enumerate(elements[:30]):
        if isinstance(element, Title) and any(
            word in str(element).lower() for word in ["about", "overview"]
        ):
            in_overview = True
            if debug:
                logger.debug(f"Found overview section title: {str(element)}")
            continue

        if in_overview and isinstance(element, (Text, NarrativeText)) and len(str(element)) > 30:
            text = str(element).strip()

            # Skip map images, directions, and other noise in overview
            if any(
                skip_term in text.lower()
                for skip_term in ["map of", "get directions", "visit our", "your settings"]
            ):
                if debug:
                    logger.debug(f"Skipped noise in overview: {text[:50]}...")
                continue

            # Stop if we encounter another section
            if isinstance(element, Title) and i > 5:
                break

            overview_text.append(text)
            if debug:
                logger.debug(f"Added Overview content: {text[:50]}...")

    # If we didn't find a section title, look for long narrative text that could be a description
    if not overview_text:
        for element in elements[:20]:
            if isinstance(element, NarrativeText) and len(str(element)) > 100:
                text = str(element).strip()

                # Skip anything that looks like a map or directions
                if any(
                    skip_term in text.lower()
                    for skip_term in ["map of", "get directions", "visit our", "your settings"]
                ):
                    continue

                overview_text.append(text)
                if debug:
                    logger.debug(f"Found narrative overview content: {text[:50]}...")
                break

        # Also look for shorter, company description text near the top
        if not overview_text:
            for element in elements[:8]:
                if isinstance(element, NarrativeText) and 30 < len(str(element)) < 100:
                    text = str(element).strip()
                    if any(
                        keyword in text.lower()
                        for keyword in [
                            "ai",
                            "company",
                            "service",
                            "product",
                            "platform",
                            "solution",
                        ]
                    ):
                        overview_text.append(text)
                        if debug:
                            logger.debug(f"Found short company description: {text[:50]}...")
                        break

    if overview_text:
        return "\n\n".join(overview_text)
    return None


def _extract_locations(elements: List[Element], debug: bool = False) -> List[str]:
    """Extract locations where the company has offices."""
    locations = []
    in_locations_section = False

    for i, element in enumerate(elements):
        text = str(element).strip()

        if isinstance(element, Title) and any(
            word in text.lower() for word in ["location", "office"]
        ):
            in_locations_section = True
            if debug:
                logger.debug(f"Found locations section at element {i}: {text}")
            continue

        if in_locations_section:
            # Stop if we encounter another section title
            if isinstance(element, Title) and i > 5:
                in_locations_section = False
                break

            if isinstance(element, Text) and len(text) > 3 and "," in text:
                # Skip map references which aren't actual locations
                if "map" in text.lower() or "get directions" in text.lower():
                    if debug:
                        logger.debug(f"Skipped map reference: {text}")
                    continue

                locations.append(text)
                if debug:
                    logger.debug(f"Added location: {text}")

    return locations


def _extract_specialties(elements: List[Element], debug: bool = False) -> List[str]:
    """Extract company specialties if listed separately from metadata."""
    specialties = []
    in_specialties_section = False

    for i, element in enumerate(elements):
        text = str(element).strip()

        if isinstance(element, Title) and "specialt" in text.lower():
            in_specialties_section = True
            if debug:
                logger.debug(f"Found specialties section at element {i}: {text}")
            continue

        if in_specialties_section:
            # Stop if we encounter another section title
            if isinstance(element, Title) and i > 5:
                in_specialties_section = False
                break

            if isinstance(element, Text) and len(text) > 3:
                # Split by commas if multiple specialties in one element
                if "," in text:
                    for specialty in text.split(","):
                        cleaned = specialty.strip()
                        if cleaned:
                            specialties.append(cleaned)
                            if debug:
                                logger.debug(f"Added specialty: {cleaned}")
                else:
                    specialties.append(text)
                    if debug:
                        logger.debug(f"Added specialty: {text}")

    return specialties


def linkedin_company_about_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        elements: List[Element] = partition_html(text=html)
        logger.info(f"unstructured found {len(elements)} raw elements for company about page.")
        if debug:
            logger.debug("Raw company about page elements:")
            for i, element in enumerate(elements):
                logger.debug(
                    f"  Raw Element {i + 1}: {type(element).__name__} - {str(element)[:100]}..."
                )

        if not elements:
            logger.warning(
                "unstructured.partition_html returned no elements for company about page."
            )
            return "<!-- unstructured found no elements -->"

        # --- Filter Noise --- #
        filtered_elements: List[Element] = []
        for element in elements:
            if _is_element_noise(element, debug=debug):
                continue
            filtered_elements.append(element)

        logger.info(f"Kept {len(filtered_elements)} elements after filtering about page noise.")

        if debug:
            logger.debug("Filtered company about page elements:")
            for i, element in enumerate(filtered_elements):
                logger.debug(
                    f"  Filtered Element {i + 1}: {type(element).__name__} - {str(element)[:100]}..."
                )

        if not filtered_elements:
            logger.warning("No elements remaining after filtering about page noise.")
            return "<!-- No elements remaining after filtering noise -->"

        # --- Extract Company Metadata --- #
        company_metadata = extract_company_metadata(filtered_elements, max_elements=20, debug=debug)

        # Extract website from description if not found directly
        if not company_metadata["website"] and company_metadata["description"]:
            desc = company_metadata["description"].lower()
            # Look for common URL patterns in the description
            if ".com" in desc or ".org" in desc or ".io" in desc or ".ai" in desc:
                # Common ways URLs are introduced in text
                for prefix in ["at ", "visit ", "check out ", "website: ", "site: "]:
                    if prefix in desc:
                        start_idx = desc.find(prefix) + len(prefix)
                        # Look for end of URL (space or punctuation)
                        url_text = desc[start_idx:].split()[0].strip(",.:;!?()")
                        if "." in url_text and len(url_text) > 4:  # Simple validation
                            company_metadata["website"] = url_text
                            if debug:
                                logger.debug(f"Extracted website from description: {url_text}")
                            break

        # --- Extract Additional Sections --- #
        overview_section = _extract_overview_section(filtered_elements, debug=debug)
        locations = _extract_locations(filtered_elements, debug=debug)
        specialties = _extract_specialties(filtered_elements, debug=debug)

        # --- Create Markdown Output --- #

        # Company header
        result_md = f"# {company_metadata['name'] or 'Company About'}\n\n"

        if company_metadata["logo_url"]:
            # Ensure we only include one logo, truncate long URLs if needed
            logo_url = company_metadata["logo_url"]
            if len(logo_url) > 100:
                # Truncate to a reasonable length that still works as a URL
                logo_url = logo_url[:100] + "..."
            result_md += f"![Company Logo]({logo_url})\n\n"

        # Metadata details as a list
        metadata_items = []
        if company_metadata["website"]:
            metadata_items.append(f"**Website:** {company_metadata['website']}")
        if company_metadata["industry"]:
            metadata_items.append(f"**Industry:** {company_metadata['industry']}")
        if company_metadata["company_size"]:
            metadata_items.append(f"**Company Size:** {company_metadata['company_size']}")
        if company_metadata["type"]:
            metadata_items.append(f"**Type:** {company_metadata['type']}")
        if company_metadata["founded"]:
            metadata_items.append(f"**Founded:** {company_metadata['founded']}")

        if metadata_items:
            result_md += "\n".join(metadata_items) + "\n\n"

        # Overview section if available
        if overview_section:
            result_md += "## About\n\n" + overview_section + "\n\n"

        # Specialties section
        if company_metadata["specialties"] or specialties:
            result_md += "## Specialties\n\n"
            if company_metadata["specialties"]:
                specialties_text = company_metadata["specialties"]
                # Split by commas and create bullet points
                if "," in specialties_text:
                    for specialty in specialties_text.split(","):
                        result_md += f"- {specialty.strip()}\n"
                else:
                    result_md += f"{specialties_text}\n"

            # Add any additional specialties found in separate section
            if specialties and not company_metadata["specialties"]:
                for specialty in specialties:
                    result_md += f"- {specialty}\n"

            result_md += "\n"

        # Locations section
        if locations:
            result_md += "## Locations\n\n"
            for location in locations:
                result_md += f"- {location}\n"
            result_md += "\n"

        logger.info("Successfully extracted company about page information.")
        if debug:
            logger.debug(f"Final markdown structure contains {len(result_md.splitlines())} lines")

        return result_md.strip()

    except Exception as e:
        logger.error(
            "Error processing LinkedIn company about HTML with unstructured",
            exc_info=True,
        )
        return f"Error processing LinkedIn company about HTML with unstructured: {e}"
