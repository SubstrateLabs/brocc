from typing import Optional, Tuple

from bs4 import Tag

from brocc_li.utils.logger import logger


def extract_video_info(container: Tag, debug: bool = False) -> Optional[Tuple[str, str]]:
    """Extracts video title and URL from a YouTube container Tag."""
    # Try common selectors used in home and history
    selectors = ["a#video-title-link", "a#video-title"]
    title_tag: Optional[Tag] = None
    for selector in selectors:
        title_tag = container.select_one(selector)
        if title_tag:
            break  # Found one

    if not isinstance(title_tag, Tag):
        if debug:
            logger.debug("  Could not find video title/URL tag using selectors: %s", selectors)
        return None

    # Ensure title is a string before processing
    title_val = title_tag.get("title")
    title_text = title_tag.text.strip()
    # Prioritize non-empty title attribute, fall back to text
    title = title_val if isinstance(title_val, str) and title_val else title_text

    href = title_tag.get("href")

    # Title must be non-empty, href must be a string
    if not title or not isinstance(href, str):
        if debug:
            logger.debug(
                "  Found title tag, but title is empty or href attribute is missing/invalid. Title: '%s', Href: '%s'",
                title,
                href,
            )
        return None

    video_url = "https://www.youtube.com" + href
    # Clean potential "Watched " prefix from history titles
    clean_title = title.removeprefix("Watched ")  # Now title is guaranteed non-empty str

    if debug:
        logger.debug("  Extracted Video Info:")
        logger.debug(f"    Title: {clean_title}")
        logger.debug(f"    URL: {video_url}")

    return clean_title, video_url


def extract_channel_info(
    container: Tag, debug: bool = False
) -> Optional[Tuple[str, Optional[str]]]:
    """Extracts channel name and URL from a YouTube container Tag."""
    # --- Strategy 1: Look for `ytd-channel-name a` --- #
    channel_tag_1: Optional[Tag] = container.select_one("ytd-channel-name a")
    if isinstance(channel_tag_1, Tag):
        name = channel_tag_1.text.strip()
        if name:  # Ensure name is not empty string
            # If we are here, name is a non-empty string.
            channel_url: Optional[str] = None
            href = channel_tag_1.get("href")
            if isinstance(href, str):
                channel_url = "https://www.youtube.com" + href
            if debug:
                logger.debug(
                    "  Extracted Channel Info (Strat 1: 'ytd-channel-name a'): Name: %s, URL: %s",
                    name,  # Use name directly, it's a str here
                    channel_url,
                )
            # Return immediately since name is confirmed str
            return name, channel_url

    # --- Strategy 2: Look for `ytd-channel-name` text, link might be separate --- #
    # Only reached if Strategy 1 failed to find a non-empty name
    channel_name_tag_2: Optional[Tag] = container.select_one("ytd-channel-name")
    if isinstance(channel_name_tag_2, Tag):
        name = channel_name_tag_2.text.strip()
        if name:  # Ensure name is not empty string
            # If we are here, name is a non-empty string.
            channel_url: Optional[str] = None
            # Look for a link as the next sibling
            next_a = channel_name_tag_2.find_next_sibling("a")
            if isinstance(next_a, Tag):
                href = next_a.get("href")
                if isinstance(href, str) and (
                    href.startswith("/@") or href.startswith("/channel/")
                ):
                    channel_url = "https://www.youtube.com" + href
            if debug:
                logger.debug(
                    "  Extracted Channel Info (Strat 2: 'ytd-channel-name' + sibling): Name: %s, URL: %s",
                    name,  # Use name directly, it's a str here
                    channel_url,
                )
            # Return immediately since name is confirmed str
            return name, channel_url

    # --- If neither strategy worked --- #
    if debug:
        logger.debug("  Could not find channel name/URL using known strategies.")
    return None
