from typing import List, Optional

from bs4 import BeautifulSoup, Tag

from brocc_li.utils.logger import logger

from .twitter_utils import (
    extract_media,
    extract_metrics,
    extract_tweet_content,
    format_metrics,
    format_user_link,
)

# Enable debug logging temporarily to diagnose the issue
DEBUG = True


def _is_section_relevant(header_text: str) -> bool:
    """Check if a section header is relevant to include in output."""
    # Skip these sections as they're not content-relevant
    skip_sections = [
        "To view keyboard shortcuts",
        "Messages",
        "Pinned by people you follow",
        "Live on X",
        "Who to follow",
        "Explore",
    ]

    for skip_text in skip_sections:
        if skip_text in header_text:
            return False

    # Filter actual content sections we want to keep
    relevant_sections = [
        "Your Home Timeline",
        "Trending now",
    ]

    for relevant in relevant_sections:
        if relevant in header_text:
            return True

    # Default to excluding unknown section headers
    return False


def twitter_feed_html_to_md(html: str) -> Optional[str]:
    """
    Convert Twitter HTML to structured Markdown using BeautifulSoup,
    extracting tweets and sections with proper formatting.

    Args:
        html: The HTML content to convert

    Returns:
        Formatted markdown text, or None on failure.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")

        # Extract structure - we'll collect sections and tweets
        output_blocks: List[str] = []

        # 1. First look for section headers (like "Trending now")
        section_headers = soup.select('h2, [role="heading"][aria-level="2"]')
        if DEBUG:
            logger.debug(f"Found {len(section_headers)} section headers")

        for header in section_headers:
            header_text = header.get_text(strip=True)
            if header_text and _is_section_relevant(header_text):
                if DEBUG:
                    logger.debug(f"Adding section header: {header_text}")
                output_blocks.append(f"## {header_text}")

        # 2. Find all tweets using the container selector
        tweets = soup.select('article[data-testid="tweet"]')
        logger.info(f"Found {len(tweets)} tweets in the HTML")

        for i, tweet in enumerate(tweets):
            if DEBUG:
                logger.debug(f"Processing tweet {i + 1}/{len(tweets)}")

            # Extract tweet metadata
            name = ""
            handle = ""
            handle_url = ""
            timestamp = ""

            # Get name and handle - this needs more precision for Twitter's HTML structure
            user_name_section = tweet.select_one('[data-testid="User-Name"]')
            if user_name_section:
                if DEBUG:
                    logger.debug(f"Tweet {i + 1}: Found User-Name section")
                    logger.debug(f"User-Name HTML: {user_name_section.prettify()[:300]}")

                # Extract the username (display name)
                name_element = user_name_section.select_one('div[dir="ltr"] span span')
                if name_element:
                    name = name_element.get_text(strip=True)
                    if DEBUG:
                        logger.debug(f"Found username: '{name}'")
                else:
                    if DEBUG:
                        logger.debug("Could not find name element with the current selector")
                        # Try a broader selector for debugging
                        all_spans = user_name_section.select("span")
                        logger.debug(f"Found {len(all_spans)} spans in the User-Name section")
                        for idx, span in enumerate(all_spans):
                            logger.debug(f"Span {idx}: '{span.get_text(strip=True)}'")

                # Find the handle specifically - need to extract only the @username part
                handle_elements = user_name_section.select('div[dir="ltr"] span')
                if DEBUG:
                    logger.debug(f"Found {len(handle_elements)} handle candidate elements")

                # Loop through spans to find the one with the @handle
                for span_idx, span in enumerate(handle_elements):
                    span_text = span.get_text(strip=True)
                    if DEBUG:
                        logger.debug(f"Span {span_idx} text: '{span_text}'")

                    if span_text.startswith("@"):
                        handle = span_text
                        if DEBUG:
                            logger.debug(f"Found handle: '{handle}'")

                        # Find the link in this same element
                        a_tag = span.select_one("a")
                        if a_tag:
                            if DEBUG:
                                logger.debug(
                                    f"Found a_tag in handle span: {a_tag.prettify()[:100]}"
                                )
                            if a_tag.get("href"):
                                href_attr = a_tag.get("href")
                                if isinstance(href_attr, str):
                                    handle_url = href_attr
                                    if DEBUG:
                                        logger.debug(f"Found handle URL: '{handle_url}'")
                                else:
                                    if DEBUG:
                                        logger.debug(
                                            f"href attribute is not a string: {type(href_attr)}"
                                        )
                            else:
                                if DEBUG:
                                    logger.debug("a_tag exists but has no href attribute")
                        else:
                            # If no direct link in span, try to find a parent a tag
                            if DEBUG:
                                logger.debug(
                                    "No direct a_tag found in handle span, looking for parent link"
                                )
                            parent_a = span.find_parent("a")
                            if isinstance(parent_a, Tag) and parent_a.get("href"):
                                href_attr = parent_a.get("href")
                                if isinstance(href_attr, str):
                                    handle_url = href_attr
                                    if DEBUG:
                                        logger.debug(
                                            f"Found handle URL from parent a: '{handle_url}'"
                                        )
                        break

                if not handle:
                    if DEBUG:
                        logger.debug("Could not find handle with @, trying different approach")
                    # Try a more direct approach - find any link that might be the user profile
                    profile_links = user_name_section.select('a[role="link"]')
                    for link_idx, link in enumerate(profile_links):
                        href = link.get("href", "")
                        if DEBUG:
                            logger.debug(f"Profile link {link_idx} href: '{href}'")
                        if (
                            isinstance(href, str)
                            and href.startswith("/")
                            and "/status/" not in href
                        ):
                            handle_url = href
                            # Try to extract handle text from it
                            for span in link.select("span"):
                                span_text = span.get_text(strip=True)
                                if span_text.startswith("@"):
                                    handle = span_text
                                    if DEBUG:
                                        logger.debug(
                                            f"Found handle from profile link: '{handle}', URL: '{handle_url}'"
                                        )
                                    break
                            if handle:  # If we found the handle, stop looking
                                break

            # Get the timestamp
            time_element = tweet.select_one("time")
            if time_element:
                timestamp = time_element.get_text(strip=True)
                if DEBUG:
                    logger.debug(f"Found timestamp: '{timestamp}'")

            # Extract tweet content
            content = extract_tweet_content(tweet)
            if DEBUG:
                logger.debug(f"Tweet content length: {len(content)} chars")

            # Extract media
            media_strings = extract_media(tweet)
            if DEBUG:
                logger.debug(f"Found {len(media_strings)} media items")

            # Extract metrics
            metrics = extract_metrics(tweet)
            if DEBUG:
                logger.debug(f"Engagement metrics: {metrics}")

            # Format the tweet header
            header = ""

            # Create the full header with proper linking
            if name and handle and handle_url:
                if DEBUG:
                    logger.debug(
                        f"Creating linked header with name='{name}', handle='{handle}', handle_url='{handle_url}'"
                    )
                # Format as: ### [name](profile_url) (@handle) timestamp
                user_link = format_user_link(name, handle, handle_url)
                if DEBUG:
                    logger.debug(f"Formatted user link: '{user_link}'")
                header = f"### {user_link}"
                if timestamp:
                    header += f" {timestamp}"
            else:
                # Fallback to simple format if we're missing info
                if DEBUG:
                    logger.debug(
                        f"Missing user info: name='{name}', handle='{handle}', handle_url='{handle_url}'"
                    )
                    logger.debug("Using fallback header format without links")
                header_parts = []
                if name:
                    header_parts.append(name)
                if handle:
                    header_parts.append(handle)
                if timestamp:
                    header_parts.append(timestamp)
                header = f"### {' '.join(header_parts)}"
                if DEBUG:
                    logger.debug(f"Final fallback header: '{header}'")

            # Format the full tweet block
            tweet_block = header
            if content:
                tweet_block += f"\n{content}"

            if media_strings:
                # Join media with line breaks for better formatting
                tweet_block += f"\n\n{' '.join(media_strings)}"

            # Add engagement metrics if available
            metrics_str = format_metrics(metrics)
            if metrics_str:
                tweet_block += f"\n\n{metrics_str}"

            output_blocks.append(tweet_block)

        # Join all blocks with double newlines
        markdown = "\n\n".join(output_blocks)

        if not markdown:
            logger.warning("BeautifulSoup extraction resulted in empty markdown")
            return None

        logger.info("BeautifulSoup conversion successful")
        return markdown.strip()  # Ensure no leading/trailing whitespace on the final output
    except Exception as e:
        logger.error(
            "Error converting HTML with BeautifulSoup",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error converting HTML with BeautifulSoup: {e}"
