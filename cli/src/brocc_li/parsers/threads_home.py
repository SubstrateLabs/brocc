import re  # Import regex
from typing import List, Optional
from urllib.parse import urlparse

# Use Image type for checking
from unstructured.documents.elements import Element, Image, NarrativeText, Text
from unstructured.partition.html import partition_html

# Use our Threads-specific utils
from brocc_li.parsers.threads_utils import (
    clean_element_text,
    clean_username,
    deduplicate_image_urls,
    deduplicate_text_blocks,
    extract_links_from_metadata,
    extract_profile_url,
    format_markdown_links,
    is_profile_picture,
    is_timestamp,
)
from brocc_li.parsers.unstructured_utils import is_element_noisy
from brocc_li.utils.logger import logger

# Threads-specific noise patterns (expand as needed)
THREADS_NOISE = [
    "What's new?",
    "Your online status is now visible to others",
    "For public profiles, anyone can see this.",
    "For private profiles, only followers can see this.",
    "Manage",
    "Follow",
    "Following",
    "Suggested for you",
    "Show 2 more",
    # Common interaction words
    "like",
    "reply",
    "repost",
    "share",
    "view post",
    "more",
    "...",
]


# --- Helper to Merge Consecutive Text Elements ---
def merge_consecutive_text(elements: List[Element], debug: bool = False) -> List[Element]:
    if not elements:
        return []

    merged: List[Element] = []
    buffer = ""
    first_text_element = None

    for element in elements:
        is_text = isinstance(element, (Text, NarrativeText))
        if is_text:
            text = str(element).strip()
            if text:
                if not buffer:
                    first_text_element = element  # Keep metadata of the first element
                buffer += text + " "  # Add space between merged parts
        else:
            # If we encounter a non-text element, flush the buffer
            if buffer and first_text_element:
                if debug:
                    logger.debug(f"Merging text buffer: '{buffer.strip()[:100]}...'")
                merged_element = Text(text=buffer.strip(), metadata=first_text_element.metadata)
                merged.append(merged_element)
                buffer = ""
                first_text_element = None
            # Add the non-text element
            merged.append(element)

    # Flush any remaining buffer at the end
    if buffer and first_text_element:
        if debug:
            logger.debug(f"Merging final text buffer: '{buffer.strip()[:100]}...'")
        merged_element = Text(text=buffer.strip(), metadata=first_text_element.metadata)
        merged.append(merged_element)

    return merged


# --- Helper to Find Next Post Start --- #
def find_next_post_start(elements: List[Element], start_index: int, debug: bool = False) -> int:
    """Find the index of the next element that looks like a profile picture starting a post."""
    for i in range(start_index, len(elements)):
        element = elements[i]
        if is_profile_picture(element) and i + 1 < len(elements):
            potential_username_element = elements[i + 1]
            potential_username_text = str(potential_username_element).strip()
            is_likely_username = (
                isinstance(potential_username_element, Text)
                and len(potential_username_text) > 1
                and len(potential_username_text) < 35
                and not is_timestamp(potential_username_element, debug=False)
            )
            if is_likely_username:
                if debug:
                    logger.debug(f"find_next_post_start: Found next post indicator at index {i}")
                return i
    if debug:
        logger.debug(
            f"find_next_post_start: No further post indicators found after index {start_index}"
        )
    return len(elements)  # Return end of list if no more posts found


def threads_home_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        if debug:
            logger.debug("Partitioning HTML with unstructured (strategy=hi_res)...")

        elements: list[Element] = partition_html(text=html, strategy="hi_res")

        if debug:
            logger.debug(f"Received {len(elements)} elements from partition_html.")
            # Log initial elements summary
            element_types = {}
            for el in elements:
                el_type = type(el).__name__
                element_types[el_type] = element_types.get(el_type, 0) + 1

                # Log image elements specifically
                if isinstance(el, Image):
                    img_url = getattr(el.metadata, "image_url", None)
                    img_text = str(el)[:100] + "..." if len(str(el)) > 100 else str(el)
                    logger.debug(f"  IMAGE FOUND: text='{img_text}', url={img_url}")

                # v10: Check for links in metadata
                link_url = extract_links_from_metadata(el)
                if link_url:
                    logger.debug(
                        f"  LINK FOUND IN METADATA: element_type={el_type}, text='{str(el)[:50]}...', url={link_url}"
                    )

            logger.debug(f"Element type counts: {element_types}")

            # v10: Log sample elements with their metadata to understand structure
            logger.debug("--- Element Metadata Sample ---")
            for i, el in enumerate(elements[:10]):
                try:
                    if hasattr(el, "metadata"):
                        metadata = (
                            el.metadata.__dict__
                            if hasattr(el.metadata, "__dict__")
                            else str(el.metadata)
                        )
                        logger.debug(f"Element {i} ({type(el).__name__}) metadata: {metadata}")
                except Exception as e:
                    logger.debug(f"Error accessing metadata for element {i}: {e}")
            logger.debug("--- End Element Metadata Sample ---")

        # --- Filter Noise (v8: But preserve timestamps and links) --- #
        filtered_elements = []
        if debug:
            logger.debug("--- Filtering Noisy Elements (v8) ---")
        for element in elements:
            if not is_element_noisy(element, THREADS_NOISE, debug=debug):
                filtered_elements.append(element)
        if debug:
            logger.debug(f"Elements remaining after noise filtering: {len(filtered_elements)}")
            # Count image elements after filtering
            image_count = sum(1 for el in filtered_elements if isinstance(el, Image))
            logger.debug(f"Images remaining after filtering: {image_count}")

        if not filtered_elements:
            logger.warning("No elements remaining after initial noise filtering.")
            return "<!-- No elements remaining after filtering -->"

        # --- Post Grouping Logic (V9: with clean usernames) --- #
        posts = []
        current_index = 0
        while current_index < len(filtered_elements):
            element = filtered_elements[current_index]

            profile_pic_match = is_profile_picture(element)
            potential_username_element = (
                filtered_elements[current_index + 1]
                if current_index + 1 < len(filtered_elements)
                else None
            )
            is_likely_username_start = False
            username_text = ""

            if profile_pic_match and potential_username_element:
                username_text_candidate = str(potential_username_element).strip()
                # Clean username text if needed
                cleaned_username = clean_username(username_text_candidate)

                if (
                    isinstance(potential_username_element, Text)
                    and len(cleaned_username) > 1
                    and len(cleaned_username) < 35
                    and not is_timestamp(potential_username_element, debug=False)
                ):
                    is_likely_username_start = True
                    username_text = cleaned_username

            if is_likely_username_start:
                post_start_index = current_index
                if debug:
                    logger.debug(
                        f"--- Potential Post Start --- Index: {post_start_index}, User: {username_text}"
                    )

                # Extract profile URL from the profile picture element
                profile_url = extract_profile_url(element)
                if debug and profile_url:
                    logger.debug(f"  Extracted profile URL: {profile_url}")

                # Check for optional timestamp immediately after username
                timestamp_offset = 2  # Index relative to profile pic
                potential_timestamp_element = (
                    filtered_elements[post_start_index + timestamp_offset]
                    if post_start_index + timestamp_offset < len(filtered_elements)
                    else None
                )
                timestamp_found_early = (
                    is_timestamp(potential_timestamp_element, debug=debug)
                    if potential_timestamp_element
                    else False
                )
                content_start_offset = (
                    timestamp_offset + 1 if timestamp_found_early else timestamp_offset
                )

                # Find the start of the *next* post to determine the end of this one
                next_post_start_index = find_next_post_start(
                    filtered_elements, post_start_index + 1, debug=debug
                )
                if debug:
                    logger.debug(f" -> Next post starts at index: {next_post_start_index}")

                # Extract elements for this post (content elements start *after* the profile pic+username+optional timestamp)
                post_content_elements = filtered_elements[
                    post_start_index + content_start_offset : next_post_start_index
                ]

                # Log post elements if debugging
                if debug:
                    post_images = [el for el in post_content_elements if isinstance(el, Image)]
                    if post_images:
                        logger.debug(f" -> Post has {len(post_images)} image elements")
                        for i, img in enumerate(post_images):
                            img_url = getattr(img.metadata, "image_url", None)
                            logger.debug(f"    Post image {i}: url={img_url or 'NONE'}")
                    else:
                        logger.debug(" -> Post has NO image elements")

                    logger.debug(
                        f" -> Associating {len(post_content_elements)} content elements with user {username_text}"
                    )

                # Add the found post
                post_data = {
                    "username": username_text,
                    "profile_url": profile_url,  # Add profile URL to post data
                    "elements": post_content_elements,
                }

                # Add the early timestamp if found
                if timestamp_found_early and potential_timestamp_element:
                    post_data["elements"].insert(0, potential_timestamp_element)

                posts.append(post_data)
                current_index = next_post_start_index
            else:
                current_index += 1

        if debug:
            logger.debug(f"Identified {len(posts)} posts using pattern matching (v9).")

        if not posts and filtered_elements:
            logger.warning("Post pattern matching failed (v9), no posts detected.")
            return "<!-- Post pattern matching failed -->"

        # --- Convert Posts to Markdown (V9: With fixed links) --- #
        markdown_blocks = []
        for post_idx, post_data in enumerate(posts):
            username = post_data.get("username", "Unknown User")
            # Clean username again to ensure consistency
            username = clean_username(username)
            profile_url = post_data.get("profile_url")
            elements = post_data.get("elements", [])

            if debug:
                logger.debug(
                    f"--- Processing post {post_idx} ({username}), {len(elements)} elements ---"
                )

            # --- V9: Improved Text and Image Processing --- #
            # 1. Extract text, timestamps, and image URLs
            all_text_elements = [el for el in elements if isinstance(el, (Text, NarrativeText))]
            all_image_elements = [el for el in elements if isinstance(el, Image)]
            all_timestamp_elements = [el for el in elements if is_timestamp(el)]

            # 2. Process timestamps first
            timestamp_texts = []
            for element in all_timestamp_elements:
                timestamp_text = str(element).strip()
                if timestamp_text:
                    timestamp_texts.append(f"* Posted {timestamp_text}")

            # 3. Process images - collect URLs with alt text
            image_data = []
            for element in all_image_elements:
                img_url = getattr(element.metadata, "image_url", None)
                if img_url:
                    alt_text = clean_element_text(str(element))
                    if not alt_text or len(alt_text) < 5:
                        alt_text = "Image"
                    image_data.append((alt_text, img_url))

            # 4. Deduplicate image URLs
            deduplicated_images = deduplicate_image_urls(image_data, debug=debug)

            # 5. Process text elements
            text_blocks = []
            for element in all_text_elements:
                # Skip elements we already processed as timestamps
                if is_timestamp(element):
                    continue

                text = str(element).strip()
                if text:
                    cleaned_text = clean_element_text(text)
                    if cleaned_text:
                        # v10: Check if this element has a link in its metadata
                        link_url = extract_links_from_metadata(element)
                        if link_url:
                            # Element has link metadata - format as markdown link
                            # If the entire text is the link, wrap it
                            if len(cleaned_text) < 50:
                                # Short text - likely the whole thing is a link
                                cleaned_text = f"[{cleaned_text}]({link_url})"
                            else:
                                # Longer text - append the link at the end
                                domain = urlparse(link_url).netloc
                                display_text = domain if domain else "link"
                                cleaned_text += f" [{display_text}]({link_url})"

                            if debug:
                                logger.debug(
                                    f"Applied metadata link to text element: {cleaned_text[:100]}..."
                                )

                        text_blocks.append(cleaned_text)

            # 6. Deduplicate text blocks
            deduplicated_text = deduplicate_text_blocks(text_blocks, debug=debug)

            # 7. Format links in text with improved URL detection
            formatted_text = []
            for text in deduplicated_text:
                # Skip already formatted links (those we processed from metadata)
                if re.search(r"\[.+?\]\(.+?\)", text):
                    formatted_text.append(text)
                # Only try link formatting if there's likely a URL present
                elif "http" in text or "www." in text:
                    formatted = format_markdown_links(text)
                    formatted_text.append(formatted)
                else:
                    formatted_text.append(text)

            if debug and formatted_text:
                logger.debug(
                    f"Post contains {len(formatted_text)} text blocks, {len(deduplicated_images)} images"
                )

            # --- Build the final markdown post --- #
            post_lines = []

            # Add the header with profile URL if available
            if profile_url:
                post_header = f"### Post by [{username}]({profile_url})"
            else:
                post_header = f"### Post by {username}"

            post_lines.append(post_header)

            # Add timestamps if any
            if timestamp_texts:
                post_lines.append("\n".join(timestamp_texts))

            # Add content: first text blocks, then images
            for text in formatted_text:
                post_lines.append(text)

            # Add images after text
            for alt_text, url in deduplicated_images:
                post_lines.append(f"![{alt_text}]({url})")

            # Only add non-empty posts
            if len(post_lines) > 1:  # More than just the header
                markdown_blocks.append("\n\n".join(post_lines))
            elif debug:
                logger.debug(f"Skipping empty post by {username} (Post Index: {post_idx})")

        # Handle case with no markdown blocks
        if not markdown_blocks:
            logger.warning("No markdown posts generated after processing (v9).")
            # Fallback logic (simplified)
            all_text = "\n\n".join([str(el) for el in filtered_elements if isinstance(el, Text)])
            if all_text:
                return "### Fallback: All Filtered Text\n\n" + all_text
            else:
                return "<!-- No markdown posts generated -->"

        markdown = "\n\n\n".join(markdown_blocks)
        logger.info("Threads HTML to markdown conversion completed successfully (v10).")
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error processing Threads HTML with unstructured",
            exc_info=True,
        )
        return f"Error processing Threads HTML with unstructured: {e}"
