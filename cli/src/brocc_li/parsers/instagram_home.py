from typing import Optional

from unstructured.documents.elements import Image, NarrativeText, Text

from brocc_li.parsers.instagram_utils import partition_instagram_html
from brocc_li.utils.logger import logger


def instagram_home_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        # Use shared utility function to partition HTML
        filtered_elements = partition_instagram_html(html, debug=debug)

        if not filtered_elements:
            logger.warning("No elements remaining after filtering.")
            return "<!-- No elements remaining after filtering -->"

        # Better post detection - search for profile picture sequences followed by timestamps
        posts = []
        current_post_elements = []
        current_username = None

        # First pass: identify posts by profile picture + username + timestamp pattern
        i = 0
        while i < len(filtered_elements) - 2:  # Need at least 3 elements to form a pattern
            element = filtered_elements[i]
            element_text = str(element).strip()

            # Pattern: profile picture + username + timestamp
            profile_pic_match = "profile picture" in element_text

            if profile_pic_match and i + 2 < len(filtered_elements):
                # Next element should be username
                username_element = filtered_elements[i + 1]
                username_text = str(username_element).strip()

                # Third element could be timestamp (like "5d", "1w")
                timestamp_element = filtered_elements[i + 2]
                timestamp_text = str(timestamp_element).strip()
                timestamp_match = len(timestamp_text) <= 4 and (
                    "d" in timestamp_text or "w" in timestamp_text or "h" in timestamp_text
                )

                if timestamp_match:
                    # We found a new post!
                    if current_post_elements and current_username:
                        # Save the previous post
                        posts.append(
                            {"username": current_username, "elements": current_post_elements}
                        )

                    # Extract username from profile picture text or username element
                    if profile_pic_match:
                        username = element_text.replace("'s profile picture", "").strip()
                    else:
                        username = username_text

                    if debug:
                        logger.debug(f"Found new post by {username} at element {i + 1}")

                    # Start a new post
                    current_username = username
                    current_post_elements = []

                    # Add these elements to the post
                    current_post_elements.append(element)  # Profile pic
                    current_post_elements.append(username_element)  # Username
                    current_post_elements.append(timestamp_element)  # Timestamp

                    # Skip the elements we just processed
                    i += 3
                    continue

            # If no pattern match, add to current post if we have one
            if current_username:
                current_post_elements.append(element)

            i += 1

        # Don't forget the last post
        if current_post_elements and current_username:
            posts.append({"username": current_username, "elements": current_post_elements})

        # Fallback if no posts were detected with the pattern approach
        if not posts and filtered_elements:
            # Try an alternative approach - look for clear post boundaries
            posts = []
            post_boundaries = []

            # Find all potential post boundaries (profile pictures)
            for i, element in enumerate(filtered_elements):
                element_text = str(element).strip()
                if "profile picture" in element_text:
                    post_boundaries.append(i)

            # Add sentinel at the end
            post_boundaries.append(len(filtered_elements))

            # Create posts based on boundaries
            for i in range(len(post_boundaries) - 1):
                start = post_boundaries[i]
                end = post_boundaries[i + 1]

                post_elements = filtered_elements[start:end]
                if post_elements:
                    first_element = post_elements[0]
                    first_text = str(first_element).strip()

                    # Extract username from profile picture text
                    if "profile picture" in first_text:
                        username = first_text.replace("'s profile picture", "").strip()
                        posts.append({"username": username, "elements": post_elements})

        if debug:
            logger.debug(f"Identified {len(posts)} posts")

        # Convert posts to markdown
        markdown_blocks = []

        for _post_idx, post in enumerate(posts):
            if "username" not in post or "elements" not in post:
                continue

            post_lines = []
            username = post.get("username", "")

            # Start with post header
            post_header = f"### Post by {username}"
            post_lines.append(post_header)

            # Process post elements
            seen_images = set()  # Track image descriptions to avoid duplication
            seen_text = set()  # Track text to avoid duplication
            likes_text = None
            has_content = False

            for element in post["elements"]:
                element_text = str(element).strip()
                if not element_text:
                    continue

                # Skip profile pictures and username repetitions
                if "profile picture" in element_text or element_text == username:
                    continue

                # Handle timestamp
                if len(element_text) <= 4 and any(t in element_text for t in ["d", "w", "h", "m"]):
                    post_lines.append(f"*Posted {element_text} ago*")
                    continue

                # Collect likes info for later
                if "likes" in element_text:
                    likes_text = element_text
                    continue

                # Process by element type
                if isinstance(element, Image):
                    # Avoid duplicate images
                    if element_text in seen_images:
                        continue

                    # Add image description if meaningful
                    if element_text and element_text not in seen_images:
                        # Extract just the photo attribution without excessive detail
                        if element_text.startswith("Photo by") or element_text.startswith(
                            "Photo shared by"
                        ):
                            parts = element_text.split(".")
                            if parts:
                                simplified_desc = parts[0].strip()
                                if simplified_desc not in seen_images:
                                    seen_images.add(simplified_desc)
                                    post_lines.append(f"*{simplified_desc}*")
                                    has_content = True
                        else:
                            seen_images.add(element_text)
                            post_lines.append(f"*{element_text}*")
                            has_content = True

                    # Add image URL
                    img_url = (
                        element.metadata.image_url
                        if hasattr(element.metadata, "image_url")
                        else None
                    )
                    if img_url and img_url not in seen_images:
                        seen_images.add(img_url)
                        post_lines.append(f"![Image]({img_url})")
                        has_content = True

                elif isinstance(element, (NarrativeText, Text)):
                    # Skip elements we've already seen
                    if element_text in seen_text:
                        continue

                    # Skip navigation elements
                    if element_text in ["more", "..."] or element_text.startswith("View all"):
                        continue

                    # Skip user profile names that might be floating (they're often tags)
                    if len(element_text) < 20 and "." in element_text and " " not in element_text:
                        continue

                    # Add the text content
                    seen_text.add(element_text)
                    post_lines.append(element_text)
                    has_content = True

            # Add likes at the end if collected
            if likes_text:
                post_lines.append(f"*{likes_text}*")

            # Only add posts that have actual content
            if has_content:
                markdown_blocks.append("\n\n".join(post_lines))

        # Join all blocks with triple newlines to create final markdown
        markdown = "\n\n\n".join(markdown_blocks)

        if not markdown.strip():
            logger.warning("unstructured parsing resulted in empty markdown after processing.")
            return "<!-- unstructured parsing completed, but resulted in empty output -->"

        logger.info("Instagram HTML to markdown conversion completed successfully.")
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error processing Instagram HTML with unstructured",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error processing Instagram HTML with unstructured: {e}"
