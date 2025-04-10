import re
from typing import Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from brocc_li.utils.logger import logger


def _extract_actor_info(item: Tag, debug: bool = False) -> Dict[str, Optional[str]]:
    """Extracts author information from a feed item."""
    actor_info: Dict[str, Optional[str]] = {
        "name": None,
        "profile_url": None,
        "subtitle": None,
        "timestamp": None,  # Or time description like '1d', '2h'
        "avatar_url": None,
    }
    actor_container = item.select_one("div.update-components-actor__container")
    if not actor_container:
        if debug:
            logger.debug("Could not find actor container (div.update-components-actor__container)")
        return actor_info

    # Name (try the specific span first, fallback to aria-label on link)
    name_span = actor_container.select_one(
        "span.update-components-actor__title span[aria-hidden=true]"
    )
    if name_span:
        actor_info["name"] = name_span.get_text(strip=True)

    # Profile URL and potential name fallback
    profile_link = actor_container.select_one("a.update-components-actor__meta-link")
    if profile_link:
        # Explicitly handle potential list return from get() although unlikely for href
        href_val = profile_link.get("href")
        actor_info["profile_url"] = str(href_val) if href_val else None
        if not actor_info["name"]:
            # Fallback using aria-label, cleaning it up
            # Ensure aria_label is treated as a string
            aria_label_val = profile_link.get("aria-label")
            aria_label = str(aria_label_val) if aria_label_val else ""
            # Example: "View: Steffen Holm • 1st co-founder ..."
            match = re.search(r"View:\s*([^•]+)\s*(?:•.*)?", aria_label)
            if match:
                actor_info["name"] = match.group(1).strip()
            elif debug:
                logger.debug(f"Could not extract name from aria-label: {aria_label}")

    # Subtitle (job title, company, etc.)
    subtitle_span = actor_container.select_one("span.update-components-actor__description")
    if subtitle_span:
        # Try to clean up the text, focusing on the visible portion
        subtitle_text = subtitle_span.get_text(strip=True)

        # Remove duplicated text - sometimes LinkedIn duplicates the text
        # Example: "Software Engineer at CompanySoftware Engineer at Company"
        if len(subtitle_text) > 10:  # Only process if reasonably long
            half_length = len(subtitle_text) // 2
            first_half = subtitle_text[:half_length]
            second_half = subtitle_text[half_length:]

            # If the two halves are identical or very similar
            if first_half == second_half or first_half.strip() == second_half.strip():
                subtitle_text = first_half
            elif len(first_half) > 5 and first_half in second_half:
                # Try to find if first half is contained in second half
                subtitle_text = first_half
            elif len(second_half) > 5 and second_half in first_half:
                # Or vice versa
                subtitle_text = second_half

        # If still multi-line, just take the first line
        if "\n" in subtitle_text:
            subtitle_text = subtitle_text.split("\n")[0].strip()

        actor_info["subtitle"] = subtitle_text

    # Timestamp / Sub-description
    sub_desc_span = actor_container.select_one("span.update-components-actor__sub-description")
    if sub_desc_span:
        # Look specifically for the first span inside which usually has the timestamp
        timestamp_spans = sub_desc_span.select("span")
        if timestamp_spans:
            # Take the first visible span's text
            timestamp_text = timestamp_spans[0].get_text(strip=True)

            # In case of "2h •" format, clean up
            if "•" in timestamp_text:
                timestamp_text = timestamp_text.split("•")[0].strip() + " •"

            actor_info["timestamp"] = timestamp_text
        else:
            # Fallback to the full text, just trying to clean it
            timestamp_text = sub_desc_span.get_text(strip=True)

            # Check for duplication in timestamp text
            if len(timestamp_text) > 4:  # Only process if reasonably long
                half_length = len(timestamp_text) // 2
                if timestamp_text[:half_length] == timestamp_text[half_length:]:
                    timestamp_text = timestamp_text[:half_length]

            # Clean up multi-line timestamp text
            if "\n" in timestamp_text:
                timestamp_text = timestamp_text.split("\n")[0].strip()

            actor_info["timestamp"] = timestamp_text

    # Avatar URL
    avatar_img = actor_container.select_one("img.update-components-actor__avatar-image")
    if avatar_img:
        # Explicitly handle potential list return from get() although unlikely for src
        src_val = avatar_img.get("src")  # or data-delayed-url?
        actor_info["avatar_url"] = str(src_val) if src_val else None

    if debug:
        logger.debug(f"Extracted actor info: {actor_info}")

    return actor_info


def _extract_post_text(item: Tag, debug: bool = False) -> Optional[str]:
    """Extracts the main text content of the post, handling potential 'See more'."""
    text_container = item.select_one("div.update-components-text")
    if not text_container:
        if debug:
            logger.debug("Could not find post text container (div.update-components-text)")
        return None

    # The actual text might be within a span inside, or directly in the div
    # Let's get all text, stripping leading/trailing whitespace from each part and joining
    full_text = text_container.get_text(separator="\n", strip=True)

    # Fix double newlines and spacing issues with tagged content by reducing multiple newlines to single newline
    full_text = re.sub(r"\n\s*\n", "\n", full_text)

    # Try to detect tagged companies/profiles (text chunks separated by newlines that are short)
    # and improve formatting
    lines = full_text.split("\n")
    cleaned_lines = []

    for i, line in enumerate(lines):
        stripped_line = line.strip()
        # Check if this might be a standalone tag (short text between newlines)
        if stripped_line and len(stripped_line) < 20 and i > 0 and i < len(lines) - 1:
            # Might be a tag, append it to previous line if it looks like a name/company
            if re.match(r"^[A-Za-z0-9\s]+$", stripped_line):
                # If previous line doesn't end with punctuation, append with space
                if cleaned_lines and not cleaned_lines[-1].rstrip().endswith(
                    (".", ",", ":", "!", "?")
                ):
                    cleaned_lines[-1] = f"{cleaned_lines[-1]} {stripped_line}"
                else:
                    # Otherwise, append with comma if not already there
                    if cleaned_lines and not cleaned_lines[-1].rstrip().endswith(","):
                        cleaned_lines[-1] = f"{cleaned_lines[-1]} {stripped_line},"
                    else:
                        cleaned_lines[-1] = f"{cleaned_lines[-1]} {stripped_line}"
            else:
                cleaned_lines.append(stripped_line)
        else:
            cleaned_lines.append(stripped_line)

    # Join with single newlines
    cleaned_text = "\n".join(cleaned_lines)

    # Sometimes there's a collapsed view with a button
    # The full text might be available directly, or we might need to handle this (future improvement)
    # For now, we grab what's visible.
    # Check for a potential hidden span holding more text (common pattern)
    hidden_span = text_container.select_one(
        "span.visually-hidden"
    )  # Example selector, might need adjustment
    if hidden_span:
        # This is a simplistic approach; real handling might require finding the button
        # and potentially accessing data attributes if the full text isn't in the DOM directly.
        pass  # For now, we rely on get_text() grabbing available content

    if debug:
        text_preview = (
            (cleaned_text[:100] + "...")
            if cleaned_text and len(cleaned_text) > 100
            else cleaned_text
        )
        logger.debug(f"Extracted post text (preview): {text_preview}")

    return cleaned_text if cleaned_text else None


def _extract_media(item: Tag, debug: bool = False) -> List[Dict[str, str]]:
    """Extracts media information (images, videos, articles)."""
    media_items = []

    # --- Images ---
    # Look for image containers
    image_containers = item.select(".update-components-image")
    for i, img_container in enumerate(image_containers):
        img_tag = img_container.select_one("img")
        if img_tag:
            img_src = img_tag.get("src")
            if img_src:
                media_items.append(
                    {
                        "type": "image",
                        "url": str(img_src),
                        "alt": img_tag.get("alt", "LinkedIn image"),
                    }
                )
                if debug:
                    logger.debug(f"Found image {i + 1}: {str(img_src)[:100]}...")

    # --- Videos ---
    video_containers = item.select(".update-components-video")
    for i, video_container in enumerate(video_containers):
        # Video preview image
        video_img = video_container.select_one("img")
        video_url = None

        # Try to find the actual video link
        video_link = video_container.select_one("a[href*='video']")
        if video_link:
            video_url = video_link.get("href")

        if video_img or video_url:
            media_items.append(
                {
                    "type": "video",
                    "url": str(video_url) if video_url else "#",
                    "thumbnail": str(video_img.get("src"))
                    if video_img and video_img.get("src")
                    else None,
                }
            )
            if debug:
                logger.debug(f"Found video {i + 1}")

    # --- Articles ---
    article_containers = item.select("article.update-components-article")
    for i, article in enumerate(article_containers):
        article_data = {"type": "article", "url": "#", "title": None, "image": None}

        # Find article link
        article_link = article.select_one(
            "a.update-components-article__meta, a.update-components-article__image-link"
        )
        if article_link:
            article_url = article_link.get("href")
            if article_url:
                article_data["url"] = str(article_url)

        # Find article title
        title_elem = article.select_one(".update-components-article__title")
        if title_elem:
            article_data["title"] = title_elem.get_text(strip=True)

        # Find article image
        article_img = article.select_one(".update-components-article__image")
        if article_img:
            img_src = article_img.get("src")
            if img_src:
                article_data["image"] = str(img_src)

        media_items.append(article_data)
        if debug:
            logger.debug(f"Found article {i + 1}: {article_data['title'] or 'Untitled'}")

    # Log summary
    if debug:
        logger.debug(f"Extracted {len(media_items)} media items in total")

    return media_items


def _extract_metrics(item: Tag, debug: bool = False) -> Dict[str, int]:
    """Extracts engagement metrics (likes, comments, reposts)."""
    metrics = {
        "likes": 0,
        "comments": 0,
        "reposts": 0,
    }

    # Find the social activity container
    social_container = item.select_one(
        "div.update-v2-social-activity, div.social-details-social-counts"
    )
    if not social_container:
        if debug:
            logger.debug(
                "Could not find social metrics container (div.update-v2-social-activity or div.social-details-social-counts)"
            )

        # Try looking at the parent level for containers
        social_action_bar = item.select_one("div.feed-shared-social-action-bar")
        if social_action_bar and debug:
            logger.debug("Found feed-shared-social-action-bar, might contain metrics")

        return metrics

    # Look for metrics counts - they might be in different formats

    # --- Likes/Reactions ---
    # Strategy 1: Look for dedicated reaction count elements
    likes_elem = social_container.select_one(
        "span.social-details-social-counts__reactions-count, button[aria-label*='reaction'], .social-details-social-counts__reactions-count"
    )
    if likes_elem:
        # Try to extract number from text
        likes_text = likes_elem.get_text(strip=True)
        likes_extracted = re.sub(r"[^\d]", "", likes_text)
        if likes_extracted.isdigit():
            metrics["likes"] = int(likes_extracted)

        # Fallback: Try extracting from aria-label if text approach didn't work
        if metrics["likes"] == 0 and "aria-label" in likes_elem.attrs:
            aria_label_value = likes_elem.get("aria-label")
            aria_label = str(aria_label_value) if aria_label_value is not None else ""
            match = re.search(r"(\d+)\s*reaction", aria_label)
            if match:
                metrics["likes"] = int(match.group(1))

    # Strategy 2: Look for social proof fallback number for reactions
    if metrics["likes"] == 0:
        fallback_elem = social_container.select_one(
            ".social-details-social-counts__social-proof-fallback-number"
        )
        if fallback_elem:
            fallback_text = fallback_elem.get_text(strip=True)
            if fallback_text.isdigit():
                metrics["likes"] = int(fallback_text)

    # --- Comments ---
    # Look for comment elements with various patterns
    comments_elem = social_container.select_one(
        "button[aria-label*='comment'], .social-details-social-counts__comments-count"
    )
    if comments_elem:
        # Try text content first
        comments_text = comments_elem.get_text(strip=True)
        comments_extracted = re.sub(r"[^\d]", "", comments_text)
        if comments_extracted.isdigit():
            metrics["comments"] = int(comments_extracted)

        # Fallback: Try aria-label
        if metrics["comments"] == 0 and "aria-label" in comments_elem.attrs:
            aria_label_value = comments_elem.get("aria-label")
            aria_label = str(aria_label_value) if aria_label_value is not None else ""
            match = re.search(r"(\d+)\s*comment", aria_label)
            if match:
                metrics["comments"] = int(match.group(1))

    # --- Reposts ---
    # Look for repost elements with various patterns
    reposts_elem = social_container.select_one(
        "button[aria-label*='repost'], .social-details-social-counts__reshares-count, button[aria-label*='reposts']"
    )
    if reposts_elem:
        # Try text content first
        reposts_text = reposts_elem.get_text(strip=True)
        reposts_extracted = re.sub(r"[^\d]", "", reposts_text)
        if reposts_extracted.isdigit():
            metrics["reposts"] = int(reposts_extracted)

        # Fallback: Try aria-label for reposts
        if metrics["reposts"] == 0 and "aria-label" in reposts_elem.attrs:
            aria_label_value = reposts_elem.get("aria-label")
            aria_label = str(aria_label_value) if aria_label_value is not None else ""
            match = re.search(r"(\d+)\s*repost", aria_label)
            if match:
                metrics["reposts"] = int(match.group(1))

    # If still no reposts found, try looking specifically for elements with repost text
    if metrics["reposts"] == 0:
        # Try to find any element containing exact repost counts
        repost_elements = item.select("[aria-label*='repost']")
        for repost_el in repost_elements:
            if "aria-label" in repost_el.attrs:
                aria_label_value = repost_el.get("aria-label")
                aria_label = str(aria_label_value) if aria_label_value is not None else ""
                match = re.search(r"(\d+)\s*repost", aria_label)
                if match:
                    metrics["reposts"] = int(match.group(1))
                    break

    if debug:
        logger.debug(f"Extracted metrics: {metrics}")

    return metrics


def _extract_comments(item: Tag, debug: bool = False) -> List[Dict[str, str]]:
    """Extracts comments from a feed item."""
    comments = []

    # Look for the comments container
    comments_container = item.select_one("div.feed-shared-update-v2__comments-container")
    if not comments_container:
        if debug:
            logger.debug("No comments container found")
        return comments

    # Find all comment articles
    comment_articles = comments_container.select("article.comments-comment-entity")
    if debug:
        logger.debug(f"Found {len(comment_articles)} comments")

    for i, comment in enumerate(comment_articles):
        comment_data = {
            "author_name": None,
            "author_headline": None,
            "author_url": None,
            "text": None,
            "timestamp": None,
            "is_reply": False,
            "likes": 0,
        }

        # Check if this is a reply comment - use string class attribute to avoid type issues
        comment_class_attr = comment.get("class")
        if comment_class_attr:
            class_str = " ".join(str(c) for c in comment_class_attr)
            if "comments-comment-entity--reply" in class_str:
                comment_data["is_reply"] = True

        # Extract author name
        author_link = comment.select_one("a.comments-comment-meta__description-container")
        if author_link:
            # Try to get the name from aria-label (more reliable)
            aria_label_val = author_link.get("aria-label")
            if aria_label_val:
                aria_label = str(aria_label_val)
                name_match = re.search(r"View:\s*([^•]+)(?:•|Author)", aria_label)
                if name_match:
                    comment_data["author_name"] = name_match.group(1).strip()

            # Try to get the profile URL
            href_val = author_link.get("href")
            if href_val:
                comment_data["author_url"] = str(href_val)

            # Try to get the headline from title or subtitle
            subtitle = comment.select_one("div.comments-comment-meta__description-subtitle")
            if subtitle:
                comment_data["author_headline"] = subtitle.get_text(strip=True)

        # If no name was found, try to get it directly from the title span
        if not comment_data["author_name"]:
            title_span = comment.select_one("span.comments-comment-meta__description-title")
            if title_span:
                comment_data["author_name"] = title_span.get_text(strip=True)

        # Extract timestamp
        timestamp_elem = comment.select_one("time.comments-comment-meta__data")
        if timestamp_elem:
            comment_data["timestamp"] = timestamp_elem.get_text(strip=True)

        # Extract comment text
        content_span = comment.select_one("span.comments-comment-item__main-content")
        if content_span:
            comment_data["text"] = content_span.get_text(strip=True)

        # Extract likes count
        likes_button = comment.select_one("button.comments-comment-social-bar__reactions-count--cr")
        if likes_button:
            likes_text = likes_button.get_text(strip=True)
            likes_match = re.search(r"(\d+)", likes_text)
            if likes_match:
                comment_data["likes"] = int(likes_match.group(1))

        comments.append(comment_data)

        if debug and i < 3:  # Only debug log first few comments to avoid spam
            logger.debug(f"Comment {i + 1}: {comment_data}")

    return comments


def _format_linkedin_post_markdown(
    actor: Dict[str, Optional[str]],
    content: Optional[str],
    media: List[Dict[str, str]],
    metrics: Dict[str, int],
    comments: Optional[List[Dict[str, str]]] = None,
    post_urn: Optional[str] = None,
) -> str:
    """Formats the extracted data into a Markdown block."""
    lines = []

    # --- Header ---
    author_name = actor.get("name", "Unknown Author")
    timestamp = actor.get("timestamp", "N/A")

    lines.append(f"### {author_name} ({timestamp})")

    if actor.get("subtitle"):
        lines.append(f"> {actor.get('subtitle')}")

    # Add profile and post links
    profile_url = actor.get("profile_url", "#")
    post_url = f"https://www.linkedin.com/feed/update/{post_urn}" if post_urn else None

    if profile_url and post_url:
        lines.append(f"> [Profile]({profile_url}) | [Post]({post_url})")
    elif profile_url:
        lines.append(f"> [Profile]({profile_url})")

    # Add avatar thumbnail if available
    if actor.get("avatar_url"):
        lines.append(f"![{author_name}]({actor.get('avatar_url')}){{: width=50px}}")

    lines.append("")  # Empty line after header

    # --- Content ---
    if content:
        lines.append(content)
        lines.append("")  # Empty line after content

    # --- Media ---
    for item in media:
        media_type = item.get("type")

        if media_type == "image":
            url = item.get("url")
            alt = item.get("alt")
            if url:
                lines.append(f"![{alt or 'Image'}]({url})")

        elif media_type == "video":
            url = item.get("url")
            thumbnail = item.get("thumbnail")
            if thumbnail:
                lines.append(f"[![Video Thumbnail]({thumbnail})]({url or '#'}) *(Video)*")
            else:
                lines.append(f"[View Video]({url or '#'})")

        elif media_type == "article":
            title = item.get("title") or "Shared Article"
            url = item.get("url")
            image = item.get("image")

            if image:
                lines.append(f"[![{title}]({image})]({url})")

            lines.append(f"**[{title}]({url})**")

    # Add empty line if media was added
    if media:
        lines.append("")

    # --- Metrics ---
    metric_parts = []

    likes = metrics.get("likes", 0)
    if likes > 0:
        metric_parts.append(f"❤️ {likes} reactions")

    comments_count = metrics.get("comments", 0)
    if comments_count > 0:
        metric_parts.append(f"💬 {comments_count} comments")

    reposts = metrics.get("reposts", 0)
    if reposts > 0:
        metric_parts.append(f"🔄 {reposts} reposts")

    if metric_parts:
        lines.append(" · ".join(metric_parts))

    # --- Comments Section ---
    if comments and isinstance(comments, list) and len(comments) > 0:
        lines.append("")
        lines.append(f"**Comments ({len(comments)}):**")

        for i, comment in enumerate(comments):
            # If more than 3 comments, only show the first 3
            if i >= 3:
                remaining = len(comments) - 3
                lines.append(f"*...and {remaining} more comments*")
                break

            is_reply = comment.get("is_reply", False)
            prefix = "   " if is_reply else ""
            author = comment.get("author_name", "Unknown")
            text = comment.get("text", "")
            timestamp = comment.get("timestamp", "")

            # Ensure likes is an integer
            likes_val = comment.get("likes")
            likes = int(likes_val) if likes_val is not None and str(likes_val).isdigit() else 0

            lines.append(f"{prefix}**{author}** ({timestamp}): {text}")

            if likes > 0:
                lines.append(f"{prefix}❤️ {likes}")

    return "\n".join(lines)


def linkedin_feed_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Parses the HTML of a LinkedIn feed page and extracts feed items.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        feed_item_selector = "div.feed-shared-update-v2"
        feed_items: List[Tag] = soup.select(feed_item_selector)

        if debug:
            logger.debug(
                f"Found {len(feed_items)} potential feed items using selector: '{feed_item_selector}'"
            )

        if not feed_items:
            logger.warning(f"No feed items found using selector: '{feed_item_selector}'.")
            return None  # Return None if no items found

        output_blocks: List[str] = []
        filtered_count = 0

        for i, item in enumerate(feed_items):
            # Ensure item_urn is Optional[str]
            urn_val = item.get("data-urn")
            item_urn: Optional[str] = str(urn_val) if urn_val else None
            item_html_str = str(item)
            truncated_html = (
                (item_html_str[:250] + "...") if len(item_html_str) > 250 else item_html_str
            )  # Shorten more

            if debug:
                logger.debug(
                    f"--- Processing Feed Item {i + 1}/{len(feed_items)} (URN: {item_urn}) ---"
                )
                logger.debug(f"Item HTML (truncated): {truncated_html}")

            # --- Extract Content ---
            actor_info = _extract_actor_info(item, debug=debug)
            post_text = _extract_post_text(item, debug=debug)
            media_info = _extract_media(item, debug=debug)
            metrics_info = _extract_metrics(item, debug=debug)
            comments_info = _extract_comments(item, debug=debug)

            # --- Skip 'None' items that don't have proper author info ---
            if actor_info["name"] == "None" or actor_info["name"] is None:
                if debug:
                    logger.debug(f"Skipping item {i + 1} because it has no valid author name")
                filtered_count += 1
                continue

            # --- Format Block ---
            markdown_block = _format_linkedin_post_markdown(
                actor=actor_info,
                content=post_text,
                media=media_info,
                metrics=metrics_info,
                comments=comments_info,
                post_urn=item_urn,
            )
            output_blocks.append(markdown_block)

        if filtered_count > 0 and debug:
            logger.debug(f"Filtered out {filtered_count} items with missing author information")

        # --- Combine and Return ---
        # Join blocks with double newline instead of separator
        markdown_output = "\n\n".join(output_blocks)

        if not markdown_output:
            logger.warning("Processing resulted in empty markdown despite finding feed items.")
            return None  # Return None if output is empty
        else:
            logger.info(
                f"Successfully processed {len(output_blocks)} feed items into markdown after filtering {filtered_count} invalid items."
            )

        return markdown_output.strip()

    except Exception as e:
        logger.error(
            "Error converting LinkedIn HTML with BeautifulSoup",
            exc_info=True,
        )
        return f"Error converting LinkedIn HTML with BeautifulSoup: {e}"
