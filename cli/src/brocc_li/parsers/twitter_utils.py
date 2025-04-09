import re
from typing import Callable, Dict, List, Optional, Set, Tuple, TypedDict

from bs4 import BeautifulSoup, Tag

from brocc_li.utils.logger import logger


class UserInfo(TypedDict, total=False):
    """Structure to hold extracted user information."""

    name: Optional[str]
    handle: Optional[str]
    handle_url: Optional[str]
    timestamp: Optional[str]
    timestamp_full: Optional[str]


def format_user_link(name: str, handle: str, handle_url: str) -> str:
    """
    Format user name and handle as a linked header.

    Args:
        name: User's display name
        handle: User's handle (including @)
        handle_url: URL to user's profile (can be relative)

    Returns:
        Formatted string with linked name and handle
    """
    # Strip @ from the beginning if present for cleaner URLs
    clean_handle = handle.lstrip("@")

    # If handle URL is just a relative path, make it absolute
    profile_url = handle_url
    if profile_url.startswith("/"):
        profile_url = f"https://x.com{profile_url}"

    # Ensure name is properly formatted for the link
    # Trim any extra whitespace
    clean_name = name.strip()

    # Format as [name](url) (@handle)
    # Make sure the name is not empty
    if not clean_name:
        clean_name = clean_handle  # Use handle as name if name is empty

    return f"[{clean_name}]({profile_url}) (@{clean_handle})"


def format_metrics(metrics: Dict[str, str]) -> str:
    """
    Format engagement metrics with appropriate emoji symbols.

    Args:
        metrics: Dictionary with keys like "replies", "retweets", "likes", "views"

    Returns:
        Formatted string with emoji symbols, or empty string if no metrics > 0
    """
    parts = []
    if metrics.get("replies", "0") != "0":
        parts.append(f"💬 {metrics['replies']}")
    if metrics.get("retweets", "0") != "0":
        parts.append(f"⟲ {metrics['retweets']}")
    if metrics.get("likes", "0") != "0":
        parts.append(f"❤️ {metrics['likes']}")
    if metrics.get("views", "0") != "0":
        parts.append(f"👁️ {metrics['views']}")

    return " ".join(parts)


def extract_user_info(tweet_element: Tag, debug: bool = False) -> UserInfo:
    """
    Extracts user name, handle, URL, and timestamp from a tweet element.

    Args:
        tweet_element: The BeautifulSoup Tag representing the tweet article.
        enable_debug_logging: Whether to enable debug logging.

    Returns:
        A dictionary containing the extracted user information.
    """
    user_info: UserInfo = {
        "name": None,
        "handle": None,
        "handle_url": None,
        "timestamp": None,
        "timestamp_full": None,
    }

    user_name_section = tweet_element.select_one('[data-testid="User-Name"]')
    if not user_name_section:
        if debug:
            logger.debug("Could not find User-Name section in tweet.")
        # Try a fallback using common link structure near the top
        user_link = tweet_element.select_one('div > div > div > a[role="link"]')
        if user_link and isinstance(user_link, Tag):
            href = user_link.get("href")
            if isinstance(href, str) and href.startswith("/") and href.endswith("/status/"):
                spans = user_link.select("span")
                if len(spans) >= 2:
                    potential_name = spans[0].get_text(strip=True)
                    potential_handle = spans[-1].get_text(strip=True)
                    if potential_handle.startswith("@"):
                        user_info["name"] = potential_name
                        user_info["handle"] = potential_handle
                        user_info["handle_url"] = href
                        if debug:
                            logger.debug(
                                f"Found user info via fallback: {user_info['name']} ({user_info['handle']})"
                            )
        # Even if fallback works, try finding time separately
        time_element = tweet_element.select_one("time")
        if time_element:
            user_info["timestamp"] = time_element.get_text(strip=True)
            user_info["timestamp_full"] = time_element.get("datetime")
        return user_info  # Return whatever was found

    # --- Name Extraction ---
    name_container = user_name_section.select_one(
        'a[role="link"] > div[dir="ltr"], div[dir="ltr"] > span'
    )
    if name_container:
        name_parts = []
        for elem in name_container.descendants:
            if isinstance(elem, str):
                text = elem.strip()
                if text and "Verified account" not in text and "follows you" not in text:
                    name_parts.append(text)
            elif isinstance(elem, Tag) and elem.name == "span":
                span_text = elem.get_text(strip=True)
                if (
                    span_text
                    and "Verified account" not in span_text
                    and "follows you" not in span_text
                ):
                    already_added = any(span_text in part for part in name_parts)
                    if not already_added:
                        name_parts.append(span_text)
        if name_parts:
            potential_name = " ".join(name_parts)
            unique_parts = []
            seen = set()
            for part in potential_name.split():
                if part not in seen:
                    unique_parts.append(part)
                    seen.add(part)
            user_info["name"] = " ".join(unique_parts)
    # Fallback name extraction
    if not user_info["name"]:
        fallback_name_element = user_name_section.select_one(
            'a span[data-testid*="UserName"], div span[data-testid*="UserName"]'
        )
        if fallback_name_element:
            potential_name = fallback_name_element.get_text(separator=" ", strip=True)
            if "Verified account" not in potential_name:
                user_info["name"] = " ".join(potential_name.split())
    if debug:
        logger.debug(f"Extracted Name: '{user_info['name']}'")

    # --- Handle and URL Extraction ---
    handle_link = user_name_section.find(
        "a",
        href=lambda h: isinstance(h, str) and h.startswith("/") and "/status/" not in h,
        recursive=False,
    )
    if not handle_link:
        handle_link = user_name_section.find(
            "a",
            href=lambda h: isinstance(h, str) and h.startswith("/") and "/status/" not in h,
        )

    if isinstance(handle_link, Tag):
        href_val = handle_link.get("href")
        if isinstance(href_val, str):
            user_info["handle_url"] = href_val
            if debug:
                logger.debug(f"Found potential handle URL: '{user_info['handle_url']}'")

    # Find handle text (@...)
    handle_text_element = user_name_section.find(
        lambda tag: isinstance(tag, Tag)
        and tag.name == "span"
        and tag.get_text(strip=True).startswith("@")
    )

    if isinstance(handle_text_element, Tag):
        handle_text_str = str(handle_text_element.get_text(strip=True)).strip()
        user_info["handle"] = handle_text_str
        if debug:
            logger.debug(f"Extracted Handle: '{user_info['handle']}'")
    elif debug:
        logger.debug("Could not find span element with text starting with @.")

    # --- Timestamp Extraction ---
    time_element = user_name_section.select_one("time")
    if time_element:
        user_info["timestamp"] = time_element.get_text(strip=True)
        user_info["timestamp_full"] = time_element.get("datetime")
    else:
        # Fallback for relative time in link
        time_link = user_name_section.find(
            "a", href=lambda h: isinstance(h, str) and "/status/" in h
        )
        if isinstance(time_link, Tag):
            time_text = time_link.get_text(strip=True)
            if time_text and not time_text.startswith("@") and len(time_text) < 15:
                user_info["timestamp"] = time_text
                time_tag_inside = time_link.find("time")
                if isinstance(time_tag_inside, Tag):
                    user_info["timestamp_full"] = time_tag_inside.get("datetime")

    if debug:
        logger.debug(f"Final extracted user_info: {user_info}")

    return user_info


def format_tweet_markdown(
    user_info: UserInfo,
    content: str,
    media_strings: List[str],
    metrics: Dict[str, str],
) -> str:
    """
    Formats the extracted tweet components into a Markdown block.

    Args:
        user_info: Dictionary containing user name, handle, url, timestamp.
        content: The main text content of the tweet.
        media_strings: List of markdown-formatted media links.
        metrics: Dictionary of engagement metrics.

    Returns:
        A formatted Markdown string representing the tweet.
    """
    header_parts = ["###"]
    name = user_info.get("name")
    handle = user_info.get("handle")
    handle_url = user_info.get("handle_url")
    timestamp = user_info.get("timestamp")
    timestamp_full = user_info.get("timestamp_full")

    user_link_added = False
    if name and handle and handle_url:
        try:
            user_link = format_user_link(name, handle, handle_url)
            header_parts.append(user_link)
            user_link_added = True
        except Exception as e:
            logger.warning(
                f"Error formatting user link (name={name}, handle={handle}, url={handle_url}): {e}"
            )
            # Fallback to plain text if formatting fails
            header_parts.append(f"{name} {handle}")
    elif handle:
        clean_handle = handle.lstrip("@")
        profile_url = f"https://x.com/{clean_handle}"  # Basic fallback URL
        if handle_url:
            profile_url = handle_url
            if profile_url.startswith("/"):
                profile_url = f"https://x.com{profile_url}"
        header_parts.append(f"[{handle}]({profile_url})")
        user_link_added = True
    elif name:
        header_parts.append(name)

    if timestamp:
        separator = " ·" if user_link_added else ""  # Add space before dot
        header_parts.append(f"{separator} {timestamp}")
        if timestamp_full:
            header_parts.append(f" ({timestamp_full})")

    header = " ".join(header_parts)

    # Assemble block
    tweet_block_parts = [header]
    if content:
        # Ensure newline separation, avoid triple newline if header is just "###"
        sep = "\n" if header == "###" else "\n\n"
        tweet_block_parts.append(f"{sep}{content}")

    if media_strings:
        tweet_block_parts.append(f"\n\n{' '.join(media_strings)}")

    metrics_str = format_metrics(metrics)
    if metrics_str:
        tweet_block_parts.append(f"\n\n{metrics_str}")

    return "".join(tweet_block_parts)


def extract_tweet_content(tweet_element: Tag, debug: bool = False) -> str:
    """
    Extract and format tweet text content.

    Args:
        tweet_element: BeautifulSoup Tag containing the tweet
        enable_debug_logging: Whether to enable debug logging.

    Returns:
        Formatted tweet content as markdown string
    """
    tweet_text_element = tweet_element.select_one('[data-testid="tweetText"]')
    if not tweet_text_element:
        if debug:
            logger.debug("No tweet text element found in tweet")
        return ""

    # Get all links to correctly format them
    links = []
    for a_tag in tweet_text_element.select("a"):
        href = a_tag.get("href", "")
        # Check if it's a user handle link
        if (
            isinstance(href, str)
            and href.startswith("/")
            and not href.startswith("/search")
            and "/status/" not in href
        ):
            # It's likely a user handle, format as [@user](/user)
            link_text = a_tag.get_text().strip()
            if link_text.startswith("@"):
                links.append((link_text, href))
        # Check if it's an external link or hashtag/cashtag
        elif isinstance(href, str) and (
            href.startswith("http")
            or href.startswith("/search?q=%23")
            or href.startswith("/search?q=%24")
        ):
            link_text = a_tag.get_text().strip()
            # Make relative search links absolute
            if href.startswith("/search"):
                href = f"https://x.com{href}"
            links.append((link_text, href))

    # Get plain text content - preserve line breaks
    text_parts = []
    for element in tweet_text_element.contents:
        if isinstance(element, str):
            text = element.strip()
            if text:
                text_parts.append(text)
        elif isinstance(element, Tag) and element.name == "a":
            # Placeholder for links we'll replace later
            link_text = element.get_text(strip=True)
            if link_text:
                text_parts.append(link_text)
        elif (
            isinstance(element, Tag) and element.name == "img"
        ):  # Handle emojis represented as images
            alt_text = element.get("alt")
            if isinstance(alt_text, str) and alt_text:  # Ensure alt_text is a non-empty string
                text_parts.append(alt_text)
        elif isinstance(element, Tag) and element.name == "span":  # Handle potential nested spans
            span_text = element.get_text(strip=True)
            if span_text:
                text_parts.append(span_text)

    # Join with spaces, trying to avoid excessive spacing or merging words
    content = " ".join(text_parts).strip()

    # Replace all links with markdown format
    # Sort links by length descending to replace longer matches first (e.g., http://t.co/abc before t.co/abc)
    links.sort(key=lambda x: len(x[0]), reverse=True)
    for link_text, href in links:
        # Ensure we only replace the exact text as found in the link tag
        # Sometimes the display text might be shortened (e.g., t.co links)
        # Find the actual <a> tag text again to be sure
        actual_link_tag = tweet_text_element.find("a", href=href)
        if actual_link_tag:
            display_text = actual_link_tag.get_text(strip=True)
            if display_text in content:
                markdown_link = f"[{display_text}]({href})"
                # Use count=1 to only replace the first occurrence if there are duplicates
                content = content.replace(display_text, markdown_link, 1)
            elif link_text in content:  # Fallback to the initially extracted text
                markdown_link = f"[{link_text}]({href})"
                content = content.replace(link_text, markdown_link, 1)

    # Clean up potential duplicate spaces that might arise from joining/replacing
    content = " ".join(content.split())

    return content


def extract_media(tweet_element: Tag, debug: bool = False) -> List[str]:
    """
    Extract media elements (images, videos, gifs) from a tweet.

    Args:
        tweet_element: BeautifulSoup Tag containing the tweet
        enable_debug_logging: Whether to enable debug logging.

    Returns:
        List of markdown-formatted media strings
    """
    media_strings = []
    processed_urls: Set[str] = set()  # Track processed URLs to avoid duplicates

    # Look for images within the tweet article, excluding profile pictures
    # Common pattern: div > div > div > div > a > div > div > img
    # Or sometimes: div > div > div > div > div > a[href*='/photo/'] img
    images = tweet_element.select(
        'article [data-testid="tweetPhoto"] img, article a[href*="/photo/"] img'
    )
    for img in images:
        src = img.get("src")
        if (
            src
            and isinstance(src, str)
            and "profile_images" not in src  # Basic check for profile images
            and "emoji" not in src  # Basic check for emojis
            and not src.startswith("data:")  # Skip base64 images
            and src not in processed_urls
        ):
            # Try to find the parent link for a better URL if src is a preview
            parent_link = img.find_parent("a")
            if isinstance(parent_link, Tag) and parent_link.get("href"):
                link_href = parent_link["href"]
                # Check if this link looks like a status link containing a photo
                if (
                    isinstance(link_href, str)
                    and "/status/" in link_href
                    and "/photo/" in link_href
                ):
                    # Construct a likely full image URL - often requires format=jpg&name=large
                    # This is heuristic and might need adjustment based on actual HTML patterns
                    f"https://x.com{link_href.split('/photo/')[0]}"
                    # Let's just use the src for now, but log the potential link
                    if debug:
                        logger.debug(f"Found image link: {link_href}, using src: {src}")

            alt = img.get("alt", "image")
            # Filter out placeholder alt text
            if isinstance(alt, str) and (alt.lower() == "image" or alt.strip() == ""):
                # Try to get a better description from aria-label on a parent
                aria_parent = img.find_parent(attrs={"aria-label": True})
                # Check if aria_parent is a Tag and has the attribute before accessing
                if isinstance(aria_parent, Tag) and aria_parent.has_attr("aria-label"):
                    label = aria_parent.get("aria-label")  # Use .get() for safety
                    if isinstance(label, str):  # Check if label is a string
                        alt = label
                # Ensure alt is string before final assignment if logic changes it
                if not isinstance(alt, str) or alt.lower() == "image" or alt.strip() == "":
                    alt = "Image"  # Default fallback if still placeholder

            # Ensure alt is string before using in f-string
            if not isinstance(alt, str):
                alt = "Image"

            media_strings.append(f"![{alt}]({src})")
            processed_urls.add(src)

    # Look for videos (similar structure often)
    videos = tweet_element.select("article video")
    for video in videos:
        poster = video.get("poster")
        if (
            poster
            and isinstance(poster, str)
            and "profile_images" not in poster
            and poster not in processed_urls
            and not poster.startswith("data:")
        ):
            # Try to get a better URL from a parent link
            parent_link = video.find_parent("a")
            video_url = poster  # Default to poster
            if isinstance(parent_link, Tag) and parent_link.get("href"):
                link_href = parent_link["href"]
                if isinstance(link_href, str) and "/status/" in link_href:
                    # Maybe the link itself is better?
                    full_link = (
                        f"https://x.com{link_href}" if link_href.startswith("/") else link_href
                    )
                    if debug:
                        logger.debug(f"Found video link: {full_link}, using poster: {poster}")
                    # For now, still using poster as the primary reference
                    video_url = poster

            media_strings.append(
                f"![Video Thumbnail]({video_url})"
            )  # Represent as image link to thumbnail
            processed_urls.add(poster)  # Add poster URL to processed
            if video_url != poster:
                processed_urls.add(video_url)  # Add link URL if different

        else:  # If no poster, try finding a source tag
            source = video.select_one("source")
            if source:
                src = source.get("src")
                if (
                    src
                    and isinstance(src, str)
                    and src not in processed_urls
                    and not src.startswith("blob:")
                ):
                    media_strings.append(
                        f"[Video Source]({src})"
                    )  # Link to source directly if possible
                    processed_urls.add(src)

    # Look for GIFs (often marked with aria-label="Embedded video")
    # Or sometimes within a div[data-testid="tweetPhoto"] that contains a video element
    gif_containers = tweet_element.select(
        'article div[aria-label="Embedded video"], article [data-testid="tweetPhoto"] video'
    )
    for container in gif_containers:
        video_tag = (
            container
            if isinstance(container, Tag) and container.name == "video"
            else container.find("video")
        )
        if isinstance(video_tag, Tag):  # Check if video_tag is a Tag
            poster = video_tag.get("poster")
            if poster and isinstance(poster, str) and poster not in processed_urls:
                media_strings.append(f"![GIF Thumbnail]({poster})")
                processed_urls.add(poster)

    return media_strings


def extract_metrics(tweet_element: Tag, debug: bool = False) -> Dict[str, str]:
    """
    Extract engagement metrics (replies, retweets, likes, views).

    Args:
        tweet_element: BeautifulSoup Tag containing the tweet
        enable_debug_logging: Whether to enable debug logging.

    Returns:
        Dictionary of engagement metrics
    """
    metrics = {
        "replies": "0",
        "retweets": "0",
        "likes": "0",
        "views": "0",  # Added views
    }
    if debug:
        logger.debug("--- Extracting metrics for tweet ---")

    # Common pattern: find the group containing interaction buttons
    action_bar = tweet_element.select_one('[role="group"]')
    if not action_bar:
        if debug:
            logger.debug(
                'Could not find action bar group [role="group"]. Dumping tweet element HTML:'
            )
            logger.debug(tweet_element.prettify()[:1000])  # Log first 1000 chars
        return metrics

    if debug:
        logger.debug(f'Found action bar [role="group"]: {action_bar.prettify()[:500]}')

    # --- Try parsing aria-label first for all metrics ---
    aria_label = action_bar.get("aria-label", "")
    if isinstance(aria_label, str) and aria_label:
        if debug:
            logger.debug(f"Found aria-label on action bar: '{aria_label}'")
        # Use regex to find counts for each metric
        replies_match = re.search(r"(\d[\d,]*) repl(?:y|ies)", aria_label, re.IGNORECASE)
        reposts_match = re.search(r"(\d[\d,]*) reposts", aria_label, re.IGNORECASE)
        likes_match = re.search(r"(\d[\d,]*) likes", aria_label, re.IGNORECASE)
        views_match = re.search(r"(\d[\d,]*) views", aria_label, re.IGNORECASE)

        if replies_match:
            metrics["replies"] = replies_match.group(1).replace(",", "")
        if reposts_match:
            metrics["retweets"] = reposts_match.group(1).replace(
                ",", ""
            )  # Note: aria-label uses "reposts"
        if likes_match:
            metrics["likes"] = likes_match.group(1).replace(",", "")
        if views_match:
            metrics["views"] = views_match.group(1).replace(",", "")

        if debug:
            logger.debug(f"Metrics extracted from aria-label: {metrics}")

    # --- Original button finding logic (modified selector) ---
    buttons = action_bar.select(
        'button[data-testid="reply"], button[data-testid="retweet"], button[data-testid="like"]'
    )
    if debug:
        logger.debug(f"Found {len(buttons)} potential metric buttons with updated selector.")

    for i, button in enumerate(buttons):
        # Ensure button is a Tag before accessing attributes like ['data-testid']
        if not isinstance(button, Tag):
            continue
        test_id = button.get("data-testid")  # Use .get() for safer access
        if not isinstance(test_id, str):
            continue  # Ensure test_id is a string

        if debug:
            logger.debug(f"Button {i}: test_id='{test_id}', HTML: {button.prettify()[:200]}")

        # Find the text within the button, usually in a span sibling to the icon path
        text_span = button.select_one(
            'span[data-testid="app-text-transition-container"] span span'
        )  # More specific selector
        count = "0"
        if text_span:
            raw_text = text_span.get_text(strip=True)
            if debug:
                logger.debug(f"  Found text span: '{raw_text}'")
            if raw_text.isdigit():
                count = raw_text
            elif "K" in raw_text or "M" in raw_text:  # Handle K/M suffixes
                count = raw_text  # Keep the formatted string like "1.2K"
            else:
                if debug:
                    logger.debug(f"  Text span content '{raw_text}' is not a digit or K/M format.")
        elif debug:
            logger.debug(
                "  Could not find text span with selector 'span[data-testid=\"app-text-transition-container\"] span span'"
            )

        # Only update if aria-label didn't provide a value (or if we want to overwrite)
        if test_id == "reply" and metrics["replies"] == "0":
            metrics["replies"] = count
            if debug:
                logger.debug(f"  Assigned replies = {count} (from button)")
        elif test_id == "retweet" and metrics["retweets"] == "0":
            metrics["retweets"] = count
            if debug:
                logger.debug(f"  Assigned retweets = {count} (from button)")
        elif test_id == "like" and metrics["likes"] == "0":
            metrics["likes"] = count
            if debug:
                logger.debug(f"  Assigned likes = {count} (from button)")

    # --- View count finding logic (fallback if not found in aria-label) ---
    if metrics["views"] == "0":
        if debug:
            logger.debug("--- Searching for Views metric (Fallback) ---")
        likes_button_text_container = action_bar.find(
            lambda tag: isinstance(tag, Tag) and tag.name == "span" and "Likes" in tag.get_text()
        )
        view_count = "0"
        if likes_button_text_container:
            if debug:
                # Ensure it's a Tag before prettifying
                log_text = str(likes_button_text_container)[:200]  # Fallback to string conversion
                if isinstance(likes_button_text_container, Tag):
                    log_text = likes_button_text_container.prettify()[:200]
                logger.debug(f"Found container potentially near Views: {log_text}")
            # Try finding a sibling or parent link that looks like view count
            view_link = likes_button_text_container.find_parent(
                "a", href=lambda h: isinstance(h, str) and ("/analytics" in h or "/status/" in h)
            )
            if isinstance(view_link, Tag):  # Check if view_link is a Tag
                if debug:
                    # Ensure it's a Tag before prettifying
                    log_text = str(view_link)[:300]  # Fallback
                    if isinstance(view_link, Tag):
                        log_text = view_link.prettify()[:300]
                    logger.debug(f"Found potential view link parent/sibling: {log_text}")
                # Text might be like "10K Views"
                view_text_span = view_link.select_one(
                    'span span span, span[aria-hidden="true"] span'
                )  # Adjust selector as needed, try common patterns
                if view_text_span:
                    view_count_text = view_text_span.get_text(strip=True)
                    if debug:
                        logger.debug(f"Found potential view count text span: '{view_count_text}'")
                    # Extract number part if possible
                    # Handle cases like "1,234 Views" or "10K Views" or just "123"
                    view_count_match = re.match(r"^([\d,\.]+[KkMm]?)\b", view_count_text)
                    if view_count_match:
                        view_count = view_count_match.group(1)
                        if debug:
                            logger.debug(f"Extracted view count: {view_count}")
                    elif view_count_text.isdigit():  # Handle plain numbers
                        view_count = view_count_text
                        if debug:
                            logger.debug(f"Extracted plain digit view count: {view_count}")
                    elif debug:
                        logger.debug(
                            f"View count text '{view_count_text}' did not match expected pattern."
                        )
                elif debug:
                    logger.debug("Could not find view count text span in the view link.")
            elif debug:
                logger.debug("Could not find parent/sibling link for views near the 'Likes' text.")
        elif debug:
            logger.debug("Could not find 'Likes' text span container to anchor view search.")

        # Assign the fallback view count if found
        metrics["views"] = view_count
    elif debug:
        logger.debug("View count already found from aria-label or button parsing.")

    if debug:
        logger.debug(f"Final metrics: {metrics}")

    return metrics


def extract_text_based_user_info(
    text: str, debug: bool = False
) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract name and handle from text content. Used by both followers and inbox parsers.

    Args:
        text: Raw text to extract from
        debug: Enable debug logging

    Returns:
        Tuple of (name, handle)
    """
    if not text:
        return None, None

    if debug:
        logger.debug(f"Extracting from text: '{text[:100]}{'...' if len(text) > 100 else ''}'")

    # Try different pattern matching approaches for Twitter followers list

    # Pattern 1: "Name@handle" without spaces
    match = re.search(r"^([^@]+)@([^\s·]+)", text)
    if match:
        name = match.group(1).strip()
        handle = match.group(2).split("Follow")[0].strip()

        # Clean up handle (remove any trailing characters)
        handle = re.sub(r"[^a-zA-Z0-9_].*$", "", handle)

        if debug:
            logger.debug(f"Extracted using pattern 1: name='{name}', handle='{handle}'")
        return name, handle

    # Pattern 2: Another common name@handle pattern
    match = re.search(r"^([^@]+)@([a-zA-Z0-9_]+)", text)
    if match:
        name = match.group(1).strip()
        handle = match.group(2)
        if debug:
            logger.debug(f"Extracted using pattern 2: name='{name}', handle='{handle}'")
        return name, handle

    # Pattern 3: Try to find any handle with @ symbol
    handle_match = re.search(r"@([a-zA-Z0-9_]+)", text)
    handle = handle_match.group(1) if handle_match else None

    name = None

    # Try to find name if handle was found
    if handle:
        # Look for name before handle
        name_match = re.search(r"^([^@]+)@", text)
        if name_match:
            name = name_match.group(1).strip()
            if debug:
                logger.debug(f"Found name before handle: '{name}'")

        # Pattern 4: Look for name in portions of text before the handle
        # For cases with format "Name \n @handle" or "Name • @handle"
        if not name:
            # Split text by common separators and find name-like text before the handle
            for sep in ["\n", "•", "·", "|", "-"]:
                if sep in text:
                    parts = text.split(sep)
                    for i, part in enumerate(parts):
                        if f"@{handle}" in parts[i + 1] if i + 1 < len(parts) else False:
                            potential_name = part.strip()
                            if potential_name and len(potential_name) < 30:
                                name = potential_name
                                if debug:
                                    logger.debug(f"Found name before separator '{sep}': '{name}'")
                                break
                    if name:
                        break

    # If still no name, try looking for reasonable name-like text
    if not name:
        # Pattern 5: Look for text that appears to be a name (not too long, no special chars)
        # Exclude common Twitter UI text
        ui_texts = ["follow", "following", "follows you", "click to follow", "to follow"]

        # First try to find name patterns near the beginning of the text
        first_part = text[: min(100, len(text))]
        potential_names = re.findall(r"([A-Za-z][A-Za-z\s'\-\.]{2,25})", first_part)

        for potential_name in potential_names:
            if potential_name.lower() not in ui_texts and not any(
                ui.lower() in potential_name.lower() for ui in ui_texts
            ):
                name = potential_name.strip()
                if debug:
                    logger.debug(f"Found potential name near beginning: '{name}'")
                break

    if debug:
        logger.debug(f"Final extraction: name='{name}', handle='{handle}'")

    return name, handle


def format_user_markdown_header(
    name: Optional[str],
    handle: Optional[str],
    additional_info: Optional[str] = None,
    handle_url: Optional[str] = None,
) -> str:
    """
    Format user information into a markdown header.

    Args:
        name: User's display name
        handle: User's handle (with or without @)
        additional_info: Additional info to append (like timestamp)
        handle_url: URL for the user's profile (can be relative)

    Returns:
        Formatted markdown header
    """
    header = "### "

    # Clean handle if provided (ensure no @ prefix for URL construction)
    clean_handle = handle.lstrip("@") if handle else None

    # Format based on available info
    if name and handle:
        # Use format_user_link if handle_url is provided, otherwise direct format
        if handle_url or clean_handle:
            url = handle_url or f"/{clean_handle}"
            user_link = format_user_link(name, handle, url)
            header += user_link
        else:
            header += f"{name} ({handle})"
    elif name:
        header += name
    elif handle:
        if clean_handle:
            url = handle_url or f"/{clean_handle}"
            header += f"[{handle}](https://x.com{url if url.startswith('/') else url})"
        else:
            header += handle
    else:
        header += "Unknown User"

    # Add additional info if provided
    if additional_info:
        header += f" · {additional_info}"

    return header


def process_html_with_parser(
    html: str,
    element_selector: str,
    processor_function: Callable,
    join_str: str = "\n\n",
    requirement_checker: Optional[Callable] = None,
    debug: bool = False,
) -> Optional[str]:
    """
    Generic function to process HTML with BeautifulSoup and convert to markdown.

    Args:
        html: Raw HTML to parse
        element_selector: CSS selector to find elements
        processor_function: Function to process each element
        join_str: String to join markdown blocks
        requirement_checker: Function to check if an element meets requirements
        debug: Enable debug logging

    Returns:
        Markdown string or None if parsing failed
    """
    try:
        soup = BeautifulSoup(html, "html.parser")

        if debug:
            logger.debug(f"HTML length: {len(html)} characters")
            title = soup.title.get_text() if soup.title else "No title found"
            logger.debug(f"Page title: {title}")

        # Find all elements using the selector
        elements = soup.select(element_selector)

        if not elements:
            logger.warning(f"No elements found using selector: {element_selector}")
            return None

        logger.info(f"Found {len(elements)} potential elements")

        # Process each element
        markdown_blocks = []
        valid_elements = 0

        for i, element in enumerate(elements):
            if debug:
                logger.debug(f"Processing element {i + 1}/{len(elements)}")

            # Skip if element doesn't meet requirements
            if requirement_checker and not requirement_checker(element):
                if debug:
                    logger.debug(f"Skipping element {i + 1} - doesn't meet requirements")
                continue

            # Process the element
            markdown = processor_function(element, debug=debug)
            if markdown:
                markdown_blocks.append(markdown)
                valid_elements += 1

        logger.info(f"Successfully processed {valid_elements} valid elements")

        # Join blocks
        markdown = join_str.join(markdown_blocks)

        if not markdown:
            logger.warning("Processing resulted in empty markdown")
            return None

        return markdown.strip()

    except Exception as e:
        logger.error(
            f"Error processing HTML with BeautifulSoup: {e}",
            exc_info=True,
        )
        return f"Error processing HTML with BeautifulSoup: {e}"
