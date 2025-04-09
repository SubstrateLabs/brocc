from typing import List, Optional

from unstructured.documents.elements import Element, Image, NarrativeText, Title
from unstructured.partition.html import partition_html

from brocc_li.parsers.linkedin_utils import is_noisy
from brocc_li.utils.logger import logger

# LinkedIn profile-specific noise patterns
PROFILE_NOISE_PATTERNS = [
    "Show all",
    "Show more",
    "Loaded",
    "posts",
    "endorsements",
    "Activate to view",
    "message",
    "Report / Block",
    "Remove Connection",
    "Unfollow",
    "Save to PDF",
    "Request a recommendation",
    "About this profile",
    "Published weekly",
    "Endorsed by",
    "who is highly skilled at this",
]


def is_profile_noise(text: str, debug: bool = False) -> bool:
    """Check if text is LinkedIn profile-specific noise."""
    if not text:
        return True

    text_lower = text.lower()

    for pattern in PROFILE_NOISE_PATTERNS:
        if pattern.lower() in text_lower:
            if debug:
                logger.debug(f"Profile noise: matched '{pattern}' in '{text[:50]}...'")
            return True

    return False


def _is_element_noise(element: Element, debug: bool = False) -> bool:
    """Check if an element contains general or profile-specific noise."""
    element_text = str(element)
    return is_noisy(element_text, debug=debug) or is_profile_noise(element_text, debug=debug)


def _extract_profile_header(
    elements: List[Element], debug: bool = False
) -> tuple[Optional[str], Optional[str]]:
    """Extracts the profile name and image URL from the initial elements."""
    profile_name = None
    profile_image_url = None
    for element in elements:
        element_text = str(element).strip()
        if isinstance(element, Title) and not profile_name:
            profile_name = element_text
            if debug:
                logger.debug(f"Found profile name: {profile_name}")
        elif (
            isinstance(element, Image)
            and not profile_image_url
            and "profile" in (element.text or "").lower()
        ):
            img_url = element.metadata.image_url
            if img_url:
                profile_image_url = img_url
                if debug:
                    logger.debug(f"Found profile image: {profile_image_url[:50]}...")

        # Stop early if both found
        if profile_name and profile_image_url:
            break
    return profile_name, profile_image_url


def linkedin_profile_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        elements: List[Element] = partition_html(text=html)
        logger.info(f"unstructured found {len(elements)} raw elements.")
        if debug:
            # Log ALL raw elements to help pinpoint the issue
            logger.debug("All raw elements:")
            for i, element in enumerate(elements):
                logger.debug(f"  Element {i + 1}: {type(element).__name__} - {str(element)}")

        if not elements:
            logger.warning("unstructured.partition_html returned no elements.")
            return "<!-- unstructured found no elements -->"

        # --- Filter Noise --- #
        filtered_elements: List[Element] = []
        for _i, element in enumerate(elements):
            # Skip if general noise or profile-specific noise
            if _is_element_noise(element, debug=debug):
                continue

            filtered_elements.append(element)

        logger.info(f"Kept {len(filtered_elements)} elements after filtering.")

        if debug:
            # Log ALL filtered elements
            logger.debug("All filtered elements:")
            for i, element in enumerate(filtered_elements):
                logger.debug(f"  Element {i + 1}: {type(element).__name__} - {str(element)}")

        if not filtered_elements:
            logger.warning("No elements remaining after filtering noise.")
            return "<!-- No elements remaining after filtering noise -->"

        # --- Create a simpler structure with direct sections --- #
        sections = {}

        # First, extract profile header info using the helper
        profile_name, profile_image_url = _extract_profile_header(filtered_elements, debug=debug)

        # Build header markdown
        header_md = f"# {profile_name or 'LinkedIn Profile'}\n\n"
        if profile_image_url:
            header_md += f"![Profile Image]({profile_image_url})\n\n"

        sections["header"] = header_md

        # Now organize elements into sections
        section_titles = [
            "About",
            "Experience",
            "Education",
            "Skills",
            "Interests",
            "Projects",
            "Languages",
            "Recommendations",
            "Certifications",
        ]

        current_section = "Other"
        section_elements = {}

        # Initialize all sections
        for section in section_titles:
            section_elements[section] = []
        section_elements["Other"] = []

        # Group elements by section
        for element in filtered_elements:
            text = str(element).strip()

            if not text:
                continue

            # Check if this is a section header
            is_section_header = False
            if isinstance(element, Title):
                for section in section_titles:
                    if section.lower() in text.lower():
                        is_section_header = True
                        current_section = section
                        if debug:
                            logger.debug(f"Found section header: {text} -> {section}")
                        break

            if not is_section_header:
                section_elements[current_section].append(element)

        # Process each section
        markdown_sections = [header_md]

        for section_name, elements in section_elements.items():
            if not elements or section_name == "Other":
                continue

            section_content = []
            section_md = f"## {section_name}\n\n"

            # Special handling for Experience and Education sections - group by company/school
            if section_name in ["Experience", "Education"]:
                # Append text from all non-empty elements in these sections
                for element in elements:
                    text = str(element).strip()
                    if text:
                        section_content.append(text)

            # Skills and Interests get bullet points
            elif section_name in ["Skills", "Interests"]:
                for element in elements:
                    text = str(element).strip()
                    if text:
                        if not text.startswith("- ") and not text.startswith("* "):
                            text = f"- {text}"
                        section_content.append(text)

            # Generic processing for other sections (like About)
            else:
                for element in elements:
                    text = str(element).strip()
                    if text:
                        section_content.append(text)

            if section_content:
                # Use single newline for tighter lists in Exp/Edu/Skills/Interests
                joiner = (
                    "\n"
                    if section_name in ["Experience", "Education", "Skills", "Interests"]
                    else "\n\n"
                )
                section_md += joiner.join(section_content)
                markdown_sections.append(section_md)

        # Add Activities/Posts section separately with metadata
        activity_md = "## Activity\n\n"
        post_count = 0

        # Iterate through elements to find posts and potential repost headers
        for i, element in enumerate(filtered_elements):
            if isinstance(element, NarrativeText):
                text = str(element).strip()
                # Check if it's potential post content (long enough, not noise)
                if len(text) > 100 and not is_profile_noise(text, debug=debug):
                    repost_header = None
                    # Check the previous element to see if it was a repost header
                    if i > 0:
                        prev_element = filtered_elements[i - 1]
                        if isinstance(prev_element, NarrativeText):
                            prev_text = str(prev_element).strip()
                            if "reposted this" in prev_text.lower():
                                repost_header = prev_text

                    # Format the post
                    post_count += 1
                    activity_md += f"### Post {post_count}\n\n"
                    if repost_header:
                        activity_md += f"_{repost_header}_\n\n"  # Add italicized header
                    activity_md += f"{text}\n\n\n"  # Add post content

        if post_count > 0:
            markdown_sections.append(activity_md.rstrip("\n"))

        # Combine all sections
        result = "\n\n".join(markdown_sections)

        if debug:
            logger.debug("Final markdown structure:")
            logger.debug(
                "\n".join(
                    f"Section: {section.splitlines()[0] if section.splitlines() else ''}"
                    for section in markdown_sections
                )
            )

        logger.info("unstructured parsing of LinkedIn profile successful.")
        return result

    except Exception as e:
        logger.error(
            "Error processing LinkedIn profile HTML with unstructured",
            exc_info=True,
        )
        return f"Error processing LinkedIn profile HTML with unstructured: {e}"
