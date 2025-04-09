from typing import Any, Dict, List

from bs4 import Tag

from brocc_li.utils.logger import logger


def extract_user_info_from_post(post_el: Tag, debug: bool = False) -> Dict[str, Any]:
    """Extracts author name, handle, and profile URL from a Bluesky post element."""
    user_info = {
        "name": "Unknown Author",
        "handle": "@unknownhandle",
        "profile_url": "",
        "reposter": None,  # Store reposter if present
    }

    # Check for Repost indicator first
    # NOTE: In a feed, the context is different than a profile. The 'reposted by' might be above the item.
    # This selector might need adjustment for feed context.
    # Let's try finding it *within* the feed item first.
    repost_indicator = post_el.select_one('div[aria-label*="Reposted by"] a')
    if repost_indicator:
        user_info["reposter"] = repost_indicator.get_text(strip=True)
        if debug:
            logger.debug(f"Found repost indicator within post element by: {user_info['reposter']}")
            # In a repost, the main content is the *original* poster, not the reposter.

    # Extract Author Name and Handle (within the main post content part)
    # Selectors adapted from bsky_profile.py, potentially need refinement for feed structure
    author_link = post_el.select_one(
        'a[href*="/profile/"][aria-label*="profile"] span[style*="font-weight: 600"]'
    )
    author_handle_link = post_el.select_one(
        'a[href*="/profile/"][aria-label*="profile"] span[style*="color: rgb(147, 165, 183)"]'  # Slightly more generic selector for color
    )

    if author_link:
        user_info["name"] = author_link.get_text(strip=True)
    elif debug:
        logger.warning("Could not find author name element using profile selector logic.")

    if author_handle_link:
        user_info["handle"] = (
            author_handle_link.get_text(strip=True)
            .replace("\u2069", "")
            .replace("\u2066", "")
            .strip()
        )
    elif debug:
        logger.warning("Could not find author handle element using profile selector logic.")

    # Extract Profile URL
    author_profile_url_element = post_el.select_one('a[href*="/profile/"][aria-label*="profile"]')
    if author_profile_url_element:
        author_profile_url = author_profile_url_element.get("href", "")
        if isinstance(author_profile_url, str) and author_profile_url.startswith("/"):
            user_info["profile_url"] = f"https://bsky.app{author_profile_url}"
        else:
            user_info["profile_url"] = str(
                author_profile_url
            )  # Cast just in case it's not a string
    elif debug:
        logger.warning("Could not find author profile URL element.")

    if debug:
        logger.debug(
            f"Extracted user info: Name='{user_info['name']}', Handle='{user_info['handle']}', URL='{user_info['profile_url']}', Reposter='{user_info['reposter']}'"
        )

    return user_info


def extract_post_content_and_links(post_el: Tag, debug: bool = False) -> Dict[str, Any]:
    """Extracts post text, timestamp, and post URL from a Bluesky post element."""
    content_info = {
        "text": "",
        "timestamp": "Unknown Time",
        "post_url": "",
    }

    # Extract Timestamp and Post URL
    timestamp_link = post_el.select_one('a[href*="/post/"][data-tooltip]')
    if timestamp_link:
        content_info["timestamp"] = str(timestamp_link.get("data-tooltip", "Unknown Time"))
        post_url_raw = timestamp_link.get("href", "")
        post_url = str(post_url_raw) if post_url_raw else ""
        if post_url.startswith("/"):
            content_info["post_url"] = f"https://bsky.app{post_url}"
        else:
            content_info["post_url"] = post_url
        if debug:
            logger.debug(
                f"Timestamp: {content_info['timestamp']}, Post URL: {content_info['post_url']}"
            )
    else:
        if debug:
            logger.warning("Could not find timestamp link for post.")

    # Extract Post Text
    post_text_element = post_el.select_one('div[data-testid="postText"]')
    if post_text_element:
        text_parts = []
        for content in post_text_element.contents:
            if isinstance(content, str):
                text_parts.append(content)
            elif isinstance(content, Tag):
                if content.name == "a":  # Handle links
                    link_text = content.get_text(strip=True)
                    link_href = content.get("href", "")
                    # Make links absolute if they are relative paths
                    if isinstance(link_href, str) and link_href.startswith("/"):
                        link_href = f"https://bsky.app{link_href}"
                    text_parts.append(f"[{link_text}]({link_href})")
                elif content.name == "br":  # Handle line breaks
                    text_parts.append("\n")
                else:  # Get text from other inline tags
                    text_parts.append(content.get_text())
        content_info["text"] = "".join(text_parts).strip()
        if debug:
            logger.debug(f"Extracted Post Text ({len(content_info['text'])} chars)")
            if len(content_info["text"]) < 200:  # Log short texts fully
                logger.debug(f"Post Text Content: {content_info['text']}")
            else:  # Log snippet for long texts
                logger.debug(f"Post Text Snippet: {content_info['text'][:100]}...")

    else:
        if debug:
            logger.warning("Could not find post text element (data-testid='postText')")

    return content_info


def format_post_markdown(
    user_info: Dict[str, Any],
    content_info: Dict[str, Any],
    media_strings: List[str],
    metrics: Dict[str, int],
    debug: bool = False,
) -> str:
    """Formats the extracted Bluesky post information into a Markdown block."""
    if debug:
        logger.debug("Formatting post markdown block...")

    parts = []

    # Handle Repost Header
    if user_info.get("reposter"):
        parts.append(f"> Reposted by {user_info['reposter']}")  # Indicate repost clearly

    # Author and Timestamp Header (H3)
    author_part = (
        f"[{user_info['name']}]({user_info['profile_url']})"
        if user_info.get("profile_url")
        else user_info["name"]
    )
    time_part = (
        f"[{content_info['timestamp']}]({content_info['post_url']})"
        if content_info.get("post_url")
        else content_info["timestamp"]
    )
    header = f"### {author_part} ({user_info['handle']}) · {time_part}"
    parts.append(header)

    # Post Content
    if content_info["text"]:
        parts.append(content_info["text"])

    # Media (Placeholder - needs implementation in extract_media)
    if media_strings:
        parts.extend(media_strings)

    # Metrics (Placeholder - needs implementation in extract_metrics)
    # Using different repost emoji (🔄) for Bluesky vs Twitter (⟲)
    footer = f"💬 {metrics.get('replies', 0)}   🔄 {metrics.get('reposts', 0)}   ❤️ {metrics.get('likes', 0)}"
    parts.append(footer)

    # Join with double newlines, filtering empty parts
    markdown = "\n\n".join(filter(None, parts))
    if debug:
        logger.debug(f"Formatted Markdown Block Length: {len(markdown)}")
    return markdown


# --- Placeholder/TODO Functions ---


def extract_media(post_el: Tag, debug: bool = False) -> List[str]:
    """Placeholder for extracting media (images, embeds) from a Bluesky post."""
    if debug:
        logger.debug("[Placeholder] Extracting media")
    # TODO: Implement media extraction logic
    # Look for img tags, video tags, embedded content divs (e.g., data-testid='embedView')
    return []


def extract_metrics(post_el: Tag, debug: bool = False) -> Dict[str, int]:
    """Extracts engagement metrics (replies, reposts, likes) from a Bluesky post element."""
    metrics = {"replies": 0, "reposts": 0, "likes": 0}
    if debug:
        logger.debug("Extracting metrics...")

    try:
        # Extract Replies (using button's inner div text)
        reply_btn_div = post_el.select_one('button[data-testid="replyBtn"] div.css-146c3p1')
        if reply_btn_div:
            reply_count_str = reply_btn_div.get_text(strip=True)
            metrics["replies"] = _parse_metric_string(reply_count_str, debug=debug)
            if debug:
                logger.debug(f"Found Replies: {metrics['replies']} (Raw: '{reply_count_str}')")
        elif debug:
            logger.debug("Could not find reply button/count.")

        # Extract Reposts
        repost_count_el = post_el.select_one('div[data-testid="repostCount"]')
        if repost_count_el:
            repost_count_str = repost_count_el.get_text(strip=True)
            if debug:
                logger.debug(f"Repost element found. Raw text: '{repost_count_str}'")
            metrics["reposts"] = _parse_metric_string(repost_count_str, debug=debug)
            if debug:
                logger.debug(f"Parsed Reposts: {metrics['reposts']}")
        elif debug:
            logger.debug("Could not find repost count element.")

        # Extract Likes
        like_count_el = post_el.select_one('div[data-testid="likeCount"]')
        if like_count_el:
            like_count_str = like_count_el.get_text(strip=True)
            if debug:
                logger.debug(f"Like element found. Raw text: '{like_count_str}'")
            metrics["likes"] = _parse_metric_string(like_count_str, debug=debug)
            if debug:
                logger.debug(f"Parsed Likes: {metrics['likes']}")
        elif debug:
            logger.debug("Could not find like count element.")

    except Exception as e:
        if debug:
            logger.error(f"Error parsing metrics: {e}", exc_info=True)
        # Keep default zeros if parsing fails

    if debug:
        logger.debug(f"Final metrics extracted: {metrics}")
    return metrics


def _parse_metric_string(metric_str: str, debug: bool = False) -> int:
    """Parses metric strings like '123', '2.6K', '1.1M' into integers."""
    metric_str = metric_str.strip().replace(",", "")  # Remove whitespace and commas
    multiplier = 1

    if metric_str.endswith("K"):
        multiplier = 1000
        numeric_part = metric_str[:-1]
    elif metric_str.endswith("M"):
        multiplier = 1_000_000
        numeric_part = metric_str[:-1]
    else:
        numeric_part = metric_str

    try:
        # Use float for parsing to handle decimals like '2.6'
        value = float(numeric_part)
        result = int(value * multiplier)
        if debug:
            logger.debug(f"Parsed metric '{metric_str}' -> {result}")
        return result
    except ValueError:
        if debug:
            logger.warning(f"Could not parse metric string '{metric_str}' as number.")
        return 0
