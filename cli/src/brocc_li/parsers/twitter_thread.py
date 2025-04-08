from typing import List, Optional, Set

from bs4 import BeautifulSoup, Tag

from brocc_li.utils.logger import logger

from .twitter_utils import (
    extract_media,
    extract_metrics,
    extract_tweet_content,
    format_metrics,
    format_user_link,
)

DEBUG = False


def twitter_thread_html_to_md(html: str) -> Optional[str]:
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
            if DEBUG:
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
                        if DEBUG:
                            logger.debug(f"Skipping duplicate tweet: {permalink}")
                        continue
                    processed_tweet_links.add(permalink)

            # Extract tweet metadata
            name = ""
            handle = ""
            handle_url = ""
            timestamp = ""
            timestamp_full = ""  # For potential hover text/exact time

            # Get name and handle - Look within the User-Name section
            user_name_section = tweet.select_one('[data-testid="User-Name"]')
            if DEBUG and user_name_section:
                logger.debug("--- Debugging User Info Extraction ---")
            if DEBUG and user_name_section:
                logger.debug(f"User-Name Section HTML: {user_name_section.prettify()[:500]}")
            if user_name_section:
                # Extract the display name (often bolded span within links)
                # More robust name extraction:
                name_container = user_name_section.select_one(
                    'a[role="link"] > div[dir="ltr"], div[dir="ltr"] > span'
                )
                if name_container:
                    name_parts = []
                    # Iterate through elements, trying to get text smartly
                    for elem in name_container.descendants:
                        if isinstance(elem, str):
                            text = elem.strip()
                            # Filter out noise like 'Verified account' or empty strings
                            if (
                                text
                                and "Verified account" not in text
                                and "follows you" not in text
                            ):
                                name_parts.append(text)
                        elif isinstance(elem, Tag) and elem.name == "span":
                            # If we encounter a span, grab its direct text if it seems relevant
                            span_text = elem.get_text(strip=True)
                            if (
                                span_text
                                and "Verified account" not in span_text
                                and "follows you" not in span_text
                            ):
                                # Avoid adding text that's already part of a larger string we captured
                                already_added = False
                                for part in name_parts:
                                    if span_text in part:
                                        already_added = True
                                        break
                                if not already_added:
                                    name_parts.append(span_text)

                    # Join and clean the collected parts
                    if name_parts:
                        potential_name = " ".join(name_parts)
                        # Extra cleaning: remove duplicates and clean whitespace
                        unique_parts = []
                        seen = set()
                        for part in potential_name.split():
                            if part not in seen:
                                unique_parts.append(part)
                                seen.add(part)
                        name = " ".join(unique_parts)  # Final cleaned name
                # Fallback if the refined logic fails
                if not name:
                    fallback_name_element = user_name_section.select_one(
                        'a span[data-testid*="UserName"], div span[data-testid*="UserName"]'
                    )  # More specific fallback selector
                    if fallback_name_element:
                        potential_name = fallback_name_element.get_text(separator=" ", strip=True)
                        if "Verified account" not in potential_name:
                            name = " ".join(potential_name.split())  # Clean whitespace
                if DEBUG:
                    logger.debug(f"Extracted Name: '{name}'")

                # Extract the handle (starts with @, usually a link)
                # First, find the main link to get the URL
                handle_link = user_name_section.find(
                    "a",
                    href=lambda h: isinstance(h, str) and h.startswith("/") and "/status/" not in h,
                    recursive=False,
                )  # Look for direct child link
                if not handle_link:
                    handle_link = user_name_section.find(
                        "a",
                        href=lambda h: isinstance(h, str)
                        and h.startswith("/")
                        and "/status/" not in h,
                    )  # Broader search if no direct child

                if isinstance(handle_link, Tag):
                    href_val = handle_link.get("href")
                    if isinstance(href_val, str):
                        handle_url = href_val
                        if DEBUG:
                            logger.debug(
                                f"Found potential handle URL: '{handle_url}' from link: {handle_link.prettify()[:100]}"
                            )
                elif DEBUG:
                    logger.debug("Could not find main handle link tag <a> to extract URL.")

                # Now, search for the handle text (@...) within the whole section
                if DEBUG:
                    logger.debug("Searching for handle text starting with @...")
                handle_text_element = user_name_section.find(
                    lambda tag: isinstance(tag, Tag)
                    and tag.name == "span"
                    and tag.get_text(strip=True).startswith("@")
                )

                if isinstance(handle_text_element, Tag):  # Check handle_link is Tag
                    # Check if handle_text_element is a Tag before getting text
                    # if isinstance(handle_text_element, Tag):
                    handle_text_str = str(handle_text_element.get_text(strip=True)).strip()
                    if DEBUG:
                        logger.debug(f"Found handle text element: '{handle_text_str}'")
                    # Convert NavigableString to str before stripping
                    handle = handle_text_str  # Already stripped
                    if handle_url:  # We should have found the URL earlier
                        if DEBUG:
                            logger.debug(f"Extracted Handle: '{handle}' (URL: '{handle_url}')")
                    else:
                        if DEBUG:
                            logger.warning(
                                f"Extracted Handle: '{handle}' but URL was not found earlier!"
                            )
                elif DEBUG:
                    logger.debug("Could not find span element with text starting with @.")

                # Get the timestamp (often a link within the User-Name section)
                time_element = user_name_section.select_one("time")
                if time_element:
                    timestamp = time_element.get_text(strip=True)
                    timestamp_full = time_element.get(
                        "datetime", ""
                    )  # Get ISO timestamp if available

                # Fallback: Sometimes timestamp is an 'a' tag with text like '5h'
                if not timestamp:
                    time_link = user_name_section.find(
                        "a", href=lambda h: isinstance(h, str) and "/status/" in h
                    )
                    if isinstance(time_link, Tag):  # Check time_link is Tag
                        # Text might be directly in the link or in a span inside
                        time_text = time_link.get_text(strip=True)
                        # Check if it looks like a relative time ('5h', 'Mar 20', etc.)
                        if time_text and not time_text.startswith("@") and len(time_text) < 15:
                            timestamp = time_text
                            # Try to get datetime attribute if present
                            time_tag = time_link.find("time")
                            if time_tag:
                                # Ensure time_tag is a Tag before calling .get()
                                if isinstance(time_tag, Tag):
                                    timestamp_full = time_tag.get("datetime", "")

            if not name or not handle:
                if DEBUG:
                    logger.warning(
                        f"Could not extract full user info for tweet {i + 1}. Name: '{name}', Handle: '{handle}'. Trying fallback..."
                    )
                # Try a simpler fallback for user info if User-Name fails
                user_divs = tweet.select(
                    'div > div > div > a[role="link"]'
                )  # Common structure for user link
                if DEBUG:
                    logger.debug(f"Fallback: Found {len(user_divs)} potential user divs.")
                for link_idx, link in enumerate(user_divs):
                    # Check if link is a Tag before accessing attributes
                    if not isinstance(link, Tag):
                        continue
                    if DEBUG:
                        logger.debug(f"Fallback Link {link_idx} HTML: {link.prettify()[:200]}")
                    href = link.get("href")
                    # Check href type and content
                    if (
                        isinstance(href, str)
                        and not href.startswith("/")
                        and "/i/status/" not in href
                    ):  # Filter out some common non-user links
                        # This might be the user link section
                        if DEBUG:
                            logger.debug(f"  Found potential user link: href='{href}'")
                        spans = link.select("span")
                        if DEBUG:
                            logger.debug(f"  Found {len(spans)} spans inside.")
                        if len(spans) >= 2:  # Expect Name + Handle potentially
                            # Ensure text extraction results in strings
                            potential_name_text = spans[0].get_text(strip=True)
                            potential_handle_text = spans[-1].get_text(
                                strip=True
                            )  # Handle often last
                            if (
                                isinstance(potential_name_text, str)
                                and isinstance(potential_handle_text, str)
                                and potential_handle_text.startswith("@")
                            ):
                                name = potential_name_text
                                handle = potential_handle_text
                                handle_url = href  # href is already confirmed string
                                if DEBUG:
                                    logger.debug(
                                        f"Fallback user info found: {name} ({handle}) URL: {handle_url}"
                                    )
                                break  # Found it
                        elif DEBUG and len(spans) < 2:
                            logger.debug("  Not enough spans for fallback Name/Handle logic.")
                    elif DEBUG:
                        logger.debug(
                            f"  Skipping link {link_idx}: href='{href}' did not meet criteria."
                        )
                if not name or not handle:
                    if DEBUG:
                        logger.debug("Fallback logic also failed to find Name/Handle.")

            # Extract tweet content
            content = extract_tweet_content(tweet)
            if DEBUG and not content:
                logger.debug(f"No content extracted for tweet {i + 1}")

            # Extract media
            media_strings = extract_media(tweet)
            if DEBUG and media_strings:
                logger.debug(f"Found {len(media_strings)} media items")

            # Extract metrics
            metrics = extract_metrics(tweet)
            if DEBUG:
                logger.debug(f"Engagement metrics: {metrics}")

            # Format the tweet header
            header = "###"  # Start with H3

            if name and handle and handle_url:
                # Ensure name, handle, handle_url are strings before calling
                if (
                    isinstance(name, str)
                    and isinstance(handle, str)
                    and isinstance(handle_url, str)
                ):
                    user_link = format_user_link(name, handle, handle_url)
                    header += f" {user_link}"
                else:
                    if DEBUG:
                        logger.warning(
                            f"Skipping user link formatting due to unexpected types. Name: {type(name)}, Handle: {type(handle)}, URL: {type(handle_url)}"
                        )
                    header += f" {name} {handle}"  # Basic fallback
            elif handle:  # If only handle is found
                if not isinstance(handle, str):  # Ensure handle is string
                    if DEBUG:
                        logger.warning(f"Handle is not a string: {type(handle)}. Skipping link.")
                    header += f" {handle}"
                else:
                    clean_handle = handle.lstrip("@")
                    # Ensure handle_url is a string and make absolute if needed
                    profile_url = handle_url
                    if isinstance(handle_url, str):
                        if handle_url.startswith("/"):
                            profile_url = f"https://x.com{handle_url}"
                        else:  # Assume it might be relative path used incorrectly, construct from handle
                            profile_url = f"https://x.com/{clean_handle}"
                    else:  # Fallback if handle_url wasn't found/set correctly
                        profile_url = f"https://x.com/{clean_handle}"
                    header += f" [{handle}]({profile_url})"
            elif name:  # If only name is found
                # Ensure name is a string
                if not isinstance(name, str):
                    if DEBUG:
                        logger.warning(f"Name is not a string: {type(name)}. Using raw value.")
                    header += f" {name}"
                else:
                    header += f" {name}"

            # Add timestamp to header
            if timestamp:
                header += f" · {timestamp}"
                if timestamp_full and isinstance(timestamp_full, str):  # Check type before using
                    header += f" ({timestamp_full})"  # Add ISO time in parenthesis if available
                elif isinstance(timestamp, str) and timestamp:  # Check timestamp itself
                    # Add only the relative time if full isn't available or valid
                    pass  # Already added above

            # Skip tweets that seem like pure noise (e.g., no user info and no content)
            if not name and not handle and not content and not media_strings:
                if DEBUG:
                    logger.debug(f"Skipping potentially empty/noise tweet element {i + 1}")
                continue

            # Format the full tweet block
            tweet_block_parts = [header]
            if content:
                tweet_block_parts.append(f"\n{content}")

            if media_strings:
                # Join media with spaces for inline, or newlines if preferred
                tweet_block_parts.append(f"\n\n{' '.join(media_strings)}")

            # Add engagement metrics if available and non-zero
            metrics_str = format_metrics(metrics)
            if metrics_str:
                tweet_block_parts.append(f"\n\n{metrics_str}")

            output_blocks.append("\n".join(tweet_block_parts))

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
