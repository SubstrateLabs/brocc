from typing import Optional

from bs4 import BeautifulSoup

from brocc_li.utils.logger import logger

from .twitter_utils import (
    extract_media,
    extract_metrics,
    extract_tweet_content,
    extract_user_info,
    format_tweet_markdown,
)


def twitter_bookmarks_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        soup = BeautifulSoup(html, "html.parser")

        # Find all tweets using the container selector
        tweets = soup.select('article[data-testid="tweet"]')
        logger.info(f"Found {len(tweets)} bookmarked tweets in the HTML")

        if not tweets:
            logger.warning("No bookmarked tweets found in HTML")
            return None

        output_blocks = []

        # Add a header for the bookmarks section
        output_blocks.append("## Your Bookmarks")

        for i, tweet in enumerate(tweets):
            if debug:
                logger.debug(f"Processing bookmarked tweet {i + 1}/{len(tweets)}")

            # Extract tweet metadata
            user_info = extract_user_info(tweet, debug=debug)
            if debug:
                logger.debug(f"Extracted user info: {user_info}")

            # Extract tweet content
            content = extract_tweet_content(tweet, debug=debug)
            if debug:
                logger.debug(f"Tweet content length: {len(content)} chars")

            # Extract media
            media_strings = extract_media(tweet, debug=debug)
            if debug:
                logger.debug(f"Found {len(media_strings)} media items")

            # Extract metrics
            metrics = extract_metrics(tweet, debug=debug)
            if debug:
                logger.debug(f"Engagement metrics: {metrics}")

            # Format the full tweet block
            tweet_block = format_tweet_markdown(user_info, content, media_strings, metrics)
            output_blocks.append(tweet_block)

        # Join all blocks with double newlines
        markdown = "\n\n".join(output_blocks)

        if not markdown:
            logger.warning("BeautifulSoup extraction resulted in empty markdown")
            return None

        logger.info("BeautifulSoup conversion successful")
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error converting HTML with BeautifulSoup",
            exc_info=True,
        )
        return f"Error converting HTML with BeautifulSoup: {e}"
