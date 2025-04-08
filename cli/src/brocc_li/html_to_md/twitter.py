from typing import List, Optional

# Import specific element types we might want to handle differently
from unstructured.documents.elements import Element, Image, ListItem, NarrativeText, Text, Title
from unstructured.partition.html import partition_html

from brocc_li.utils.logger import logger


def format_element_to_markdown(element: Element) -> Optional[str]:
    """Formats a single unstructured Element into a Markdown string (content only)."""
    metadata_dict = element.metadata.to_dict() if hasattr(element, "metadata") else {}
    element_text = getattr(element, "text", "").strip()

    # Note: Noise filtering should happen *before* calling this function.

    if isinstance(element, Title):
        # Use H2, more prominent for section titles like "Trending now"
        return f"## {element_text}"
    elif isinstance(element, ListItem):
        # Standard list item
        return f"- {element_text}"
    elif isinstance(element, Image):
        # Format as Markdown image, trying to get good alt text
        src = metadata_dict.get("image_url") or metadata_dict.get("url") or "image"
        link_texts = metadata_dict.get("link_texts", [])
        # Try link text first for alt, then element text, then filename part, fallback to "image"
        alt = (
            (link_texts[0] if link_texts else "")
            or element_text
            or (
                src.split("/")[-1].split("?")[0] if isinstance(src, str) else ""
            )  # Handle potential query params
            or "image"
        )
        # Clean alt text
        alt = alt.replace("[", "").replace("]", "").strip()
        logger.debug(f"Formatting image: src='{src}', alt='{alt}'")
        return f"![{alt}]({src})"
    elif hasattr(element, "text") and element_text:
        # Handle text-based elements (NarrativeText, Text, etc.)
        # Linkify @handles if possible
        if element_text.startswith("@"):
            link_urls = metadata_dict.get("link_urls", [])
            # Find a link URL that matches the handle (e.g., link to '/handle_name' for text '@handle_name')
            handle_url = next(
                (
                    url
                    for url in link_urls
                    if isinstance(url, str) and url.lstrip("/") == element_text.lstrip("@")
                ),
                None,
            )
            if handle_url:
                # Assume relative URL, construct markdown link
                # TODO: Consider base URL injection for absolute links if needed later
                logger.debug(f"Linkifying handle: {element_text} -> {handle_url}")
                return f"[{element_text}]({handle_url})"
            else:
                logger.debug(f"Could not find link URL for handle: {element_text}")
        # Return plain text for other cases
        return element_text
    else:
        # Skip elements without text representation (unless handled above, like Image)
        logger.debug(f"Skipping element of type {type(element).__name__} with no text.")
        return None


def _extract_tweet_header_info(
    elements: List[Element],
) -> tuple[Optional[str], Optional[str], Optional[str], List[Element]]:
    """Attempts to extract name, handle, and timestamp from the start of a list of elements."""
    name, handle, timestamp = None, None, None
    extracted_count = 0
    indices_to_remove = []

    # Simpler approach: Look for the first plausible Name (Text), Handle (@link), Timestamp (status link)
    for i, el in enumerate(elements[:5]):  # Check first 5 elements
        text = getattr(el, "text", "").strip()
        metadata = el.metadata.to_dict() if hasattr(el, "metadata") else {}
        link_urls = metadata.get("link_urls", [])

        # Identify Name: First non-handle, non-timestamp text
        if (
            not name
            and isinstance(el, (Text, NarrativeText))
            and text
            and not text.startswith("@")
            and not any("/status/" in link for link in link_urls if isinstance(link, str))
        ):
            name = text
            indices_to_remove.append(i)
            extracted_count += 1
            continue

        # Identify Handle: Starts with @, has a link
        if not handle and text.startswith("@") and link_urls:
            formatted_handle = format_element_to_markdown(el)
            if (
                formatted_handle
                and formatted_handle.startswith("[")
                and formatted_handle.endswith(")")
            ):
                handle = formatted_handle
                indices_to_remove.append(i)
                extracted_count += 1
                continue

        # Identify Timestamp: Has a link to a status
        if not timestamp and any(
            isinstance(link, str) and "/status/" in link for link in link_urls
        ):
            timestamp = text  # Use the raw text
            indices_to_remove.append(i)
            extracted_count += 1
            continue

        # Stop if we have all three or checked enough elements
        if extracted_count >= 3:
            break

    # Reconstruct remaining_elements by removing the identified header elements
    if indices_to_remove:
        indices_to_remove.sort(reverse=True)
        remaining_elements = list(elements)
        for index in indices_to_remove:
            if index < len(remaining_elements):
                del remaining_elements[index]
    else:
        remaining_elements = elements  # No header info found/extracted

    logger.debug(f"Header extraction: Name='{name}', Handle='{handle}', Timestamp='{timestamp}'")
    return name, handle, timestamp, remaining_elements


def convert_twitter_feed_html_to_md(
    html: str, url: Optional[str] = None, title: Optional[str] = None
) -> Optional[str]:
    """
    Convert Twitter HTML to structured Markdown using unstructured,
    segmenting content blocks, filtering noise, and creating tweet headers.

    Args:
        html: The HTML content to convert
        url: Optional URL for logging
        title: Optional title (unused)

    Returns:
        Formatted markdown text, or None on failure.
    """
    try:
        logger.info(f"Partitioning HTML for {url or 'unknown URL'} using unstructured")
        # Consider adding strategies like 'hi_res' if needed, default is 'auto'
        elements = partition_html(text=html, source_format="html")
        logger.info(f"Found {len(elements)} elements from unstructured partitioning.")

        output_blocks: List[str] = []
        current_block_elements: List[Element] = []
        skip_current_block = False  # Flag to skip "Who to follow" content
        current_block_is_tweet = False  # Track if the current block started with a profile pic

        def finalize_block(block_elements: List[Element], is_tweet: bool) -> Optional[str]:
            """Formats a list of elements into a structured block with optional header."""
            if not block_elements:
                return None

            name, handle, timestamp, content_elements = None, None, None, block_elements
            header = ""

            if is_tweet:
                # Try to extract header info only if it's likely a tweet block
                name, handle, timestamp, content_elements = _extract_tweet_header_info(
                    block_elements
                )
                if name or handle or timestamp:
                    header_parts = [part for part in [name, handle, timestamp] if part]
                    header = f"### {' '.join(header_parts)}\n"  # Add newline after header
                else:
                    logger.warning("Detected tweet block but failed to extract header info.")

            # Format the *remaining* content elements
            formatted_parts = [
                p
                for p in (format_element_to_markdown(el) for el in content_elements)
                if p and p.strip()
            ]

            if not formatted_parts:
                return None  # Don't return just a header if content is empty

            # Join content with spaces if it's a tweet, otherwise newlines
            join_char = " " if is_tweet else "\n"
            content = join_char.join(formatted_parts)

            logger.debug(f"Finalized block with header '{header.strip()}': {content[:100]}...")
            return header + content

        for i, element in enumerate(elements):
            metadata_dict = element.metadata.to_dict() if hasattr(element, "metadata") else {}
            element_text = getattr(element, "text", "").strip()
            image_url = metadata_dict.get("image_url", "")
            link_urls = metadata_dict.get("link_urls", []) or []

            # --- Noise Filtering ---
            # Filter out analytics/view count links (common pattern)
            if any(isinstance(link, str) and "/analytics" in link for link in link_urls):
                logger.debug(f"Skipping analytics link element: {element_text}")
                continue
            # Filter out "Show more" links *before* block management
            if element_text == "Show more" and any(
                isinstance(link, str)
                and (link == "/explore/tabs/for_you" or link.startswith("/i/connect_people"))
                for link in link_urls
            ):
                logger.debug(f"Skipping 'Show more' element: {element_text}")
                continue
            # Filter out explicit "Click to Follow" text elements
            if "Click to Follow" in element_text:
                logger.debug(f"Skipping 'Click to Follow' element: {element_text}")
                continue
            # Filter empty NarrativeText more reliably
            if isinstance(element, NarrativeText) and not element_text:
                logger.debug("Skipping empty NarrativeText element.")
                continue
            # Filter out Emoji images
            if (
                isinstance(element, Image)
                and isinstance(metadata_dict.get("image_url", ""), str)
                and "abs-0.twimg.com/emoji/v2/svg" in metadata_dict.get("image_url", "")
            ):
                logger.debug(f"Skipping emoji image element: {metadata_dict.get('image_url')}")
                continue
            # Filter out specific boilerplate text
            if isinstance(element, Text) and element_text in ["Quote", "Live on X"]:
                logger.debug(f"Skipping boilerplate text element: '{element_text}'")
                continue
            # Filter more UI text
            if isinstance(element, Text) and element_text in ["Explore", "Beta"]:
                if skip_current_block:
                    continue
                logger.debug(f"Skipping UI text element: '{element_text}'")
                continue
            # Filter small profile images (_normal size) typically found in lists/trends
            if (
                isinstance(element, Image)
                and isinstance(image_url, str)
                and "profile_images" in image_url
                and "_normal" in image_url
            ):
                logger.debug(f"Skipping _normal profile image element: {image_url}")
                continue
            # Filter "X posts" text often found in trending topics
            if isinstance(element, Text) and element_text.endswith(" posts"):
                logger.debug(f"Skipping 'posts' count text: '{element_text}'")
                continue
            # Filter out potential timestamp-only text nodes if they have a link to the status
            # Example: "6m" linking to "/username/status/123..."
            # Let format_element handle this for now, maybe it's useful context
            # if len(element_text) <= 5 and ('h' in element_text or 'm' in element_text or 's' in element_text) and element_text[:-1].isdigit():
            #     if any(isinstance(link, str) and "/status/" in link for link in link_urls):
            #         logger.debug(f"Skipping linked timestamp element: {element_text}")
            #         continue

            # --- Structure Detection ---
            # Heuristic: An Image from pbs.twimg.com/profile_images is likely a profile pic.
            is_profile_pic = (
                isinstance(element, Image)
                and isinstance(image_url, str)
                and "profile_images" in image_url
                and "_normal" not in image_url  # Exclude the small icons in lists/trends
            )

            # Heuristic: The text "Who to follow" starts a new section
            is_who_to_follow_header = element_text == "Who to follow"

            # Heuristic: Title element starts a new distinct section.
            is_title = isinstance(element, Title)

            # --- Block Management ---
            block_break_detected = is_profile_pic or is_title or is_who_to_follow_header

            if block_break_detected:
                # If we were already skipping, just clear any potential stray elements and continue skipping
                if skip_current_block:
                    logger.debug(f"Continuing skip state due to block break at element {i}.")
                    current_block_elements = []  # Ensure buffer is clear
                    # Keep skip_current_block = True
                    # Determine if the *current* break means we should STOP skipping (e.g. a Title outside WhoToFollow)
                    # For now, assume any break while skipping keeps skipping until a major Title perhaps?
                    # Let's keep it simple: only reset skip on a non-WhoToFollow trigger *if not already skipping*.
                    # If a break happens *while* skipping, we stay skipping.
                    # Except! If the break is a Title, maybe that ends the skip?
                    if is_title:
                        logger.info(
                            f"Title element {i} detected while skipping, resetting skip state."
                        )
                        skip_current_block = False  # A new Title likely ends the skip section
                        current_block_is_tweet = False
                    else:
                        # Profile pic break while skipping, just continue skip
                        continue  # Go to next element, still skipping

                # Finalize the PREVIOUS block *only if we weren't skipping it*
                if current_block_elements and not skip_current_block:
                    logger.debug(
                        f"Finalizing previous block (Tweet={current_block_is_tweet}) before element {i} due to break."
                    )
                    final_block = finalize_block(
                        current_block_elements, is_tweet=current_block_is_tweet
                    )
                    if final_block:
                        output_blocks.append(final_block)

                # Reset for the new block
                current_block_elements = []
                # Set state for the NEW block based on the trigger element
                skip_current_block = is_who_to_follow_header
                current_block_is_tweet = (
                    is_profile_pic and not skip_current_block
                )  # Only a tweet if started by pic AND not skipping
                logger.debug(
                    f"Resetting block state after element {i}. New block is_tweet={current_block_is_tweet}, skip={skip_current_block}"
                )

            # --- Add Element to Current Block (if not skipped) ---
            # Re-check skip_current_block, as it might have been reset by a Title break
            if skip_current_block:
                continue  # Don't add *any* element if we are skipping the current block

            # Skip adding the profile pic itself if it triggered a break
            if is_profile_pic:
                logger.debug(
                    f"Skipping addition of profile pic element {i} that triggered block break."
                )
                continue

            # Add the raw element to the current block list
            current_block_elements.append(element)

        # Finalize the very last block of parts
        if current_block_elements and not skip_current_block:
            logger.debug(f"Finalizing final block (Tweet={current_block_is_tweet})")
            final_block = finalize_block(current_block_elements, is_tweet=current_block_is_tweet)
            if final_block:
                output_blocks.append(final_block)

        # Join the final blocks with double newlines
        markdown = "\n\n".join(output_blocks)

        if not markdown:
            logger.warning(f"Unstructured resulted in empty markdown for {url or 'unknown URL'}")
            return None

        logger.info(
            f"Unstructured conversion successful for {url or 'unknown URL'}, markdown length: {len(markdown)}"
        )
        return markdown.strip()  # Ensure no leading/trailing whitespace on the final output
    except Exception as e:
        logger.error(
            f"Error converting HTML with unstructured for {url or 'unknown URL'}: {e}",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error converting HTML with unstructured: {e}"
