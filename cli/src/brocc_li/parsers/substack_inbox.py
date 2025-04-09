from typing import Dict, List, Optional

from unstructured.documents.elements import Element
from unstructured.partition.html import partition_html

from brocc_li.parsers.substack_utils import extract_element_url
from brocc_li.utils.logger import logger


def _is_newsletter_name(text: str) -> bool:
    """Check if text looks like a newsletter name using general patterns"""
    text = text.strip()

    # Too long to be a newsletter name
    if len(text) > 40:
        return False

    # Common newsletter name patterns
    if "Newsletter" in text:
        return True

    # Possessive name pattern (e.g., "Kyla's", "Matt's")
    if "'" in text and len(text.split()) <= 3:
        return True

    # Publication-style names (typically short)
    if len(text.split()) <= 2 and len(text) < 20:
        # Look for capitalized words that could be publication names
        words = text.split()
        if all(word[0].isupper() for word in words if len(word) > 1):
            return True

    return False


def substack_inbox_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Parses the HTML content of Substack Inbox into Markdown.

    This parser converts the unstructured output to markdown,
    with proper formatting for newsletter items.
    """
    logger.info("Starting Substack Inbox HTML processing...")
    try:
        # Partition the HTML using unstructured
        elements: List[Element] = partition_html(text=html)
        logger.info(f"unstructured found {len(elements)} raw elements.")

        if debug:
            logger.debug("Raw Substack Inbox elements:")
            for i, element in enumerate(elements[:20]):  # Limit to first 20 elements
                logger.debug(
                    f"  Raw Element {i + 1}: {type(element).__name__} - {str(element)[:50]}..."
                )
            if len(elements) > 20:
                logger.debug(f"  ... and {len(elements) - 20} more elements")

        if not elements:
            logger.warning("unstructured.partition_html returned no elements.")
            return "<!-- unstructured found no elements -->"

        # --- Group Elements into Post Items --- #
        posts = []
        current_post: Dict[str, Optional[str]] = {}

        i = 0
        while i < len(elements):
            element = elements[i]
            element_text = str(element).strip()
            element_type = type(element).__name__

            if debug:
                logger.debug(f"Processing element {i}: {element_type} - {element_text[:50]}...")

            # Start of a new post if we see a newsletter name
            if _is_newsletter_name(element_text) and i + 1 < len(elements):
                # Save previous post if it has a title
                if current_post.get("title"):
                    posts.append(current_post)

                # Start new post
                current_post = {
                    "newsletter": element_text,
                    "url": extract_element_url(element, url_type="link"),
                }

                # Next element is usually the date
                if i + 1 < len(elements):
                    date_element = elements[i + 1]
                    date_text = str(date_element).strip()
                    if len(date_text) < 15 and not date_text.endswith("min read"):  # Likely a date
                        current_post["date"] = date_text
                        i += 1  # Skip the date element in next iteration

            # Article title (after newsletter and date)
            elif "title" not in current_post and element_text and i > 1:
                # Capture URL if present
                url = extract_element_url(element, url_type="link")
                if url:
                    current_post["url"] = url

                current_post["title"] = element_text

            # Article description (usually NarrativeText after title)
            elif (
                "title" in current_post
                and element_type == "NarrativeText"
                and "description" not in current_post
            ):
                current_post["description"] = element_text

            # Author and read time (usually after title/description)
            elif "∙" in element_text and "min read" in element_text:
                current_post["author_read_time"] = element_text

            i += 1

        # Add the last post if not empty
        if current_post.get("title"):
            posts.append(current_post)

        if debug:
            logger.debug(f"Grouped elements into {len(posts)} posts")

        # --- Convert to Markdown --- #
        markdown_parts = []

        # Add a title
        markdown_parts.append("# Substack Inbox\n")

        # Format each post
        for post in posts:
            # Create title with optional link
            title = post.get("title", "Untitled Post")
            url = post.get("url")

            if url:
                markdown_parts.append(f"### [{title}]({url})")
            else:
                markdown_parts.append(f"### {title}")

            # Add metadata as bullet points
            if post.get("newsletter"):
                markdown_parts.append(f"- **Newsletter**: {post['newsletter']}")

            if post.get("date"):
                markdown_parts.append(f"- **Date**: {post['date']}")

            if post.get("author_read_time"):
                markdown_parts.append(f"- **Author**: {post['author_read_time']}")

            if post.get("description"):
                markdown_parts.append(f"- **Description**: {post['description']}")

            # Add spacing between posts
            markdown_parts.append("")

        # Join all parts with newlines for readability
        result_md = "\n".join(markdown_parts)

        logger.info("Successfully processed Substack Inbox HTML.")
        if debug:
            logger.debug(f"Final markdown structure contains {len(result_md.splitlines())} lines")

        return result_md.strip()

    except Exception as e:
        logger.error(
            "Error processing Substack Inbox HTML with unstructured",
            exc_info=True,
        )
        return f"Error processing Substack Inbox HTML: {e}"
