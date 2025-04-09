from typing import Any, Dict, List, Tuple

from unstructured.documents.elements import Element, NarrativeText, Text, Title

from brocc_li.parsers.instagram_utils import (
    partition_instagram_html,
    process_instagram_feed_elements,
)
from brocc_li.utils.logger import logger


def _preprocess_saved_collection(
    filtered_elements: List[Element], debug: bool = False
) -> Tuple[List[Element], Tuple[str, str]]:
    """
    Preprocess elements from an Instagram saved collection to extract collection name and description.

    Returns:
        Tuple of (filtered_elements_to_process, (collection_name, collection_description))
    """
    collection_name = "Saved Collection"
    collection_description = ""
    start_processing_index = 0
    title_found_index = -1

    # Search for Title and potential Description early in the elements
    for i, element in enumerate(filtered_elements[:15]):
        element_text = str(element).strip()

        # If we haven't found the title yet, check if this element is it
        if title_found_index == -1 and isinstance(element, Title) and len(element_text) > 0:
            # Check if it's a plausible collection title
            if element_text.lower() != "instagram" and "saved" not in element_text.lower():
                collection_name = element_text
                title_found_index = i
                start_processing_index = i + 1  # Default: start processing after title
                if debug:
                    logger.debug(f"Found collection name: '{collection_name}' at index {i}")

                # Check *immediately following* element for a TEXT description
                if i + 1 < len(filtered_elements):
                    next_element = filtered_elements[i + 1]
                    next_text = str(next_element).strip()
                    next_element_type = type(next_element)
                    if debug:
                        logger.debug(
                            f"Checking element at index {i + 1} for description. Type: {next_element_type.__name__}"
                        )

                    # *** CRITICAL CHECK: Only Text/NarrativeText counts as description ***
                    is_desc_type = isinstance(next_element, (Text, NarrativeText))

                    # CRITICAL: Also check it doesn't have an image_url - images with captions
                    # can be wrongly classified as Text due to unstructured's class hierarchy
                    has_image_url = (
                        hasattr(next_element, "metadata")
                        and getattr(next_element.metadata, "image_url", None) is not None
                    )

                    if debug:
                        logger.debug(
                            f"Is element {i + 1} of type Text or NarrativeText? {is_desc_type}"
                        )
                        logger.debug(f"Does element {i + 1} have an image_url? {has_image_url}")

                    # Element must be Text/NarrativeText AND must NOT have an image_url to be a description
                    if is_desc_type and not has_image_url and len(next_text) > 5:
                        collection_description = next_text
                        start_processing_index = i + 2  # If description found, start after it
                        if debug:
                            logger.debug(
                                f"Confirmed description: '{collection_description[:50]}...' starting at index {i + 1}"
                            )
                    elif debug:
                        logger.debug(
                            f"Element {i + 1} is NOT Text/NarrativeText or too short. Not treating as description."
                        )
                # Continue loop after finding title, might find description later?

        # If title not found yet, check for early Text description before any title
        elif (
            title_found_index == -1
            and isinstance(element, (Text, NarrativeText))
            and len(element_text) > 10
            and i < 5
        ):
            collection_description = element_text
            start_processing_index = i + 1  # Start processing after this potential description
            if debug:
                logger.debug(
                    f"Found potential early description: '{collection_description[:50]}...' at index {i}"
                )

    # If title was never found, process everything as posts
    if title_found_index == -1:
        logger.warning("Collection title not found, processing all elements as posts.")
        start_processing_index = 0  # Reset to process from the beginning

    if debug:
        logger.debug(f"Final start_processing_index for feed posts: {start_processing_index}")

    # Return the elements to process and collection info
    return (filtered_elements[start_processing_index:], (collection_name, collection_description))


# Custom formatter for saved collections that preserves full image URLs
def _format_saved_collection_posts(posts, section_title="Saved Posts"):
    """Special version of format_feed_posts_to_md that preserves full URLs for saved collections"""
    if not posts:
        return [f"## {section_title}", "<!-- No posts extracted -->"]

    markdown_blocks = [f"## {section_title}"]

    for idx, post in enumerate(posts, 1):
        post_content_blocks = []

        # Add user info if available
        if "user" in post.get("metadata", {}):
            post_content_blocks.append(f"**From**: {post['metadata']['user']}")

        # Add post text
        if post.get("text"):
            post_content_blocks.append("\n".join(post["text"]))

        # Add metadata if available (e.g., engagement count)
        if "count" in post.get("metadata", {}):
            post_content_blocks.append(f"**{post['metadata']['count']}** likes/views")

        # Add image URL if available - don't truncate!
        if "image_url" in post.get("metadata", {}):
            url = post["metadata"]["image_url"]
            post_content_blocks.append(f"![Image]({url})")

        # Add hashtags section if found
        if post.get("hashtags"):
            post_content_blocks.append(f"**Tags**: {' '.join(sorted(post['hashtags']))}")

        # Construct the full markdown for this post IF it has content parts
        if post_content_blocks:
            full_post_md = f"### Post {idx}\n\n" + "\n\n".join(post_content_blocks)
            markdown_blocks.append(full_post_md)

    # Ensure we always return a list. If only the header was added, add a comment.
    if len(markdown_blocks) == 1:
        markdown_blocks.append("<!-- Posts processed, but no content to display -->")

    return markdown_blocks


def instagram_saved_collection_html_to_md(html: str, debug: bool = False) -> str:
    """Convert Instagram saved collection HTML to Markdown."""

    def saved_collection_preprocessor(
        elements: List[Element], debug: bool
    ) -> Tuple[List[Element], Dict[str, Any]]:
        elements_to_process, (collection_name, collection_description) = (
            _preprocess_saved_collection(elements, debug)
        )

        # Return the processed elements and a dictionary with name and description
        result = {"page_title": collection_name}
        if collection_description:
            result["description"] = collection_description

        return elements_to_process, result

    try:
        logger.info("Starting Instagram saved collection parsing")

        # Partition HTML using shared utility function
        filtered_elements = partition_instagram_html(html, debug=debug)

        if not filtered_elements:
            logger.warning("No elements remaining after filtering.")
            return "<!-- No elements remaining after filtering -->"

        # Preprocess elements to extract collection metadata
        elements_to_process, custom_data = saved_collection_preprocessor(filtered_elements, debug)
        page_title = custom_data.get("page_title", "Saved Collection")

        # Process elements into structured posts
        posts = process_instagram_feed_elements(elements_to_process, debug=debug)

        # Build markdown output
        markdown_blocks = [f"# {page_title}"]

        # Add custom description if available
        if "description" in custom_data:
            markdown_blocks.append(custom_data["description"])

        # Format posts to markdown using our custom formatter that preserves full URLs
        post_blocks = _format_saved_collection_posts(posts, section_title="Saved Posts")
        if post_blocks and len(post_blocks) > 1:  # At least header + one post
            markdown_blocks.extend(post_blocks)
        else:
            logger.warning("No saved posts extracted from elements.")
            markdown_blocks.append("<!-- No saved posts extracted -->")

        # Join all blocks with double newlines to create final markdown
        markdown = "\n\n".join(markdown_blocks)

        # Check if result is effectively empty
        is_empty = (
            not markdown.strip()
            or markdown == f"# {page_title}\n\n<!-- No saved posts extracted -->"
        )

        if is_empty:
            logger.warning("Parsing resulted in effectively empty markdown after processing.")
            return "<!-- Parsing completed, but resulted in empty or placeholder output -->"

        logger.info(
            f"Instagram {page_title.lower()} HTML to markdown conversion completed successfully."
        )
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error processing Instagram saved collection HTML with unstructured",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error processing Instagram saved collection HTML with unstructured: {e}"
