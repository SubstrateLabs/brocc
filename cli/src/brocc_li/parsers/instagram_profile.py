import re
from typing import Dict, List, Optional

from unstructured.documents.elements import Element, Image, NarrativeText, Text, Title

from brocc_li.parsers.instagram_utils import (
    clean_element_text,
    is_profile_picture,
    partition_instagram_html,
)
from brocc_li.utils.logger import logger


def _extract_og_description_stats(html: str, debug: bool = False) -> Dict[str, Optional[str]]:
    """Extract stats from the og:description meta tag using regex."""
    stats: Dict[str, Optional[str]] = {"followers": None, "following": None, "posts": None}
    og_desc_pattern = (
        r'<meta property="og:description" content="([^"]+)">'  # Adjusted pattern to be less greedy
    )
    match = re.search(og_desc_pattern, html)
    if match:
        content = match.group(1)
        if debug:
            logger.debug(f"Found og:description content: {content}")

        # Extract numbers using regex on the content string
        followers_match = re.search(r"([\d,]+)\s+Followers", content)
        following_match = re.search(r"([\d,]+)\s+Following", content)
        posts_match = re.search(r"([\d,]+)\s+Posts", content)

        if followers_match:
            stats["followers"] = followers_match.group(1)
            if debug:
                logger.debug(f"Extracted followers count from meta: {stats['followers']}")
        if following_match:
            stats["following"] = following_match.group(1)
            if debug:
                logger.debug(f"Extracted following count from meta: {stats['following']}")
        if posts_match:
            stats["posts"] = posts_match.group(1)
            if debug:
                logger.debug(f"Extracted posts count from meta: {stats['posts']}")
    elif debug:
        logger.warning("og:description meta tag not found.")

    return stats


def instagram_profile_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        # Extract stats from meta tag first
        meta_stats = _extract_og_description_stats(html, debug=debug)
        posts_count = meta_stats.get("posts")
        followers_count = meta_stats.get("followers")
        following_count = meta_stats.get("following")

        # Use shared utility function to partition HTML
        filtered_elements = partition_instagram_html(html, debug=debug)

        if not filtered_elements:
            logger.warning("No elements remaining after filtering.")
            return "<!-- No elements remaining after filtering -->"

        # Extract profile information
        profile_info = {}
        bio_elements: List[Element] = []
        profile_pic_element_idx = -1
        username_idx = -1  # Index where username was found
        posts_start_idx = -1  # Index of "Posts"/"Reels" tab

        # First pass: identify key elements and sections
        for i, element in enumerate(filtered_elements):
            element_text = str(element).strip()

            # Find profile picture element (usually the first image)
            if is_profile_picture(element) and profile_pic_element_idx == -1:
                profile_pic_element_idx = i
                if debug:
                    logger.debug(f"Found profile picture element at index {i}")

            # Look for username (Title element usually after profile pic)
            # Check if it's a Title and comes *after* the profile pic index (if found)
            if (
                isinstance(element, Title)
                and (profile_pic_element_idx == -1 or i > profile_pic_element_idx)
                and "username" not in profile_info
            ):
                if element_text and "@" not in element_text and element_text.count(" ") < 3:
                    profile_info["username"] = element_text
                    username_idx = i  # Store index
                    if debug:
                        logger.debug(f"Found username: {element_text} at index {i}")

            # Find start of posts section (usually text like "Posts", "Reels", "Tagged")
            if (
                isinstance(element, Text)
                and element_text.lower() in ["posts", "reels", "tagged"]
                and posts_start_idx == -1
            ):
                posts_start_idx = i
                if debug:
                    logger.debug(
                        f"Found start of posts section marker: '{element_text}' at index {i}"
                    )

        # Collect bio elements (NarrativeText/Text between username and posts start)
        # Also backup bio search by looking for bio-like text throughout
        backup_bio_elements = []
        for i, element in enumerate(filtered_elements):
            element_text = str(element).strip().lower()
            # Look for typical bio phrases
            if isinstance(element, (NarrativeText, Text)) and (
                ("writer" in element_text and "x" in element_text)
                or ("bio" in element_text)
                or ("followed by" in element_text)
                or ("posts" in element_text and "followers" in element_text)
                or element_text.startswith("@")
            ):
                backup_bio_elements.append(element)
                if debug:
                    logger.debug(
                        f"Found potential bio element (backup method): {element_text} at index {i}"
                    )

        # Main method for bio collection - between username and posts section
        if username_idx != -1 and posts_start_idx != -1:
            potential_bio_elements = filtered_elements[username_idx + 1 : posts_start_idx]
            for element in potential_bio_elements:
                element_text = str(element).strip()
                # Basic filtering for bio elements
                # Exclude elements that look like stats (redundant now) or nav items
                if (
                    isinstance(element, (NarrativeText, Text))
                    and len(element_text) > 3
                    and not re.match(
                        r"^[\d,]+\s+(posts|followers|following)$", element_text, re.IGNORECASE
                    )
                    and element_text.lower() not in ["edit profile", "share profile"]
                    and "followed by" not in element_text.lower()
                ):
                    bio_elements.append(element)
                    if debug:
                        logger.debug(f"Adding potential bio element: {element_text}")
        elif debug:
            logger.debug(
                f"Could not reliably determine bio range. Username Index: {username_idx}, Posts Start Index: {posts_start_idx}"
            )

        # If no bio elements found through main method, use backup bio elements
        if not bio_elements and backup_bio_elements:
            if debug:
                logger.debug(
                    "Using backup bio elements since no bio elements found through main method"
                )
            bio_elements = backup_bio_elements

        # Format profile information as markdown
        markdown_blocks = []

        # Add profile header
        username = profile_info.get("username", "Unknown User")
        markdown_blocks.append(f"# {username}")

        # Add stats if available (using values from meta tag)
        stats = []
        if posts_count:
            stats.append(f"**Posts**: {posts_count}")
        if followers_count:
            stats.append(f"**Followers**: {followers_count}")
        if following_count:
            stats.append(f"**Following**: {following_count}")

        if stats:
            markdown_blocks.append(" | ".join(stats))

        # Add bio
        if bio_elements:
            bio_text = []
            seen_text = set()

            for element in bio_elements:
                element_text = str(element).strip()
                if element_text and element_text not in seen_text:
                    # Attempt to clean up potential duplicates / less meaningful bio parts
                    # Example: Skip simple repetitions of username or handle
                    if element_text.lower() == username.lower():
                        continue
                    # Skip short potential mentions or links if they seem redundant
                    if element_text.startswith("@") and len(element_text) < 20:
                        continue
                    if element_text.startswith("http") and len(element_text) < 30:
                        # Allow if it's the only bio element, otherwise skip short links
                        if len(bio_elements) > 1:
                            continue

                    seen_text.add(element_text)
                    bio_text.append(element_text)

            if bio_text:
                markdown_blocks.append("\n".join(bio_text))

        # Extract recent posts (simplistic approach, skipping profile pic)
        markdown_blocks.append("## Recent Posts")

        image_count = 0
        seen_images = set()
        # Start looking for posts after the posts section marker, or after username if marker not found
        start_index_for_posts = posts_start_idx + 1 if posts_start_idx != -1 else username_idx + 1
        if start_index_for_posts <= profile_pic_element_idx and profile_pic_element_idx != -1:
            start_index_for_posts = profile_pic_element_idx + 1  # Ensure we start after profile pic

        if start_index_for_posts >= len(filtered_elements):
            logger.warning("Calculated post start index is out of bounds.")
            start_index_for_posts = max(
                0, len(filtered_elements) - 20
            )  # Fallback: look at last few elements

        for i, element in enumerate(
            filtered_elements[start_index_for_posts:], start=start_index_for_posts
        ):
            # Skip the profile picture element explicitly if it wasn't filtered
            if i == profile_pic_element_idx:
                if debug:
                    logger.debug(f"Skipping profile pic element index {i} during post processing.")
                continue

            if isinstance(element, Image):
                element_text = str(element).strip()

                # Basic check to avoid adding profile pic again if logic failed above
                if is_profile_picture(element):
                    continue

                if element_text in seen_images:
                    continue

                seen_images.add(element_text)
                image_count += 1

                # Add image description if meaningful
                if element_text:
                    # Clean up generic descriptions
                    if (
                        "No photo description available" in element_text
                        or "No hay ninguna descripción" in element_text
                    ):
                        clean_text = f"Post {image_count} - Image"
                    else:
                        # Keep original description but maybe shorten if too long? Currently keeping full.
                        clean_text = clean_element_text(element_text)
                    markdown_blocks.append(f"### Post {image_count}")
                    markdown_blocks.append(f"*{clean_text}*")

                # Add image URL if available
                img_url = (
                    getattr(element.metadata, "image_url", None)
                    if hasattr(element, "metadata")
                    else None
                )
                if img_url:
                    markdown_blocks.append(f"![Image]({img_url})")

        # Join all blocks with double newlines to create final markdown
        markdown = "\n\n".join(markdown_blocks)

        if not markdown.strip():
            logger.warning("unstructured parsing resulted in empty markdown after processing.")
            return "<!-- unstructured parsing completed, but resulted in empty output -->"

        logger.info("Instagram profile HTML to markdown conversion completed successfully.")
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error processing Instagram profile HTML with unstructured",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error processing Instagram profile HTML with unstructured: {e}"
