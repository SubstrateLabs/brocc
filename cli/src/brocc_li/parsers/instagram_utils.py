import re
from typing import Any, Dict, List, Optional, Set

from unstructured.documents.elements import Element, Image, ListItem, NarrativeText, Text, Title
from unstructured.partition.html import partition_html

from brocc_li.utils.logger import logger


def partition_instagram_html(html: str, debug: bool = False) -> List[Element]:
    """Parse Instagram HTML with unstructured and apply basic filtering"""
    logger.info("Starting Instagram HTML parsing with unstructured...")
    elements: List[Element] = partition_html(text=html)
    logger.info(f"unstructured found {len(elements)} raw elements.")

    if not elements:
        logger.warning("unstructured.partition_html returned no elements.")
        return []

    # Apply minimal filtering initially
    filtered_elements: List[Element] = []
    for i, element in enumerate(elements):
        element_text = str(element)
        # Very minimal filtering initially
        if element_text.strip() == "":
            if debug:
                logger.debug(f"Filtering empty element {i + 1}")
            continue
        filtered_elements.append(element)
        if debug:
            logger.debug(
                f"Element {i + 1} type: {type(element).__name__}, text: {element_text[:100]}..."
            )

    logger.info(f"Kept {len(filtered_elements)} elements after minimal filtering.")
    return filtered_elements


def clean_element_text(text: str, max_length: Optional[int] = None) -> str:
    """Clean element text of common noise patterns found in Instagram HTML."""
    if not text:
        return ""

    # Remove common noise characters
    cleaned = text.replace("·", "").strip()

    # Truncate if needed
    if max_length and len(cleaned) > max_length:
        return cleaned[:max_length] + "..."

    return cleaned


def is_timestamp(element: Element) -> bool:
    """Check if an element is likely an Instagram timestamp."""
    if not isinstance(element, Text):
        return False

    text = str(element).strip()
    time_indicators = ["w", "h", "m", "d", "ago", "now"]

    # Instagram timestamps are typically short with time indicators
    return len(text) < 15 and any(ind in text for ind in time_indicators)


def format_timestamp(text: str) -> str:
    """Format an Instagram timestamp string consistently."""
    if not text:
        return ""

    # Strip and add parentheses if not already present
    formatted = text.strip()
    if not (formatted.startswith("(") and formatted.endswith(")")):
        formatted = f"({formatted})"

    return formatted


def is_profile_picture(element: Element) -> bool:
    """Check if an element is an Instagram profile picture."""
    return isinstance(element, Image) and (
        "profile picture" in str(element).lower() or "User avatar" in str(element)
    )


def is_section_header(element: Element, headers: Optional[List[str]] = None) -> bool:
    """Check if an element is a section header."""
    if headers is None:
        headers = ["Primary", "General", "Requests", "Posts", "Reels", "Tagged"]

    return isinstance(element, Text) and str(element).strip() in headers


def _clean_feed_caption(caption: str) -> Optional[str]:
    """Clean up common noisy patterns in Instagram feed captions."""
    if not caption or len(caption) < 5:
        return None

    cleaned = caption
    # Remove common auto-generated prefixes/suffixes
    if (
        "Puede ser una imagen de" in cleaned
        or "No photo description available" in cleaned
        or "No hay ninguna descripción" in cleaned
    ):
        # Attempt to extract meaningful part if exists before auto-gen text
        parts = re.split(
            r"Puede ser una imagen de|No photo description available|No hay ninguna descripción",
            cleaned,
            maxsplit=1,
        )
        if len(parts) > 0 and len(parts[0].strip()) > 10:
            cleaned = parts[0].strip()
        else:
            return "Image"  # Return generic placeholder if only auto-text

    # Remove "Photo by USER on DATE." pattern if it's the main content
    if re.match(r"^Photo by [\w\s]+ on \w+ \d+, \d{4}\.?$", cleaned.strip(), re.IGNORECASE):
        return "Image"  # Assume it's just metadata

    # Further noise reduction
    cleaned = cleaned.replace("·", "").strip()

    # Return None if cleaning results in very short/empty string
    return cleaned if len(cleaned) > 3 else None


def _extract_hashtags(text: str) -> Set[str]:
    """Extract unique hashtags from text."""
    return set(re.findall(r"#\w+", text))


def process_instagram_feed_elements(
    elements: List[Element], debug: bool = False
) -> List[Dict[str, Any]]:
    """
    Processes unstructured elements from an Instagram feed page (Explore, Search, Saved)
    and groups them into structured posts. Handles images, text, basic metadata, and hashtags.
    """
    posts: List[Dict[str, Any]] = []
    current_post: Dict[str, Any] = {"text": [], "metadata": {}, "hashtags": set()}
    seen_image_urls: Set[str] = set()
    seen_captions: Set[str] = set()

    logger.info(f"Processing {len(elements)} elements for feed posts...")

    for i, element in enumerate(elements):
        element_text = str(element).strip()
        element_type = type(element).__name__

        if debug:
            logger.debug(f"Processing feed element {i}: {element_type} - {element_text[:60]}...")

        potential_new_post = False

        # Image often signals a new post or is the main content
        if isinstance(element, Image):
            img_url = (
                getattr(element.metadata, "image_url", None)
                if hasattr(element, "metadata")
                else None
            )

            # Check if image URL is unique, treat as new post if so
            if img_url and img_url not in seen_image_urls:
                potential_new_post = True
                seen_image_urls.add(img_url)
                current_post["metadata"]["image_url"] = img_url
                if debug:
                    logger.debug(f"Found new image URL: {img_url[:60]}...")
            elif not img_url and element_text and len(element_text) > 10:
                # Use text as a proxy if URL missing but text is unique/long enough
                if element_text not in seen_captions:
                    potential_new_post = True

            if potential_new_post and (
                current_post["text"] or len(current_post["metadata"]) > 1
            ):  # >1 because image_url was just added
                # Finalize previous post before starting new one
                all_text = "\n".join(current_post["text"])
                current_post["hashtags"].update(_extract_hashtags(all_text))
                posts.append(current_post)
                if debug:
                    logger.debug(f"Finalized post {len(posts)}. Starting new post.")
                current_post = {
                    "text": [],
                    "metadata": {"image_url": img_url} if img_url else {},
                    "hashtags": set(),
                }
                seen_captions = set()  # Reset captions for new post

            # Process image caption text
            caption = _clean_feed_caption(element_text)
            if caption and caption not in seen_captions:
                current_post["text"].append(caption)
                seen_captions.add(caption)
                if debug:
                    logger.debug(f"Added image caption: {caption[:60]}...")

        # Look for metadata like counts, usernames in ListItems or short Text
        elif isinstance(element, ListItem) or (
            isinstance(element, Text) and len(element_text) < 20
        ):
            # Simple count check (likes/views/comments)
            count_match = re.match(r"^([\d,]+\.?\d*[KM]?)$", element_text)
            if count_match:
                current_post["metadata"]["count"] = count_match.group(1)
                if debug:
                    logger.debug(f"Found count metadata: {count_match.group(1)}")
            # Potential username / 'From' field
            elif element_text.startswith("@") or "profile" in element_text.lower():
                current_post["metadata"]["user"] = element_text
                if debug:
                    logger.debug(f"Found user metadata: {element_text}")

        # Handle narrative text, titles, etc. as post content
        elif isinstance(element, (NarrativeText, Text, Title)):
            # Skip very short or generic UI text
            if len(element_text) > 3 and element_text.lower() not in [
                "posts",
                "reels",
                "explore",
                "saved",
                "search",
                "primary",
                "general",
                "requests",
            ]:
                cleaned_text = clean_element_text(element_text)  # Use basic clean first
                # Use more specific caption cleaning too
                final_text = _clean_feed_caption(cleaned_text)
                if final_text and final_text not in seen_captions:
                    current_post["text"].append(final_text)
                    seen_captions.add(final_text)
                    if debug:
                        logger.debug(f"Added text content: {final_text[:60]}...")

    # Append the last post if it has content
    if current_post["text"] or len(current_post["metadata"]) > 0:
        all_text = "\n".join(current_post["text"])
        current_post["hashtags"].update(_extract_hashtags(all_text))
        # Ensure we have at least text or a unique image url
        if current_post["text"] or current_post["metadata"].get("image_url"):
            posts.append(current_post)
            if debug:
                logger.debug(f"Finalized last post {len(posts)}.")

    logger.info(f"Processed feed elements into {len(posts)} posts.")
    return posts


def format_feed_posts_to_md(posts: List[Dict[str, Any]], section_title: str = "Posts") -> List[str]:
    """Formats a list of processed feed posts into Markdown blocks.

    Args:
        posts: List of post dictionaries from process_instagram_feed_elements.
        section_title: The title for the Markdown section (e.g., '## Posts').

    Returns:
        A list of strings, where each string is a Markdown block
        (section header, post header, post content, etc.).
    """
    if not posts:
        # Return list containing header and placeholder comment
        return [f"## {section_title}", "<!-- No posts extracted -->"]

    markdown_blocks = [f"## {section_title}"]

    for idx, post in enumerate(posts, 1):
        post_content_blocks = []  # Store content parts (text, metadata, image, tags)

        # Add user info if available
        if "user" in post.get("metadata", {}):
            post_content_blocks.append(f"**From**: {post['metadata']['user']}")

        # Add post text
        if post.get("text"):
            # Join the list of text lines into a single block
            post_content_blocks.append("\n".join(post["text"]))

        # Add metadata if available (e.g., engagement count)
        if "count" in post.get("metadata", {}):
            post_content_blocks.append(f"**{post['metadata']['count']}** likes/views")

        # Add image URL if available
        if "image_url" in post.get("metadata", {}):
            url = post["metadata"]["image_url"]
            # Simple truncation for display
            display_url = url[:80] + "[...]" if len(url) > 83 else url
            post_content_blocks.append(f"![Image]({display_url})")

        # Add hashtags section if found
        if post.get("hashtags"):
            # Join the set of hashtags into a space-separated string
            post_content_blocks.append(f"**Tags**: {' '.join(sorted(post['hashtags']))}")

        # Construct the full markdown for this post IF it has content parts
        if post_content_blocks:
            # Start with the header, then join the content blocks with double newlines
            full_post_md = f"### Post {idx}\n\n" + "\n\n".join(post_content_blocks)
            markdown_blocks.append(full_post_md)

    # Ensure we always return a list. If only the header was added, add a comment.
    if len(markdown_blocks) == 1:
        markdown_blocks.append("<!-- Posts processed, but no content to display -->")

    return markdown_blocks


def common_instagram_parser(
    html: str,
    page_title: str,
    section_title: str = "Posts",
    debug: bool = False,
    preprocess_fn=None,
    empty_warning_msg: str = "No posts extracted from elements.",
    empty_placeholder_msg: str = "<!-- No posts extracted -->",
) -> str:
    """
    Common Instagram HTML parser function that handles the typical flow of parsing,
    extracting posts, and formatting to markdown.

    Args:
        html: The raw HTML string to parse
        page_title: The title to use for the page (without markdown symbols)
        section_title: Title for the posts section (without markdown symbols)
        debug: Enable debug logging
        preprocess_fn: Optional function to preprocess elements before processing posts.
                      Should take (elements, debug) and return (elements, custom_data).
        empty_warning_msg: Warning message to log if no posts are extracted
        empty_placeholder_msg: Placeholder HTML comment for empty results

    Returns:
        Formatted markdown string
    """
    try:
        logger.info(f"Starting Instagram {page_title.lower()} parsing")

        # Partition HTML using shared utility function
        filtered_elements = partition_instagram_html(html, debug=debug)

        if not filtered_elements:
            logger.warning("No elements remaining after filtering.")
            return "<!-- No elements remaining after filtering -->"

        # Optional preprocessing of elements
        custom_data = None
        if preprocess_fn:
            filtered_elements, custom_data = preprocess_fn(filtered_elements, debug)

            # Check if custom_data contains a page_title override
            if isinstance(custom_data, dict) and "page_title" in custom_data:
                page_title = custom_data["page_title"]
                if debug:
                    logger.debug(f"Using custom page title from preprocessor: {page_title}")

        # Process elements into structured posts
        posts = process_instagram_feed_elements(filtered_elements, debug=debug)

        # Build markdown output
        markdown_blocks = [f"# {page_title}"]

        # Add any custom data before posts section
        if custom_data:
            if isinstance(custom_data, str):
                markdown_blocks.append(custom_data)
            elif isinstance(custom_data, list):
                markdown_blocks.extend(custom_data)
            elif isinstance(custom_data, dict) and "description" in custom_data:
                markdown_blocks.append(custom_data["description"])

        # Format posts to markdown
        post_blocks = format_feed_posts_to_md(posts, section_title=section_title)
        if post_blocks and len(post_blocks) > 1:  # At least header + one post
            markdown_blocks.extend(post_blocks)
        else:
            logger.warning(empty_warning_msg)
            markdown_blocks.append(empty_placeholder_msg)

        # Join all blocks with double newlines to create final markdown
        markdown = "\n\n".join(markdown_blocks)

        # Check if result is effectively empty
        is_empty = not markdown.strip() or markdown == f"# {page_title}\n\n{empty_placeholder_msg}"

        if is_empty:
            logger.warning("Parsing resulted in effectively empty markdown after processing.")
            return "<!-- Parsing completed, but resulted in empty or placeholder output -->"

        logger.info(
            f"Instagram {page_title.lower()} HTML to markdown conversion completed successfully."
        )
        return markdown.strip()

    except Exception as e:
        logger.error(
            f"Error processing Instagram {page_title.lower()} HTML with unstructured",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error processing Instagram {page_title.lower()} HTML with unstructured: {e}"
