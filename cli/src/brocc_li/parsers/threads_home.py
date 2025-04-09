from typing import Optional

from unstructured.documents.elements import Element, Image, Text
from unstructured.partition.html import partition_html

from brocc_li.utils.logger import logger


def threads_home_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Parses Threads home feed HTML using unstructured and converts it to Markdown.

    Args:
        html: The HTML content of the Threads home feed.
        debug: If True, enables detailed debug logging.

    Returns:
        A string containing the parsed content in Markdown format, or None if parsing fails.
    """
    try:
        logger.info("Starting Threads home HTML parsing...")
        if debug:
            logger.debug("Partitioning HTML with unstructured...")

        elements: list[Element] = partition_html(
            text=html,
            # Consider adding strategy='hi_res' if basic partitioning is insufficient
        )

        if debug:
            logger.debug(f"Received {len(elements)} elements from unstructured.")
            # Optional: Log first few elements for inspection
            # if elements:
            #     for i, el in enumerate(elements[:15]):
            #          logger.debug(f"Element {i}: type={type(el).__name__}, text='{str(el)[:100]}...'")

        # --- Basic Post Grouping and Markdown Conversion ---
        # This is a simple approach; might need refinement based on actual HTML structure.
        posts_markdown = []
        current_post_lines = []
        current_username = "Unknown User"  # Default username

        for i, element in enumerate(elements):
            element_text = str(element).strip()
            if not element_text:
                continue

            # Simplistic check for a potential username starting a post
            # TODO: Refine this heuristic - might need regex or checking element attributes/context
            # Assuming usernames are relatively short, single lines, possibly followed by metadata.
            is_potential_username = (
                isinstance(element, Text)
                and len(element_text) < 30  # Arbitrary length limit
                and "." not in element_text  # Avoid potential URLs/file names
                and "\n" not in element_text  # Single line
                and i + 1 < len(elements)  # Not the very last element
                # Add more checks? e.g., next element is timestamp?
            )

            # Heuristic: If we find a potential username AND the previous post wasn't empty,
            # start a new post.
            if is_potential_username and current_post_lines:
                # Save the previous post
                if any(
                    line.strip() and not line.startswith("*") for line in current_post_lines
                ):  # Check if post has actual content besides metadata
                    posts_markdown.append(
                        f"### Post by {current_username}\n\n" + "\n".join(current_post_lines)
                    )
                    if debug:
                        logger.debug(f"--- End Post (User: {current_username}) ---")
                current_post_lines = []  # Start new post lines
                current_username = element_text  # Assume this text is the username
                if debug:
                    logger.debug(
                        f"--- Start Post Detected (Potential User: {current_username}) ---"
                    )
                # Don't add the username itself directly here, it goes in the header

            elif isinstance(element, Image):
                img_url = getattr(element.metadata, "image_url", None)
                img_alt = getattr(
                    element.metadata, "text", "Image"
                )  # Use element text as alt if available
                if img_url:
                    current_post_lines.append(f"![{img_alt}]({img_url})")
                    if debug:
                        logger.debug(f"Added Image: {img_url}")
                elif debug:
                    logger.debug(f"Skipped Image element with no URL: {element_text[:100]}...")

            elif isinstance(element, Text):
                # TODO: Add metadata detection (timestamps, likes, replies etc.)
                # For now, just add text content. Filter very common noise.
                noise = ["reply", "like", "share", "view post", "more", "..."]
                if element_text.lower() not in noise and len(element_text) > 1:
                    # Basic formatting attempts (can be expanded)
                    if (
                        "ago" in element_text
                        or "h" == element_text[-1]
                        or "m" == element_text[-1]
                        or "d" == element_text[-1]
                    ):  # Potential timestamp
                        current_post_lines.append(f"* {element_text}")  # Format as metadata
                        if debug:
                            logger.debug(f"Added potential metadata: {element_text}")
                    else:
                        current_post_lines.append(element_text)  # Add as regular content
                        if debug:
                            logger.debug(f"Added Text: {element_text[:100]}...")
                elif debug:
                    logger.debug(f"Filtered Text: {element_text[:100]}...")

            # Handle other element types if necessary

        # Add the last post
        if current_post_lines and any(
            line.strip() and not line.startswith("*") for line in current_post_lines
        ):
            posts_markdown.append(
                f"### Post by {current_username}\n\n" + "\n".join(current_post_lines)
            )
            if debug:
                logger.debug(f"--- End Last Post (User: {current_username}) ---")

        if not posts_markdown:
            logger.warning("unstructured parsing resulted in no markdown posts after processing.")
            # Log elements if debug is enabled and no posts were found
            if debug and elements:
                logger.debug("Elements present but no posts generated. Logging first 20 elements:")
                for i, el in enumerate(elements[:20]):
                    logger.debug(
                        f"Element {i}: type={type(el).__name__}, text='{str(el)[:100]}...'"
                    )
                return "<!-- unstructured parsing completed, but resulted in empty output. Check debug logs for elements. -->"
            else:
                return "<!-- unstructured parsing completed, but resulted in empty output -->"

        # Join all post markdowns with separators
        markdown = "\n\n\n".join(posts_markdown)

        logger.info("Threads HTML to markdown conversion completed successfully.")
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error processing Threads HTML with unstructured",
            exc_info=True,
        )
        return f"Error processing Threads HTML with unstructured: {e}"


# Optional: Add helper functions for cleaning text, formatting timestamps etc. later
