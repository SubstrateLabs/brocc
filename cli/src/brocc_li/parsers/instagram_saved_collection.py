import re

from unstructured.documents.elements import Image, ListItem, NarrativeText, Text, Title

from brocc_li.parsers.instagram_utils import (
    clean_element_text,
    partition_instagram_html,
    process_instagram_feed_elements,
)
from brocc_li.utils.logger import logger


def instagram_saved_collection_html_to_md(html: str, debug: bool = False) -> str:
    try:
        logger.info("Starting Instagram saved collection parsing")

        # Partition HTML using shared utility function
        filtered_elements = partition_instagram_html(html, debug=debug)

        if not filtered_elements:
            logger.warning("No elements remaining after filtering.")
            return "<!-- No elements remaining after filtering -->"

        # Attempt to find collection title and description early on
        collection_name = "Saved Collection"
        collection_description = ""
        start_processing_index = 0
        title_found_index = -1

        for i, element in enumerate(filtered_elements[:15]):  # Look in first 15 elements
            element_text = str(element).strip()
            if title_found_index == -1 and isinstance(element, Title) and len(element_text) > 0:
                if element_text.lower() != "instagram" and "saved" not in element_text.lower():
                    collection_name = element_text
                    title_found_index = i  # Mark where title was found
                    start_processing_index = i + 1  # Tentatively start processing after title
                    if debug:
                        logger.debug(f"Found collection name: {collection_name} at index {i}")
                    # Look for description *only if it's Text/NarrativeText* immediately after title
                    if i + 1 < len(filtered_elements):
                        next_element = filtered_elements[i + 1]
                        next_text = str(next_element).strip()
                        if isinstance(next_element, (Text, NarrativeText)) and len(next_text) > 5:
                            collection_description = next_text
                            start_processing_index = i + 2  # Start processing after description
                            if debug:
                                logger.debug(
                                    f"Found collection description: {collection_description}"
                                )
                    # No need to break here, let it continue in case description appears later

            # If title wasn't found yet, look for early text description
            elif (
                title_found_index == -1
                and isinstance(element, (Text, NarrativeText))
                and len(element_text) > 10
                and i < 5
            ):
                collection_description = element_text
                start_processing_index = i + 1  # Start processing after this potential description
                if debug:
                    logger.debug(f"Found potential description early: {collection_description}")

        # If title wasn't found, reset start index to 0 to process all elements as posts
        if title_found_index == -1:
            logger.warning("Collection title not found, processing all elements as posts.")
            start_processing_index = 0

        if debug:
            logger.debug(f"Final start_processing_index for posts: {start_processing_index}")

        # Process the elements for posts starting from the calculated index
        posts = process_instagram_feed_elements(
            filtered_elements[start_processing_index:], debug=debug
        )

        # Build markdown output
        markdown_blocks = [f"# {collection_name}"]
        if collection_description:
            markdown_blocks.append(collection_description)

        # Add all collected posts to markdown
        if posts:
            posts_section = ["## Saved Posts"]

            for idx, post in enumerate(posts, 1):
                post_md = [f"### Post {idx}"]

                # Add user info if available
                if "user" in post["metadata"]:
                    post_md.append(f"**From**: {post['metadata']['user']}")

                # Add post text
                if post["text"]:
                    post_md.append("\n".join(post["text"]))

                # Add metadata if available (e.g., engagement count)
                if "count" in post["metadata"]:
                    post_md.append(f"**{post['metadata']['count']}** likes/views")

                # Add image URL if available
                if "image_url" in post["metadata"]:
                    post_md.append(f"![Image]({post['metadata']['image_url']})")

                # Add hashtags section if found
                if post["hashtags"]:
                    post_md.append(f"**Tags**: {' '.join(sorted(list(post['hashtags'])))}")

                # Add the complete post section
                posts_section.append("\n\n".join(post_md))

            markdown_blocks.extend(posts_section)
        else:
            logger.warning("No saved posts extracted from elements.")
            markdown_blocks.append("<!-- No saved posts extracted -->")

        # Join all blocks with double newlines to create final markdown
        markdown = "\n\n".join(markdown_blocks)

        if (
            not markdown.strip()
            or markdown == f"# {collection_name}\n\n<!-- No saved posts extracted -->"
        ):
            logger.warning("Parsing resulted in effectively empty markdown after processing.")
            return "<!-- Parsing completed, but resulted in empty or placeholder output -->"

        logger.info(
            "Instagram saved collection HTML to markdown conversion completed successfully."
        )
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error processing Instagram saved collection HTML with unstructured",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error processing Instagram saved collection HTML with unstructured: {e}"
