from typing import List, Optional, Set

from unstructured.documents.elements import Image, ListItem, NarrativeText, Text, Title

from brocc_li.parsers.instagram_utils import (
    partition_instagram_html,
    process_instagram_feed_elements,
)
from brocc_li.utils.logger import logger


def _truncate_image_url(url: str) -> str:
    """Truncate very long image URLs to a reasonable length."""
    if len(url) > 100:
        # Keep the domain and beginning part of the URL, plus truncation indicator
        parts = url.split("?", 1)
        base_url = parts[0]
        if len(base_url) > 80:
            base_url = base_url[:80]
        return f"{base_url}[...]"
    return url


def instagram_explore_search_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """Convert Instagram explore/search HTML to Markdown."""
    try:
        # Use shared utility function to partition HTML
        filtered_elements = partition_instagram_html(html, debug=debug)

        if not filtered_elements:
            logger.warning("No elements remaining after filtering.")
            return "<!-- No elements remaining after filtering -->"

        # Process elements into structured posts using the utility function
        posts = process_instagram_feed_elements(filtered_elements, debug=debug)

        # Format as markdown
        markdown_blocks = ["# Instagram Search Results"]

        # Add all collected posts to markdown
        if posts:
            posts_section = ["## Posts"]

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

                # Add image URL if available, truncating if necessary
                if "image_url" in post["metadata"]:
                    truncated_url = _truncate_image_url(post["metadata"]["image_url"])
                    post_md.append(f"![Image]({truncated_url})")

                # Add hashtags section if found
                if post["hashtags"]:
                    post_md.append(f"**Tags**: {' '.join(sorted(list(post['hashtags'])))}")

                # Add the complete post section
                posts_section.append("\n\n".join(post_md))

            markdown_blocks.extend(posts_section)
        else:
            logger.warning("No search result posts extracted from elements.")
            markdown_blocks.append("<!-- No search result posts extracted -->")

        # Join all blocks with double newlines to create final markdown
        markdown = "\n\n".join(markdown_blocks)

        if (
            not markdown.strip()
            or markdown == "# Instagram Search Results\n\n<!-- No search result posts extracted -->"
        ):
            logger.warning("unstructured parsing resulted in empty markdown after processing.")
            return "<!-- unstructured parsing completed, but resulted in empty output -->"

        logger.info("Instagram explore/search HTML to markdown conversion completed successfully.")
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error processing Instagram explore/search HTML with unstructured",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error processing Instagram explore/search HTML with unstructured: {e}"
