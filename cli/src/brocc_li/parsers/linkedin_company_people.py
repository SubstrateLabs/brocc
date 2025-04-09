from typing import List, Optional

from unstructured.documents.elements import Element
from unstructured.partition.html import partition_html

from brocc_li.parsers.linkedin_utils import (
    extract_company_metadata,
    is_connection_info,
    is_job_title,
    is_person_name,
)
from brocc_li.utils.logger import logger


def linkedin_company_people_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Parses the HTML content of LinkedIn Company People pages into Markdown.

    This parser converts the unstructured output to markdown using pattern
    recognition to identify people, job titles and connections.
    """
    logger.info("Starting LinkedIn Company People HTML processing...")
    try:
        # Partition the HTML using unstructured
        elements: List[Element] = partition_html(text=html)
        logger.info(f"unstructured found {len(elements)} raw elements.")

        if debug:
            logger.debug("Raw LinkedIn Company People elements:")
            for i, element in enumerate(elements[:20]):  # Limit to first 20 elements
                logger.debug(
                    f"  Raw Element {i + 1}: {type(element).__name__} - {str(element)[:50]}..."
                )
            if len(elements) > 20:
                logger.debug(f"  ... and {len(elements) - 20} more elements")

        if not elements:
            logger.warning("unstructured.partition_html returned no elements.")
            return "<!-- unstructured found no elements -->"

        # --- Extract Company Information using LinkedIn Utils --- #
        company_metadata = extract_company_metadata(elements[:15], debug=debug)
        company_name = company_metadata.get("name", "Unknown Company")

        # Collect company info for markdown
        company_info = []

        # Add company description if available
        if company_metadata.get("description"):
            company_info.append(f"*{company_metadata['description']}*")

        # Add industry if available
        if company_metadata.get("industry"):
            company_info.append(f"- Industry: {company_metadata['industry']}")

        # Add location if available
        if company_metadata.get("location"):
            company_info.append(f"- Location: {company_metadata['location']}")

        # Add followers count if available
        if company_metadata.get("followers"):
            company_info.append(f"- {company_metadata['followers']}")

        # Add employees count if available
        if company_metadata.get("employees"):
            company_info.append(f"- {company_metadata['employees']}")

        # Add website if available
        if company_metadata.get("website"):
            company_info.append(f"- Website: {company_metadata['website']}")

        # Add other metadata
        for key in ["founded", "type", "specialties"]:
            if company_metadata.get(key):
                company_info.append(f"- {key.capitalize()}: {company_metadata[key]}")

        # --- Process People --- #
        # Find people by looking for text patterns in the elements
        people_data = []
        processed_names = set()
        job_titles = {}  # Map person name -> job title

        # First pass: Collect all possible people names, job titles and connection info
        for i, element in enumerate(elements):
            elem_text = str(element).strip()
            if not elem_text:
                continue

            # Use our helper functions to identify element types
            if is_person_name(elem_text):
                if elem_text not in processed_names:
                    processed_names.add(elem_text)
                    # Create entry in people_data
                    people_data.append({"name": elem_text, "job": "", "connections": []})
            elif is_job_title(elem_text):
                # Store job title to associate with a person later
                job_titles[i] = elem_text

        # Second pass: Associate job titles with people by proximity
        for _i, person in enumerate(people_data):
            person_name = person["name"]
            person_index = None

            # Find the index of this person in the original elements
            for j, element in enumerate(elements):
                if str(element).strip() == person_name:
                    person_index = j
                    break

            if person_index is not None:
                # Look at elements after the person name for job titles
                # Within a reasonable proximity (5 elements)
                for j in range(person_index + 1, min(person_index + 6, len(elements))):
                    if j in job_titles:
                        person["job"] = job_titles[j]
                        break

        # Third pass: Collect connection information
        for _i, person in enumerate(people_data):
            person_name = person["name"]
            person_index = None

            # Find the index of this person in the original elements
            for j, element in enumerate(elements):
                if str(element).strip() == person_name:
                    person_index = j
                    break

            if person_index is not None:
                # Look at nearby elements for connection info
                for j in range(person_index + 1, min(person_index + 10, len(elements))):
                    elem_text = str(elements[j]).strip()
                    if is_connection_info(elem_text) and elem_text not in person["connections"]:
                        person["connections"].append(elem_text)

        # Fourth pass: Fix cases where a job title was incorrectly identified as a person
        # This happens when the pattern detection sees a standalone job title
        filtered_people = []
        job_title_names = set()

        for person in people_data:
            # Check if this "person" is actually a job title
            if is_job_title(person["name"]):
                job_title_names.add(person["name"])
                continue

            # Good person entry, keep it
            filtered_people.append(person)

        # Replace with filtered list
        people_data = filtered_people

        # Final pass: Clean up and deduplicate
        seen_people = set()
        final_people = []

        for person in people_data:
            # Skip empty entries
            if not person["name"]:
                continue

            # Skip duplicates
            if person["name"] in seen_people:
                continue

            # Add to final list
            final_people.append(person)
            seen_people.add(person["name"])

        people_data = final_people

        # --- Generate Markdown --- #
        markdown_parts = []

        # Add company header
        markdown_parts.append(f"# LinkedIn Company People: {company_name}")

        # Add company info section
        if company_info:
            markdown_parts.append("\n## Company Information")
            markdown_parts.extend(company_info)

        # Add people section
        markdown_parts.append("\n## People")

        # Add each person
        for person in people_data:
            markdown_parts.append(f"\n### {person['name']}")

            # Add job title
            if person["job"]:
                markdown_parts.append(f"- *{person['job']}*")

            # Add connection info
            for connection in person["connections"]:
                if not connection.startswith("-"):
                    markdown_parts.append(f"- {connection}")
                else:
                    markdown_parts.append(connection)

        # Join all parts with newlines for better readability
        result_md = "\n".join(markdown_parts)

        logger.info("Successfully processed LinkedIn Company People HTML.")
        if debug:
            logger.debug(f"Final markdown structure contains {len(result_md.splitlines())} lines")

        return result_md.strip()

    except Exception as e:
        logger.error(
            "Error processing LinkedIn Company People HTML with unstructured",
            exc_info=True,
        )
        return f"Error processing LinkedIn Company People HTML: {e}"
