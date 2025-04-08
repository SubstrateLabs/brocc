from typing import List, Optional

from bs4 import BeautifulSoup

from brocc_li.utils.logger import logger

# Import necessary helpers from twitter_utils
from .twitter_utils import (
    extract_media,
    extract_metrics,
    extract_tweet_content,
    extract_user_info,
    format_tweet_markdown,
)


def twitter_likes_html_to_md(html: str, debug: bool = False) -> Optional[str]:
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
            user_info = extract_user_info(tweet, debug=debug)
            if debug:
                logger.debug(f"Extracted user info: {user_info}")

            # Extract content, media, metrics using utils
            content = extract_tweet_content(tweet, debug=debug)
            if debug:
                logger.debug(f"Tweet content length: {len(content)} chars")

            media_strings = extract_media(tweet, debug=debug)
            if debug:
                logger.debug(f"Found {len(media_strings)} media items")

            metrics = extract_metrics(tweet, debug=debug)
            if debug:
                logger.debug(f"Engagement metrics: {metrics}")

            # Format the full tweet block
            tweet_block = format_tweet_markdown(user_info, content, media_strings, metrics)

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
    return None
