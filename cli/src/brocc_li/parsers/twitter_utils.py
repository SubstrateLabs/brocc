import re
from typing import Dict, List, Set

from bs4 import Tag

from brocc_li.utils.logger import logger

# Set this to True to enable debug logging
DEBUG = False


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


def extract_tweet_content(tweet_element: Tag) -> str:
    """
    Extract and format tweet text content.

    Args:
        tweet_element: BeautifulSoup Tag containing the tweet

    Returns:
        Formatted tweet content as markdown string
    """
    tweet_text_element = tweet_element.select_one('[data-testid="tweetText"]')
    if not tweet_text_element:
        if DEBUG:
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


def extract_media(tweet_element: Tag) -> List[str]:
    """
    Extract media elements (images, videos, gifs) from a tweet.

    Args:
        tweet_element: BeautifulSoup Tag containing the tweet

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
                    if DEBUG:
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
                    if DEBUG:
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


def extract_metrics(tweet_element: Tag) -> Dict[str, str]:
    """
    Extract engagement metrics (replies, retweets, likes, views).

    Args:
        tweet_element: BeautifulSoup Tag containing the tweet

    Returns:
        Dictionary of engagement metrics
    """
    metrics = {
        "replies": "0",
        "retweets": "0",
        "likes": "0",
        "views": "0",  # Added views
    }
    if DEBUG:
        logger.debug("--- Extracting metrics for tweet ---")

    # Common pattern: find the group containing interaction buttons
    action_bar = tweet_element.select_one('[role="group"]')
    if not action_bar:
        if DEBUG:
            logger.debug(
                'Could not find action bar group [role="group"]. Dumping tweet element HTML:'
            )
            logger.debug(tweet_element.prettify()[:1000])  # Log first 1000 chars
        return metrics

    if DEBUG:
        logger.debug(f'Found action bar [role="group"]: {action_bar.prettify()[:500]}')

    # --- Try parsing aria-label first for all metrics ---
    aria_label = action_bar.get("aria-label", "")
    if isinstance(aria_label, str) and aria_label:
        if DEBUG:
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

        if DEBUG:
            logger.debug(f"Metrics extracted from aria-label: {metrics}")

    # --- Original button finding logic (modified selector) ---
    buttons = action_bar.select(
        'button[data-testid="reply"], button[data-testid="retweet"], button[data-testid="like"]'
    )
    if DEBUG:
        logger.debug(f"Found {len(buttons)} potential metric buttons with updated selector.")

    for i, button in enumerate(buttons):
        # Ensure button is a Tag before accessing attributes like ['data-testid']
        if not isinstance(button, Tag):
            continue
        test_id = button.get("data-testid")  # Use .get() for safer access
        if not isinstance(test_id, str):
            continue  # Ensure test_id is a string

        if DEBUG:
            logger.debug(f"Button {i}: test_id='{test_id}', HTML: {button.prettify()[:200]}")

        # Find the text within the button, usually in a span sibling to the icon path
        text_span = button.select_one(
            'span[data-testid="app-text-transition-container"] span span'
        )  # More specific selector
        count = "0"
        if text_span:
            raw_text = text_span.get_text(strip=True)
            if DEBUG:
                logger.debug(f"  Found text span: '{raw_text}'")
            if raw_text.isdigit():
                count = raw_text
            elif "K" in raw_text or "M" in raw_text:  # Handle K/M suffixes
                count = raw_text  # Keep the formatted string like "1.2K"
            else:
                if DEBUG:
                    logger.debug(f"  Text span content '{raw_text}' is not a digit or K/M format.")
        elif DEBUG:
            logger.debug(
                "  Could not find text span with selector 'span[data-testid=\"app-text-transition-container\"] span span'"
            )

        # Only update if aria-label didn't provide a value (or if we want to overwrite)
        if test_id == "reply" and metrics["replies"] == "0":
            metrics["replies"] = count
            if DEBUG:
                logger.debug(f"  Assigned replies = {count} (from button)")
        elif test_id == "retweet" and metrics["retweets"] == "0":
            metrics["retweets"] = count
            if DEBUG:
                logger.debug(f"  Assigned retweets = {count} (from button)")
        elif test_id == "like" and metrics["likes"] == "0":
            metrics["likes"] = count
            if DEBUG:
                logger.debug(f"  Assigned likes = {count} (from button)")

    # --- View count finding logic (fallback if not found in aria-label) ---
    if metrics["views"] == "0":
        if DEBUG:
            logger.debug("--- Searching for Views metric (Fallback) ---")
        likes_button_text_container = action_bar.find(
            lambda tag: isinstance(tag, Tag) and tag.name == "span" and "Likes" in tag.get_text()
        )
        view_count = "0"
        if likes_button_text_container:
            if DEBUG:
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
                if DEBUG:
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
                    if DEBUG:
                        logger.debug(f"Found potential view count text span: '{view_count_text}'")
                    # Extract number part if possible
                    # Handle cases like "1,234 Views" or "10K Views" or just "123"
                    view_count_match = re.match(r"^([\d,\.]+[KkMm]?)\b", view_count_text)
                    if view_count_match:
                        view_count = view_count_match.group(1)
                        if DEBUG:
                            logger.debug(f"Extracted view count: {view_count}")
                    elif view_count_text.isdigit():  # Handle plain numbers
                        view_count = view_count_text
                        if DEBUG:
                            logger.debug(f"Extracted plain digit view count: {view_count}")
                    elif DEBUG:
                        logger.debug(
                            f"View count text '{view_count_text}' did not match expected pattern."
                        )
                elif DEBUG:
                    logger.debug("Could not find view count text span in the view link.")
            elif DEBUG:
                logger.debug("Could not find parent/sibling link for views near the 'Likes' text.")
        elif DEBUG:
            logger.debug("Could not find 'Likes' text span container to anchor view search.")

        # Assign the fallback view count if found
        metrics["views"] = view_count
    elif DEBUG:
        logger.debug("View count already found from aria-label or button parsing.")

    if DEBUG:
        logger.debug(f"Final metrics: {metrics}")

    return metrics
