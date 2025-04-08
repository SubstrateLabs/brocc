from typing import Dict, List, Optional, Set

from bs4 import BeautifulSoup, Tag

from brocc_li.utils.logger import logger

DEBUG = False


def _format_user_link(name: str, handle: str, handle_url: str) -> str:
    """Format user name and handle as a linked header."""
    # Strip @ from the beginning if present for cleaner URLs
    clean_handle = handle.lstrip("@")

    # If handle URL is just a relative path, make it absolute
    profile_url = handle_url
    if profile_url.startswith("/"):
        profile_url = f"https://x.com{profile_url}"

    # Format as [name](url) (@handle)
    return f"[{name}]({profile_url}) (@{clean_handle})"


def _extract_tweet_content(tweet_element: Tag) -> str:
    """Extract and format tweet text content."""
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

    # Get plain text content - preserve line breaks
    # Get each text node's content individually, then join with proper whitespace
    # This prevents duplicate content issues
    text_parts = []
    for text_node in tweet_text_element.find_all(text=True, recursive=True):
        # The text_node is a NavigableString, which doesn't have strip() method directly
        # Convert to str first and then strip
        if text_node and isinstance(text_node, str):
            text = text_node.strip()
        else:
            text = str(text_node).strip()

        # Check if parent exists and is not a link
        parent = getattr(text_node, "parent", None)
        is_link_text = parent and getattr(parent, "name", "") == "a"

        if text and not is_link_text:  # Skip link text as we handle those separately
            text_parts.append(text)

    # Join with spaces, but dedup adjacent elements
    content = ""
    prev_part = ""
    for part in text_parts:
        if part != prev_part:  # Skip if same as previous part to avoid duplication
            if content:
                content += " "
            content += part
            prev_part = part

    # Replace all links with markdown format
    for link_text, href in links:
        # Create the proper markdown link
        markdown_link = f"[{link_text}]({href})"
        content = content.replace(link_text, markdown_link)

    return content


def _extract_media(tweet_element: Tag) -> List[str]:
    """Extract media elements (images, videos) from a tweet."""
    media_strings = []
    processed_urls: Set[str] = set()  # Track processed URLs to avoid duplicates

    # Look for images
    images = tweet_element.select('[data-testid="tweetPhoto"] img')
    for img in images:
        src = img.get("src")
        if (
            src
            and isinstance(src, str)
            and "profile_images" not in src
            and src not in processed_urls
        ):  # Skip profile pics and duplicates
            alt = img.get("alt", "image")
            media_strings.append(f"![{alt}]({src})")
            processed_urls.add(src)

    # Look for videos
    videos = tweet_element.select("video")
    for video in videos:
        poster = video.get("poster")
        if (
            poster
            and isinstance(poster, str)
            and "profile_images" not in poster
            and poster not in processed_urls
        ):
            media_strings.append(f"[video]({poster})")
            processed_urls.add(poster)
        else:
            # Try to get the source
            source = video.select_one("source")
            if source:
                src = source.get("src")
                if src and isinstance(src, str) and src not in processed_urls:
                    # Skip blob URLs which can be truncated/unusable
                    if not src.startswith("blob:"):
                        media_strings.append(f"[video]({src})")
                        processed_urls.add(src)

    # Look for GIFs
    gifs = tweet_element.select('[data-testid="tweetGif"] img')
    for gif in gifs:
        src = gif.get("src")
        if src and isinstance(src, str) and src not in processed_urls:
            media_strings.append(f"[gif]({src})")
            processed_urls.add(src)

    return media_strings


def _extract_metrics(tweet_element: Tag) -> Dict[str, str]:
    """Extract engagement metrics (likes, retweets, replies)."""
    metrics = {
        "replies": "0",
        "retweets": "0",
        "likes": "0",
    }

    # Get reply count
    reply_element = tweet_element.select_one('[data-testid="reply"]')
    if reply_element:
        span = reply_element.select_one("span")
        if span:
            metrics["replies"] = span.get_text().strip()

    # Get retweet count
    retweet_element = tweet_element.select_one('[data-testid="retweet"]')
    if retweet_element:
        span = retweet_element.select_one("span")
        if span:
            metrics["retweets"] = span.get_text().strip()

    # Get like count
    like_element = tweet_element.select_one('[data-testid="like"]')
    if like_element:
        span = like_element.select_one("span")
        if span:
            metrics["likes"] = span.get_text().strip()

    return metrics


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
        # Add other relevant section headers here
    ]

    for relevant in relevant_sections:
        if relevant in header_text:
            return True

    # Default to excluding unknown section headers
    return False


def convert_twitter_feed_html_to_md(
    html: str, url: Optional[str] = None, title: Optional[str] = None
) -> Optional[str]:
    """
    Convert Twitter HTML to structured Markdown using BeautifulSoup,
    extracting tweets and sections with proper formatting.

    Args:
        html: The HTML content to convert
        url: Optional URL for logging
        title: Optional title (unused)

    Returns:
        Formatted markdown text, or None on failure.
    """
    try:
        logger.info(f"Parsing HTML for {url or 'unknown URL'} using BeautifulSoup")
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
                # Extract the username (display name)
                name_element = user_name_section.select_one('div[dir="ltr"] span span')
                if name_element:
                    name = name_element.get_text(strip=True)
                    if DEBUG:
                        logger.debug(f"Found username: {name}")

                # Find the handle specifically - need to extract only the @username part
                handle_elements = user_name_section.select('div[dir="ltr"] span')

                # Loop through spans to find the one with the @handle
                for span in handle_elements:
                    span_text = span.get_text(strip=True)
                    if span_text.startswith("@"):
                        handle = span_text
                        # Find the link in this same element
                        a_tag = span.select_one("a")
                        if a_tag and a_tag.get("href"):
                            href_attr = a_tag.get("href")
                            if isinstance(href_attr, str):
                                handle_url = href_attr
                                if DEBUG:
                                    logger.debug(f"Found handle: {handle}, URL: {handle_url}")
                        break

            # Get the timestamp
            time_element = tweet.select_one("time")
            if time_element:
                timestamp = time_element.get_text(strip=True)
                if DEBUG:
                    logger.debug(f"Found timestamp: {timestamp}")

            # Extract tweet content
            content = _extract_tweet_content(tweet)
            if DEBUG and content:
                logger.debug(f"Tweet content length: {len(content)} chars")

            # Extract media
            media_strings = _extract_media(tweet)
            if DEBUG:
                logger.debug(f"Found {len(media_strings)} media items")

            # Extract metrics
            metrics = _extract_metrics(tweet)
            if DEBUG:
                logger.debug(f"Engagement metrics: {metrics}")

            # Format the tweet header
            header = ""

            # Create the full header with proper linking
            if name and handle and handle_url:
                # Format as: ### [name](profile_url) (@handle) timestamp
                user_link = _format_user_link(name, handle, handle_url)
                header = f"### {user_link}"
                if timestamp:
                    header += f" {timestamp}"
            else:
                # Fallback to simple format if we're missing info
                header_parts = []
                if name:
                    header_parts.append(name)
                if handle:
                    header_parts.append(handle)
                if timestamp:
                    header_parts.append(timestamp)
                header = f"### {' '.join(header_parts)}"
                if DEBUG:
                    logger.debug(f"Using fallback header format: {header}")

            # Format the full tweet block
            tweet_block = header
            if content:
                tweet_block += f"\n{content}"

            if media_strings:
                # Join media with line breaks for better formatting
                tweet_block += f"\n\n{' '.join(media_strings)}"

            # Add engagement metrics if available
            if any(val != "0" for val in metrics.values()):
                tweet_block += (
                    f"\n\n💬 {metrics['replies']} ⟲ {metrics['retweets']} ❤️ {metrics['likes']}"
                )

            output_blocks.append(tweet_block)

        # Join all blocks with double newlines
        markdown = "\n\n".join(output_blocks)

        if not markdown:
            logger.warning(
                f"BeautifulSoup extraction resulted in empty markdown for {url or 'unknown URL'}"
            )
            return None

        logger.info(
            f"BeautifulSoup conversion successful for {url or 'unknown URL'}, markdown length: {len(markdown)}"
        )
        return markdown.strip()  # Ensure no leading/trailing whitespace on the final output
    except Exception as e:
        logger.error(
            f"Error converting HTML with BeautifulSoup for {url or 'unknown URL'}: {e}",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error converting HTML with BeautifulSoup: {e}"
