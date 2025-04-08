from typing import List, Optional, Set

from bs4 import BeautifulSoup

from brocc_li.utils.logger import logger

from .twitter_utils import (
    extract_media,
    extract_metrics,
    extract_tweet_content,
    extract_user_info,
    format_tweet_markdown,
)


def twitter_thread_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        soup = BeautifulSoup(html, "html.parser")

        # Find all tweets using the container selector
        # In thread view, the main tweet and replies are usually articles
        tweets = soup.select('article[data-testid="tweet"]')
        if not tweets:
            logger.warning(
                "No article elements with data-testid='tweet' found. Trying alternative selectors."
            )
            # Fallback: Look for divs that seem to contain tweet structure (less reliable)
            # This needs careful inspection of the HTML structure if the primary selector fails
            # Example fallback (adjust based on actual HTML):
            # tweets = soup.select('div[data-focusvisible-polyfill="true"]') # Very generic, likely needs refinement
            if not tweets:  # Still nothing found
                logger.error("Could not find any tweet elements in the HTML.")
                return None

        logger.info(f"Found {len(tweets)} potential tweet elements")

        output_blocks: List[str] = []
        processed_tweet_links: Set[str] = (
            set()
        )  # Avoid processing duplicate tweets if HTML is weird

        for i, tweet in enumerate(tweets):
            if debug:
                logger.debug(f"Processing tweet element {i + 1}/{len(tweets)}")

            # Try to get a unique identifier for the tweet (e.g., its permalink)
            # Links containing '/status/' are usually permalinks
            permalink_tag = tweet.select_one('a[href*="/status/"]')
            permalink = ""
            if permalink_tag and permalink_tag.get("href"):
                href_attr = permalink_tag.get("href")
                if isinstance(href_attr, str):
                    permalink = href_attr
                    if permalink in processed_tweet_links:
                        if debug:
                            logger.debug(f"Skipping duplicate tweet: {permalink}")
                        continue
                    processed_tweet_links.add(permalink)

            # Extract tweet metadata
            user_info = extract_user_info(tweet, debug=debug)
            if debug:
                logger.debug(f"Extracted user info: {user_info}")

            # Extract tweet content
            content = extract_tweet_content(tweet, debug=debug)
            if debug and not content:
                logger.debug(f"No content extracted for tweet {i + 1}")

            # Extract media
            media_strings = extract_media(tweet, debug=debug)
            if debug and media_strings:
                logger.debug(f"Found {len(media_strings)} media items")

            # Extract metrics
            metrics = extract_metrics(tweet, debug=debug)
            if debug:
                logger.debug(f"Engagement metrics: {metrics}")

            # Skip tweets that seem like pure noise (e.g., no user info and no content)
            if (
                not user_info.get("name")
                and not user_info.get("handle")
                and not content
                and not media_strings
            ):
                if debug:
                    logger.debug(f"Skipping potentially empty/noise tweet element {i + 1}")
                continue

            tweet_block = format_tweet_markdown(user_info, content, media_strings, metrics)
            output_blocks.append(tweet_block)

        # Join all tweet blocks with a clear separator
        markdown = "\n\n".join(output_blocks)

        if not markdown:
            logger.warning("BeautifulSoup extraction resulted in empty markdown for the thread.")
            return None

        logger.info(f"Successfully parsed {len(output_blocks)} tweets using BeautifulSoup.")
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error converting Twitter thread HTML with BeautifulSoup",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error converting HTML with BeautifulSoup: {e}"
