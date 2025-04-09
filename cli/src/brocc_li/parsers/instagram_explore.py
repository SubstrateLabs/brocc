import re

from unstructured.documents.elements import Image, ListItem, NarrativeText, Text, Title

from brocc_li.parsers.instagram_utils import (
    clean_element_text,
    partition_instagram_html,
    process_instagram_feed_elements,
)
from brocc_li.utils.logger import logger


def instagram_explore_html_to_md(html: str, debug: bool = False) -> str:
    try:
        logger.info("Starting Instagram explore page parsing")

        # Partition HTML using shared utility function
        filtered_elements = partition_instagram_html(html, debug=debug)

        if not filtered_elements:
            logger.warning("No elements remaining after filtering.")
            return "<!-- No elements remaining after filtering -->"

        # Process elements into structured posts using the utility function
        posts = process_instagram_feed_elements(filtered_elements, debug=debug)

        # Build markdown output
        markdown_blocks = ["# Instagram Explore"]

        # Add all collected posts to markdown
        if posts:
            posts_section = ["## Posts"]

            for idx, post in enumerate(posts, 1):
                post_md = [f"### Post {idx}"]

                # Add user info if available (might be present in explore)
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
            logger.warning("No posts extracted from elements.")
            markdown_blocks.append("<!-- No posts extracted -->")

        # Join all blocks with double newlines to create final markdown
        markdown = "\n\n".join(markdown_blocks)

        if not markdown.strip() or markdown == "# Instagram Explore\n\n<!-- No posts extracted -->":
            logger.warning("Parsing resulted in effectively empty markdown after processing.")
            return "<!-- Parsing completed, but resulted in empty or placeholder output -->"

        logger.info("Instagram explore HTML to markdown conversion completed successfully.")
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error processing Instagram explore HTML with unstructured",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error processing Instagram explore HTML with unstructured: {e}"
