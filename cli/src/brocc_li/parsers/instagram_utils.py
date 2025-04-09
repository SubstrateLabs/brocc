from typing import List, Optional, Dict, Any, Set
import re

from unstructured.documents.elements import Element, Image, Text, ListItem, NarrativeText, Title
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
