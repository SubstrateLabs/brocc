import re
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


def _format_stat(stat_text: str, debug: bool = False) -> str:
    """Format a stat text by separating numbers from labels."""
    if debug:
        logger.debug(f"Formatting stat: '{stat_text}'")

    # Extract numbers using regex
    number_match = re.search(r"^(\d+)", stat_text)
    if number_match:
        number = number_match.group(1)
        label = stat_text[len(number) :].strip()
        formatted = f"{number} {label}"
        if debug:
            logger.debug(f"Reformatted to: '{formatted}'")
        return formatted
    return stat_text


def _extract_profile_stats(soup, debug: bool = False) -> List[str]:
    """Extract follower counts and other profile statistics with clean formatting."""
    stats = []
    followed_by = None

    # Look for the stats container
    stats_container = soup.select('a[href*="followers"], a[href*="following"]')

    if debug:
        logger.debug(f"Found {len(stats_container)} primary stat elements")

    for stat in stats_container:
        stat_text = stat.get_text(strip=True)
        if debug:
            logger.debug(f"Raw stat text: '{stat_text}'")

        # Skip if empty or too long (likely garbage)
        if not stat_text or len(stat_text) > 50:
            continue

        # Format the stat with space between number and label
        formatted_stat = _format_stat(stat_text, debug)
        stats.append(formatted_stat)

    # Try to find a more precise "Followed by" container
    # Only look for elements that are specifically about followers, not the entire page
    followed_spans = soup.select('span:-soup-contains("Followed by")')

    if not followed_spans:
        # Fallback to div for older markup
        followed_spans = soup.select('div:-soup-contains("Followed by")')

    for span in followed_spans:
        text = span.get_text(strip=True)
        # Make sure it's a reasonable length and contains the expected text
        if "Followed by" in text and len(text) < 100:
            # Extract just the "Followed by..." part
            match = re.search(r"(Followed by [^.]+)", text)
            if match:
                followed_by = match.group(1)
                if debug:
                    logger.debug(f"Found clean 'Followed by' text: '{followed_by}'")
                break

    # Add the "Followed by" text if found and not garbage
    if followed_by and len(followed_by) < 100:
        stats.append(followed_by)

    return stats


def twitter_profile_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        soup = BeautifulSoup(html, "html.parser")
        if debug:
            logger.debug("Starting Twitter profile HTML parsing")
            logger.debug(f"HTML length: {len(html)} characters")

        output_blocks = []

        # Extract profile header info
        profile_header = soup.select_one(
            'div[data-testid="UserName"], div[data-testid="UserProfileHeader"]'
        )
        if profile_header and debug:
            logger.debug(f"Found profile header element: {profile_header.name}")

        # Extract name/handle from header
        name_element = soup.select_one('div[data-testid="UserName"]')
        if name_element:
            full_text = name_element.get_text(strip=True)
            if debug:
                logger.debug(f"Raw name element text: '{full_text}'")

            # Split on @ to separate name from handle
            parts = full_text.split("@")
            if len(parts) >= 2:
                name = parts[0].strip()
                handle = "@" + parts[1].split("Follows")[0].strip()  # Remove "Follows you" suffix
                if debug:
                    logger.debug(f"Found profile name: '{name}'")
                    logger.debug(f"Found handle: '{handle}'")
                output_blocks.append(f"# {name} {handle}")

        # Extract bio
        bio = soup.select_one('div[data-testid="UserDescription"]')
        if bio:
            bio_text = bio.get_text(strip=True)
            if debug:
                logger.debug(f"Found bio text: '{bio_text}'")
            output_blocks.append(bio_text)

        # Extract profile stats with improved formatting
        stats = _extract_profile_stats(soup, debug=debug)
        if stats:
            # Remove duplicates while preserving order
            unique_stats = []
            seen = set()
            for stat in stats:
                if stat not in seen:
                    unique_stats.append(stat)
                    seen.add(stat)

            stats_str = " • ".join(unique_stats)
            if debug:
                logger.debug(f"Profile stats formatted: '{stats_str}'")
            output_blocks.append(f"**{stats_str}**")

        # Extract tweets using twitter_utils helpers
        tweets = soup.select('article[data-testid="tweet"]')
        if tweets:
            if debug:
                logger.debug(f"Found {len(tweets)} tweets")

            output_blocks.append("\n## Tweets")

            # Process each tweet using the utilities
            processed_tweets = set()  # Track processed content to avoid duplicates
            for i, tweet in enumerate(tweets):
                if debug:
                    logger.debug(f"Processing tweet {i + 1}/{len(tweets)}")

                # Extract user info
                user_info = extract_user_info(tweet, debug=debug)
                if debug:
                    logger.debug(f"Extracted user info: {user_info}")

                # Extract tweet content
                content = extract_tweet_content(tweet, debug=debug)

                # Skip tweets we've already processed (check first 50 chars)
                text_start = content[:50] if content else ""
                if text_start in processed_tweets:
                    if debug:
                        logger.debug(f"Skipping duplicate tweet: {text_start}...")
                    continue

                if content:
                    processed_tweets.add(text_start)

                    # Extract media
                    media_strings = extract_media(tweet, debug=debug)
                    if debug:
                        logger.debug(f"Found {len(media_strings)} media items")

                    # Extract metrics
                    metrics = extract_metrics(tweet, debug=debug)
                    if debug:
                        logger.debug(f"Engagement metrics: {metrics}")

                    # Format the tweet
                    tweet_block = format_tweet_markdown(user_info, content, media_strings, metrics)
                    output_blocks.append(tweet_block)

        markdown = "\n\n".join(output_blocks)

        if not markdown:
            logger.warning("Profile extraction resulted in empty markdown")
            return None

        logger.info("Twitter profile conversion successful")
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error converting profile HTML with BeautifulSoup",
            exc_info=True,
        )
        return f"Error converting profile HTML with BeautifulSoup: {e}"
