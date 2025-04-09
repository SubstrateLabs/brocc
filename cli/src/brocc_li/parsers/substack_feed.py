from typing import List, Optional

from unstructured.documents.elements import Element, Image, ListItem, NarrativeText, Text, Title
from unstructured.partition.html import partition_html

from brocc_li.parsers.substack_utils import format_image_markdown
from brocc_li.utils.logger import logger


def substack_feed_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        logger.info("Starting Substack HTML parsing with unstructured...")
        elements: List[Element] = partition_html(text=html)
        logger.info(f"unstructured found {len(elements)} raw elements.")

        if not elements:
            logger.warning("unstructured.partition_html returned no elements.")
            return "<!-- unstructured found no elements -->"

        # Enhanced logging of element metadata
        if debug:
            for i, element in enumerate(elements):
                element_text = str(element).strip()
                if not element_text:
                    continue

                # Log detailed element info including any metadata
                metadata = getattr(element, "metadata", None)
                metadata_str = str(metadata) if metadata else "None"

                logger.debug(
                    f"Element {i + 1}: {type(element).__name__} - '{element_text[:100]}...'"
                    + f"\n  Metadata: {metadata_str}"
                )

        # Group elements into posts/sections
        sections = []
        current_section = []
        section_title = None

        for _i, element in enumerate(elements):
            element_text = str(element).strip()
            if not element_text:
                continue

            # Create a new section when we find a potential section marker
            # Look for patterns indicating new content blocks
            is_new_section = False

            # Title elements or short text that looks like a substack publication name
            if isinstance(element, Title) or (
                isinstance(element, Text)
                and len(element_text) < 50
                and not element_text.endswith("read")
                and not element_text.endswith("listen")
                and not element_text.startswith("Followed by")
            ):
                # If we have content in the current section, finalize it
                if current_section and section_title:
                    sections.append((section_title, current_section))
                    current_section = []

                section_title = element_text
                is_new_section = True

                if debug:
                    logger.debug(f"Starting new section with title: {section_title}")

            # If not a section marker, add to current section
            if not is_new_section:
                current_section.append(element)

        # Add the last section if it exists
        if current_section and section_title:
            sections.append((section_title, current_section))

        if debug:
            logger.debug(f"Created {len(sections)} content sections")

        # Generate markdown from sections
        markdown_blocks = []

        for section_title, section_elements in sections:
            # Create a block for each section
            block_lines = [f"### {section_title}"]

            for element in section_elements:
                element_text = str(element).strip()
                if not element_text:
                    continue

                # Format based on element type
                if isinstance(element, NarrativeText) or isinstance(element, Text):
                    formatted_line = element_text
                elif isinstance(element, ListItem):
                    formatted_line = f"- {element_text}"
                elif isinstance(element, Image):
                    # Use our utility function to format images
                    img_markdown = format_image_markdown(element)
                    if img_markdown:
                        formatted_line = img_markdown
                    else:
                        # Skip images that couldn't be formatted
                        continue
                else:
                    # Skip other element types
                    continue

                block_lines.append(formatted_line)

            # Join the block lines and add to blocks
            if len(block_lines) > 1:  # Only add blocks with content
                markdown_blocks.append("\n\n".join(block_lines))

        # Join all blocks with triple newlines for clear separation
        markdown = "\n\n\n".join(markdown_blocks)

        if not markdown.strip():
            logger.warning("unstructured parsing resulted in empty markdown.")
            return "<!-- unstructured parsing completed, but resulted in empty output -->"

        logger.info(
            f"Substack feed parsed successfully, generated {len(markdown_blocks)} content blocks."
        )
        return markdown.strip()

    except Exception as e:
        logger.error(f"Error processing Substack HTML with unstructured: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        # Return error message in the output for debugging
        return f"Error processing Substack HTML with unstructured: {str(e)}"
