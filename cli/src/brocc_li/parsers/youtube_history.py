from typing import Optional

from bs4 import BeautifulSoup, Tag

from brocc_li.parsers.soup_utils import extract_date_text
from brocc_li.parsers.youtube_utils import extract_channel_info, extract_video_info
from brocc_li.utils.logger import logger


def youtube_history_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        logger.info("Starting YouTube History HTML parsing with BeautifulSoup...")
        soup = BeautifulSoup(html, "html.parser")

        # --- Find Video Entry Containers --- #
        # Selector based on live YouTube history page structure (similar to homepage)
        entry_selector = "ytd-video-renderer"  # Primary guess for history items
        entry_containers = soup.select(entry_selector)
        logger.info(
            f"BeautifulSoup found {len(entry_containers)} potential history entry containers (using '{entry_selector}')."
        )

        if not entry_containers:
            logger.warning(
                f"BeautifulSoup found no history entry containers with selector '{entry_selector}'."
            )
            # Log snippet of HTML for debugging help
            if debug:
                html_snippet = str(soup.find("body"))[:1000]  # Log first 1k chars of body
                logger.debug(f"HTML Body Snippet:\n{html_snippet}...")
            return f"<!-- BeautifulSoup: No history entry containers found with selector '{entry_selector}' -->"

        markdown_blocks = []

        # --- Process Each Entry Container --- #
        for i, container in enumerate(entry_containers):
            if debug:
                container_html_snippet = str(container)[:300]  # Shorten debug log
                logger.debug(f"--- Processing Container {i + 1}/{len(entry_containers)} ---")
                logger.debug(f"Container HTML (first 300): {container_html_snippet}...")

            # Extract video title and URL using utility function
            video_info = extract_video_info(container, debug)
            if not video_info:
                if debug:
                    logger.debug(f"  Skipping container {i + 1} - could not extract video info.")
                continue

            title, video_url = video_info

            # Extract channel name and URL using utility function
            channel_info = extract_channel_info(container, debug)
            channel_name = channel_info[0] if channel_info else None
            channel_url = channel_info[1] if channel_info else None

            # --- Extract Description --- #
            description = None
            description_tag = container.select_one("#description-text")
            if isinstance(description_tag, Tag):
                description = description_tag.text.strip()
                if debug:
                    logger.debug(f"  Found Description: {description[:100]}...")
            elif debug:
                logger.debug("  Selector '#description-text' did not find a Tag.")

            # Check for date info in description or elsewhere
            date_info = None
            if description:
                date_info = extract_date_text(description)
                if date_info and debug:
                    logger.debug(f"  Extracted date from description: {date_info}")

            # Check for watch time element (specific to history)
            watch_time_el = container.select_one("#metadata-line")
            if watch_time_el:
                watch_time_text = watch_time_el.text.strip()
                if watch_time_text and not date_info:  # Only try if we don't already have a date
                    date_info = extract_date_text(watch_time_text)
                    if date_info and debug:
                        logger.debug(f"  Extracted date from watch time: {date_info}")

            # --- Assemble Markdown Block --- #
            block_parts = []
            block_parts.append(f"### [{title}]({video_url})")

            if date_info:
                block_parts.append(f"Watched: {date_info}")

            if channel_name and channel_url:
                block_parts.append(f"Channel: [{channel_name}]({channel_url})")
            elif channel_name:
                block_parts.append(f"Channel: {channel_name}")

            # Add description if found
            if description:
                block_parts.append(f"\n{description}")  # Add newline before description

            markdown_blocks.append("\n".join(block_parts))
            if debug:
                logger.debug("  Successfully assembled markdown block.")

        logger.info(f"Processed {len(markdown_blocks)} history entry blocks into markdown.")

        if not markdown_blocks:
            logger.warning("No history entry blocks could be successfully processed into markdown.")
            return "<!-- BeautifulSoup: No processable history entry blocks found -->"

        # Join all blocks with double newlines
        markdown = "\n\n".join(markdown_blocks)

        if debug:
            logger.debug(f"Final markdown length: {len(markdown)} characters")

        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error processing YouTube History HTML with BeautifulSoup",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error processing YouTube History HTML with BeautifulSoup: {e}"
