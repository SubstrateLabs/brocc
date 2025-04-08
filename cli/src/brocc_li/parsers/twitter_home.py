from typing import List, Optional

from bs4 import BeautifulSoup

from brocc_li.utils.logger import logger

from .twitter_utils import (
    extract_media,
    extract_metrics,
    extract_tweet_content,
    extract_user_info,
    format_tweet_markdown,
)


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


def twitter_feed_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        soup = BeautifulSoup(html, "html.parser")

        # Extract structure - we'll collect sections and tweets
        output_blocks: List[str] = []

        # 1. First look for section headers (like "Trending now")
        section_headers = soup.select('h2, [role="heading"][aria-level="2"]')
        if debug:
            logger.debug(f"Found {len(section_headers)} section headers")

        for header in section_headers:
            header_text = header.get_text(strip=True)
            if header_text and _is_section_relevant(header_text):
                if debug:
                    logger.debug(f"Adding section header: {header_text}")
                output_blocks.append(f"## {header_text}")

        # 2. Find all tweets using the container selector
        tweets = soup.select('article[data-testid="tweet"]')
        logger.info(f"Found {len(tweets)} tweets in the HTML")

        for i, tweet in enumerate(tweets):
            if debug:
                logger.debug(f"Processing tweet {i + 1}/{len(tweets)}")

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
        return markdown.strip()  # Ensure no leading/trailing whitespace on the final output
    except Exception as e:
        logger.error(
            "Error converting HTML with BeautifulSoup",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error converting HTML with BeautifulSoup: {e}"
