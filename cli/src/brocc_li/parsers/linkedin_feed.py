from typing import List, Optional

from unstructured.documents.elements import Element, Image, ListItem, NarrativeText, Text, Title
from unstructured.partition.html import partition_html

from brocc_li.parsers.linkedin_utils import check_block_type, find_first_link, is_noisy
from brocc_li.utils.logger import logger


def linkedin_feed_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        logger.info("Starting LinkedIn HTML parsing with unstructured...")
        elements: List[Element] = partition_html(text=html)
        logger.info(f"unstructured found {len(elements)} raw elements.")

        if not elements:
            logger.warning("unstructured.partition_html returned no elements.")
            return "<!-- unstructured found no elements -->"

        # --- Filter Noise --- #
        filtered_elements: List[Element] = []
        for _i, element in enumerate(elements):
            element_text = str(element)
            # Pass debug flag to is_noisy
            if is_noisy(element_text, debug=debug) or element_text == "...see more":
                # Logging now happens inside is_noisy if debug is True
                # if debug: logger.debug(f"Filtering noisy element {i+1}: {element_text[:100]}...")
                continue
            filtered_elements.append(element)
        logger.info(f"Kept {len(filtered_elements)} elements after filtering.")

        if not filtered_elements:
            logger.warning("No elements remaining after filtering noise.")
            return "<!-- No elements remaining after filtering noise -->"

        # --- Group by Post Marker --- #
        post_blocks_elements: List[List[Element]] = []
        current_block_elements: List[Element] = []

        for element in filtered_elements:
            element_text = str(element)
            is_post_marker = isinstance(element, Title) and element_text.startswith(
                "Feed post number"
            )

            if is_post_marker and current_block_elements:
                post_blocks_elements.append(current_block_elements)
                current_block_elements = []  # Reset for the new post
            elif not is_post_marker:
                current_block_elements.append(element)

        if current_block_elements:
            post_blocks_elements.append(current_block_elements)
        logger.info(f"Grouped elements into {len(post_blocks_elements)} potential post blocks.")

        # --- Format Blocks with Headers --- #
        final_markdown_blocks = []
        for block_idx, block_elements in enumerate(post_blocks_elements):
            block_content_lines = []
            header = f"### Post {block_idx + 1}"  # Default header
            header_element = None
            block_type_marker = check_block_type(block_elements, debug=debug) or ""

            link_info = find_first_link(block_elements, debug=debug)
            if link_info:
                link_text, link_url, header_element = link_info
                header = f"### [{link_text}]({link_url}) {block_type_marker}".strip()
                if debug:
                    logger.debug(f"Using header for block {block_idx + 1}: {header}")
            elif debug:
                logger.debug(
                    f"No suitable profile link found for block {block_idx + 1}, using default header."
                )

            for element in block_elements:
                if element is header_element:
                    continue

                element_text = str(element).strip()
                formatted_line = ""

                # Deduplication check is now handled *after* formatting
                is_text_element = isinstance(element, (NarrativeText, Text))

                if isinstance(element, Title):
                    if header_element and element_text == getattr(header_element, "text", None):
                        continue
                elif is_text_element:
                    formatted_line = element_text
                elif isinstance(element, ListItem):
                    if header_element and element_text == getattr(header_element, "text", None):
                        continue
                    formatted_line = f"- {element_text}"
                elif isinstance(element, Image):
                    alt_text = element.text or "Image"
                    alt_text = alt_text.replace("'s profile photo", "").strip()
                    img_url = element.metadata.image_url
                    if img_url:
                        if header_element and alt_text == getattr(header_element, "text", None):
                            if debug:
                                logger.debug(
                                    f"Skipping image with alt text same as header: {alt_text}"
                                )
                            continue
                        formatted_line = f"![{alt_text}]({img_url})"
                    else:
                        if debug:
                            logger.debug(f"Skipping Image element with no URL: {alt_text}")
                        continue

                if formatted_line:
                    # De-duplication: Replace last line if current line is longer and starts with it
                    if (
                        is_text_element
                        and block_content_lines
                        and formatted_line.startswith(block_content_lines[-1])
                        and len(formatted_line) > len(block_content_lines[-1])
                    ):
                        if debug:
                            logger.debug(
                                f"Replacing previous line with longer text: {formatted_line[:100]}..."
                            )
                        block_content_lines[-1] = formatted_line  # Replace last line
                    elif block_content_lines and formatted_line == block_content_lines[-1]:
                        if debug:
                            logger.debug(
                                f"Skipping exact duplicate line: {formatted_line[:100]}..."
                            )
                        continue  # Skip exact duplicates too
                    else:
                        block_content_lines.append(formatted_line)

            if block_content_lines:
                final_block_md = header + "\n\n" + "\n\n".join(block_content_lines)
                final_markdown_blocks.append(final_block_md)
            elif debug:
                logger.debug(
                    f"Block {block_idx + 1} resulted in no content after formatting, skipping."
                )

        # Join the final blocks with triple newlines
        markdown = "\n\n\n".join(final_markdown_blocks)

        if not markdown.strip():
            logger.warning(
                "unstructured parsing resulted in empty markdown after all processing steps."
            )
            return "<!-- unstructured parsing completed, but resulted in empty output -->"

        logger.info("unstructured parsing, filtering, grouping, and header formatting successful.")
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error processing LinkedIn HTML with unstructured",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error processing LinkedIn HTML with unstructured: {e}"
