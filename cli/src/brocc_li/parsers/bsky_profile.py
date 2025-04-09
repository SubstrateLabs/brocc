import re
from typing import List, Optional

from bs4 import BeautifulSoup, Tag

from brocc_li.utils.logger import logger

# Use the common Bluesky utility functions
from .bsky_utils import (
    extract_media,  # Using the placeholder/implemented util
    extract_metrics,  # Using the implemented util
    extract_post_content_and_links,
    extract_user_info_from_post,
    format_post_markdown,
)


def _format_bsky_stat(stat_text: str, debug: bool = False) -> str:
    """Format a Bluesky stat text by separating numbers from labels."""
    if debug:
        logger.debug(f"Formatting Bluesky stat: '{stat_text}'")

    # Fix regex: Use \d not \\\\d
    number_match = re.search(r"^(\d+|\d{1,3}(?:,\d{3})*|\d+\.\d+[KMB]?)", stat_text)
    if number_match:
        number = number_match.group(1)
        label = stat_text[len(number) :].strip()
        formatted = f"{number} {label}"
        if debug and formatted != stat_text:
            logger.debug(f"Reformatted to: '{formatted}'")
        return formatted
    # If no number match, return the original text
    return stat_text


def _extract_bsky_profile_stats(soup: BeautifulSoup, debug: bool = False) -> List[str]:
    """Extract follower/following counts and post count for Bluesky."""
    stats = []
    if debug:
        logger.debug("Extracting Bluesky profile stats")

    # Selectors based on provided HTML (might need adjustment for variations)
    stats_container = soup.select_one('div[data-testid="profileView"]')
    follower_following_elements = []
    if stats_container:
        # Find follower/following links specifically
        potential_links = stats_container.select('a[href*="/followers"], a[href*="/follows"]')
        if potential_links:
            follower_following_elements.extend(potential_links)
            if debug:
                logger.debug(f"Found {len(potential_links)} follower/following links via selector")
        else:
            if debug:
                logger.warning("Could not find follower/following links using selector")

    for stat_link in follower_following_elements:
        stat_text = stat_link.get_text(strip=True)
        if debug:
            logger.debug(f"Raw stat link text: '{stat_text}'")

        # Check text content to ensure it's a follower/following count
        if stat_text and (
            re.search(r"followers", stat_text, re.IGNORECASE)
            or re.search(r"following", stat_text, re.IGNORECASE)
        ):
            formatted_stat = _format_bsky_stat(stat_text, debug)
            stats.append(formatted_stat)
            if debug:
                logger.debug(f"Added stat: '{formatted_stat}'")

    # Post count selector
    post_count_div = (
        stats_container.select_one('div[dir="auto"]:-soup-contains("posts")')
        if stats_container
        else None
    )
    if post_count_div:
        post_text = post_count_div.get_text(strip=True)
        if debug:
            logger.debug(f"Raw post count text: '{post_text}'")
        if "posts" in post_text:
            formatted_stat = _format_bsky_stat(post_text, debug)
            stats.append(formatted_stat)
            if debug:
                logger.debug(f"Added stat: '{formatted_stat}'")
        else:
            if debug:
                logger.warning(
                    f"Found potential post count div, but text missing 'posts': {post_text}"
                )
    else:
        if debug:
            logger.warning("Could not find post count div")

    # Uniqueify stats
    unique_stats = []
    seen = set()
    for stat in stats:
        if stat not in seen:
            unique_stats.append(stat)
            seen.add(stat)

    if debug:
        logger.debug(f"Final unique stats: {unique_stats}")

    return unique_stats


def bsky_profile_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """Converts Bluesky profile HTML to Markdown."""
    try:
        soup = BeautifulSoup(html, "html.parser")
        if debug:
            logger.debug("--- Starting Bluesky profile HTML parsing ---")
            logger.debug(f"HTML length: {len(html)} characters")

        output_blocks = []

        # --- Profile Header --- #
        profile_container = soup.select_one('div[data-testid="profileView"]')
        if not profile_container:
            logger.error("Could not find main profile container (data-testid='profileView')")
            return "Error: Main profile container not found."
        if debug:
            logger.debug("Found main profile container (data-testid='profileView')")

        # Extract display name
        display_name_element = profile_container.select_one(
            'div[data-testid="profileHeaderDisplayName"]'
        )
        name = "Unknown Name"
        if display_name_element:
            name = display_name_element.get_text(strip=True)
            if debug:
                logger.debug(f"Found display name: '{name}'")
        else:
            if debug:
                logger.warning("Could not find display name element")

        # Extract handle
        # More specific selector for handle within the profile header context
        handle_element = profile_container.select_one(
            'div[style*="flex-direction: row"] > div[dir="auto"][style*="color: rgb(147, 165, 183)"]'
        )
        handle = "@unknownhandle"
        if handle_element:
            handle_text = handle_element.get_text(strip=True)
            # Clean up potential unicode direction markers just in case
            handle_text = handle_text.replace("\u2069", "").replace("\u2066", "").strip()
            if handle_text.startswith("@"):
                handle = handle_text
                if debug:
                    logger.debug(f"Found handle: '{handle}'")
            else:
                if debug:
                    logger.warning(
                        f"Found potential handle element, but text doesn't start with @: '{handle_text}'"
                    )
        else:
            if debug:
                logger.warning("Could not find handle element")

        output_blocks.append(f"# {name} {handle}")

        # Extract bio
        bio_element = profile_container.select_one('div[data-testid="profileHeaderDescription"]')
        if bio_element:
            # Preserve line breaks within the bio
            bio_parts = []
            for content in bio_element.contents:
                if isinstance(content, str):
                    bio_parts.append(content.strip())
                elif isinstance(content, Tag):  # Check if it's a Tag first
                    if content.name == "a":  # Handle links within bio
                        link_text = content.get_text(strip=True)
                        link_href = content.get("href", "")
                        bio_parts.append(f"[{link_text}]({link_href})")
                    elif content.name == "br":
                        bio_parts.append("\\n")  # Add newline for <br>
                    else:
                        # Append other tag text, stripping extra whitespace around it
                        tag_text = content.get_text().strip()
                        if tag_text:
                            bio_parts.append(tag_text)
                # else: # Handle NavigableString or other types if necessary, though already covered by isinstance(content, str)
                #    pass

            # Join parts, cleaning up potential multiple newlines
            bio_text = " ".join(bio_parts).replace(" \\n ", "\\n").strip()

            if debug:
                logger.debug(f"Found bio text:\\n{bio_text}")
            output_blocks.append(bio_text)
        else:
            if debug:
                logger.warning("Could not find bio element")

        # --- Profile Stats --- #
        stats = _extract_bsky_profile_stats(soup, debug=debug)
        if stats:
            stats_str = " • ".join(stats)
            if debug:
                logger.debug(f"Formatted profile stats: '{stats_str}'")
            output_blocks.append(f"**{stats_str}**")
        else:
            if debug:
                logger.warning("No profile stats extracted")

        # --- Posts Section --- #
        posts_section = soup.select_one('div[data-testid="postsFeed"]')
        if posts_section:
            # Select post elements within the identified posts section
            posts = posts_section.select('div[data-testid*="feedItem-by-"]')
            if posts:
                if debug:
                    logger.debug(f"Found {len(posts)} potential post elements in the feed")
                # Fix header addition: Use \n not \\\\n
                output_blocks.append("\n## Posts")

                processed_post_urls = set()  # Avoid duplicate posts

                for i, post_el in enumerate(posts):
                    if debug:
                        logger.debug(f"--- Processing Post {i + 1}/{len(posts)} ---")

                    # Use utility functions to extract data
                    user_info = extract_user_info_from_post(post_el, debug=debug)
                    content_info = extract_post_content_and_links(post_el, debug=debug)

                    # Prevent processing duplicates based on URL
                    post_url = content_info.get("post_url")
                    if post_url and post_url in processed_post_urls:
                        if debug:
                            logger.debug(
                                f"Skipping duplicate post (URL already processed): {post_url}"
                            )
                        continue
                    if post_url:
                        processed_post_urls.add(post_url)
                    elif debug:
                        logger.warning(
                            "Post element found without a unique URL, might be duplicate or incomplete."
                        )

                    media_strings = extract_media(
                        post_el, debug=debug
                    )  # Still potentially placeholder
                    metrics = extract_metrics(post_el, debug=debug)  # Uses implemented util

                    # Format using the utility function
                    # *For profile view, remove reposter info as it's redundant*
                    user_info_for_profile = user_info.copy()
                    user_info_for_profile["reposter"] = None

                    post_block = format_post_markdown(
                        user_info_for_profile, content_info, media_strings, metrics, debug=debug
                    )
                    output_blocks.append(post_block)

            else:
                # Check for 'No posts yet' message
                no_posts_msg = posts_section.select_one(
                    'div.css-146c3p1:-soup-contains("No posts yet")'
                )
                if no_posts_msg:
                    output_blocks.append("\n## Posts")
                    output_blocks.append("*No posts yet.*")
                    if debug:
                        logger.debug("Detected 'No posts yet' message.")
                else:
                    if debug:
                        logger.warning(
                            "Posts feed section found, but no individual post elements detected and no 'No posts yet' message."
                        )
        else:
            if debug:
                logger.warning("Could not find posts feed section (data-testid='postsFeed')")

        # --- Final Assembly --- #
        # Fix join separator: Use \n\n not \\\\n\\\\n
        markdown = "\n\n".join(filter(None, output_blocks))  # Filter out potential empty blocks

        if not markdown.strip():
            logger.warning("Bluesky profile extraction resulted in empty markdown")
            return None

        logger.info("--- Bluesky profile conversion successful (using utils) ---")
        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error converting Bluesky profile HTML with BeautifulSoup",
            exc_info=True,
        )
        return f"Error converting Bluesky profile HTML with BeautifulSoup: {e}"
