from typing import List, Optional

from bs4 import BeautifulSoup

from brocc_li.utils.logger import logger

from .bsky_utils import (
    extract_media,
    extract_metrics,
    extract_post_content_and_links,
    extract_user_info_from_post,
    format_post_markdown,
)


def bsky_feed_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    if debug:
        logger.debug("--- Input HTML Snippet (first 500 chars) ---")
        # Log raw snippet, skipping replace for now due to type issues
        logger.debug(html[:500])
        logger.debug("---------------------------------------------")
    try:
        logger.debug("Parsing HTML with BeautifulSoup...")
        soup = BeautifulSoup(html, "html.parser")
        if debug:
            logger.debug("--- BeautifulSoup Parsed Snippet (first 500 chars) ---")
            # Log raw prettified snippet, remove replace to fix linter
            logger.debug(soup.prettify()[:500])
            logger.debug("----------------------------------------------------")

        output_blocks: List[str] = []

        # 1. Find all posts
        post_selector = 'div[data-testid*="feedItem-by-"]'
        if debug:
            logger.debug(f"Attempting to find posts with selector: '{post_selector}'")
        posts = soup.select(post_selector)
        logger.info(
            f"Found {len(posts)} potential posts using '{post_selector}' selector"
        )  # Log selector used

        if not posts and debug:
            logger.warning(
                "Selector did not find any post elements. Double-check the selector against the actual HTML structure."
            )

        processed_post_urls = set()  # Keep track of posts already processed to avoid duplicates

        for i, post_el in enumerate(posts):
            if debug:
                logger.debug(f"--- Processing Post Element {i + 1}/{len(posts)} ---")

            # Extract post data using utils
            user_info = extract_user_info_from_post(post_el, debug=debug)
            content_info = extract_post_content_and_links(post_el, debug=debug)

            # Check for duplicates based on post URL
            post_url = content_info.get("post_url")
            if post_url and post_url in processed_post_urls:
                if debug:
                    logger.debug(f"Skipping duplicate post (already processed URL): {post_url}")
                continue  # Skip this iteration
            if post_url:
                processed_post_urls.add(post_url)
            elif debug:
                # If no URL, log a warning but process anyway - might be a post snippet without a permalink
                logger.warning(
                    "Processing post element without a unique post URL. Duplicates might occur if structure is nested."
                )

            # Extract media (still placeholder)
            media_strings = extract_media(post_el, debug=debug)
            # Extract metrics (still placeholder)
            metrics = extract_metrics(post_el, debug=debug)

            # Format the full post block using the util
            # Pass post_el to format function? No, pass extracted dicts.
            post_block = format_post_markdown(
                user_info, content_info, media_strings, metrics, debug=debug
            )

            output_blocks.append(post_block)

        # Join all blocks with double newlines
        markdown = "\n\n".join(output_blocks)

        if not markdown:
            logger.warning(
                f"BeautifulSoup extraction resulted in empty markdown. Found {len(posts)} post elements but placeholder logic might be incomplete or structure unexpected."
            )
            return ""  # Return empty string if no posts processed

        logger.info(
            f"Bluesky BeautifulSoup conversion finished. Processed {len(posts)} post elements."
        )
        return markdown.strip()
    except Exception as e:
        logger.error(
            "Error converting Bluesky HTML with BeautifulSoup",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error converting Bluesky HTML with BeautifulSoup: {e}"
