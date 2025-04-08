from typing import List, Optional

from bs4 import BeautifulSoup, Tag

from brocc_li.utils.logger import logger

# Import necessary helpers from twitter_utils
from .twitter_utils import (
    extract_media,
    extract_metrics,
    extract_tweet_content,
    format_metrics,
    format_user_link,
)


def twitter_likes_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Parses the HTML content of a Twitter user's likes page and converts it to Markdown.

    Args:
        html: The HTML content as a string.
        debug: Whether to enable debug logging.

    Returns:
        A string containing the Markdown representation of the tweets,
        or None if parsing fails.
    """
    logger.info(
        f"Starting Twitter likes HTML to Markdown conversion for HTML of length {len(html)}"
    )

    if not html:
        logger.warning("Received empty HTML string for Twitter likes parsing.")
        return None

    try:
        soup = BeautifulSoup(html, "html.parser")
        output_blocks: List[str] = []

        # Main page title - might be useful context
        page_title_h2 = soup.select_one('h2[role="heading"] > div > div > div')
        if page_title_h2:
            title_text = page_title_h2.get_text(strip=True)
            output_blocks.append(f"# {title_text}")
            if debug:
                logger.debug(f"Found page title: {title_text}")
        else:
            output_blocks.append("# Twitter Likes Feed (Parsed)")  # Default title

        # Find all tweets using the standard container selector
        tweets = soup.select('article[data-testid="tweet"]')
        logger.info(f"Found {len(tweets)} liked tweets in the HTML")

        if not tweets:
            logger.warning(
                "No tweets found using selector 'article[data-testid=\"tweet\"]'. HTML structure might have changed."
            )
            # Log a snippet of the HTML for debugging structure issues
            if debug:
                logger.debug(f"HTML snippet (first 1000 chars): {html[:1000]}")
            # Combine output blocks and add the "No tweets found" message
            existing_output = "\n\n".join(output_blocks)
            return f"{existing_output}\n\nNo tweets found."

        for i, tweet in enumerate(tweets):
            if debug:
                logger.debug(f"--- Processing liked tweet {i + 1}/{len(tweets)} ---")

            # Extract tweet metadata (might need adjustments for likes page structure)
            name = ""
            handle = ""
            handle_url = ""
            timestamp = ""

            user_name_section = tweet.select_one('[data-testid="User-Name"]')
            if user_name_section:
                if debug:
                    logger.debug(f"Tweet {i + 1}: Found User-Name section")

                # Extract name
                name_element = user_name_section.select_one('div[dir="ltr"] span span')
                if name_element:
                    name = name_element.get_text(strip=True)
                    if debug:
                        logger.debug(f"Found username: '{name}'")

                # Extract handle and URL (simplified approach, might need refinement)
                handle_link = user_name_section.find(
                    "a",
                    href=lambda h: isinstance(h, str) and h.startswith("/") and "/status/" not in h,
                )
                if isinstance(handle_link, Tag):
                    href = handle_link.get("href")
                    if isinstance(href, str):
                        handle_url = href
                        # Find the handle within the link text or spans
                        potential_handle = ""
                        for span in handle_link.select("span"):
                            if isinstance(span, Tag):
                                span_text = span.get_text(strip=True)
                                if span_text.startswith("@"):
                                    potential_handle = span_text
                                    break
                        if potential_handle:
                            handle = potential_handle
                        else:
                            # Fallback if @handle isn't directly in a span
                            handle = "@" + href.lstrip("/")

                        if debug:
                            logger.debug(
                                f"Found handle: '{handle}', URL: '{handle_url}' (simplified extraction)"
                            )
                elif debug:
                    logger.debug("Could not find handle link with simplified approach.")

            else:
                if debug:
                    logger.debug(f"Tweet {i + 1}: Could not find User-Name section.")

            # Get timestamp
            time_element = tweet.select_one("time")
            if time_element:
                timestamp = time_element.get_text(strip=True)
                if debug:
                    logger.debug(f"Found timestamp: '{timestamp}'")

            # Extract content, media, metrics using utils
            content = extract_tweet_content(tweet)
            if debug:
                logger.debug(f"Tweet content length: {len(content)} chars")

            media_strings = extract_media(tweet)
            if debug:
                logger.debug(f"Found {len(media_strings)} media items")

            metrics = extract_metrics(tweet)
            if debug:
                logger.debug(f"Engagement metrics: {metrics}")

            # Format the tweet header
            header = ""
            if name and handle and handle_url:
                user_link = format_user_link(name, handle, handle_url)
                header = f"### {user_link}"
                if timestamp:
                    header += f" {timestamp}"
                if debug:
                    logger.debug(f"Formatted header: '{header}'")
            else:
                # Fallback if info is missing
                header_parts = []
                if name:
                    header_parts.append(name)
                if handle:
                    header_parts.append(handle)
                if timestamp:
                    header_parts.append(timestamp)
                header = f"### {' '.join(header_parts)}"
                if debug:
                    logger.debug(
                        f"Using fallback header: '{header}' (name='{name}', handle='{handle}', url='{handle_url}')"
                    )

            # Format the full tweet block
            tweet_block = header
            if content:
                # Use triple quotes for multi-line f-string or ensure newlines are escaped
                tweet_block += f"\n\n{content}"  # Add extra newline for readability

            if media_strings:
                # Join media items with a space, add double newline before
                tweet_block += f"\n\n{' '.join(media_strings)}"

            metrics_str = format_metrics(metrics)
            if metrics_str:
                # Add double newline before metrics
                tweet_block += f"\n\n{metrics_str}"

            output_blocks.append(tweet_block)
            if debug:
                logger.debug(f"--- Finished processing liked tweet {i + 1} ---")

        # Join all blocks with double newlines
        markdown_output = "\n\n".join(output_blocks)

        if not markdown_output.strip():
            logger.warning("Parsed Likes HTML but resulted in empty markdown output.")
            return None  # Or return the title block if present

        logger.info(
            f"Successfully parsed Twitter likes HTML. Markdown length: {len(markdown_output)}"
        )
        return markdown_output.strip()

    except Exception as e:
        logger.error(f"Error parsing Twitter likes HTML: {e}", exc_info=True)
        # Return error message in the output for easier debugging via test output
        return f"Error converting Twitter likes HTML to Markdown: {e}"


def parse_twitter_likes(html_content: str) -> list | None:
    """
    Parses the HTML content of a Twitter/X likes page.

    Args:
        html_content: The raw HTML string.

    Returns:
        A list of dictionaries, each representing a liked tweet,
        or None if parsing fails.
        (Currently returns None as a placeholder - focus is on twitter_likes_html_to_md).
    """
    # TODO: Implement actual parsing logic to return structured data if needed.
    # For now, this function remains a placeholder as the main goal was Markdown conversion.
    logger.warning(
        "parse_twitter_likes function is not fully implemented. Use twitter_likes_html_to_md for Markdown output."
    )
    print("Warning: parse_twitter_likes function is not implemented yet.")
    return None
