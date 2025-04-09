from typing import Optional

from bs4 import BeautifulSoup, Tag

from brocc_li.parsers.soup_utils import extract_date_text
from brocc_li.parsers.youtube_utils import extract_channel_info, extract_video_info
from brocc_li.utils.logger import logger


def youtube_home_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        logger.info("Starting YouTube Home HTML parsing with BeautifulSoup...")
        soup = BeautifulSoup(html, "html.parser")

        # --- Find Video Containers --- #
        # Guessing common selectors for video items on the homepage grid
        # We might need to adjust these based on actual fixture HTML
        video_containers = soup.select("ytd-rich-item-renderer, ytd-video-renderer")
        logger.info(f"BeautifulSoup found {len(video_containers)} potential video containers.")

        if not video_containers:
            logger.warning("BeautifulSoup found no video containers with the current selectors.")
            return "<!-- BeautifulSoup: No video containers found -->"

        markdown_blocks = []

        # --- Process Each Video Container --- #
        for i, container in enumerate(video_containers):
            if debug:
                logger.debug(f"--- Processing Container {i + 1}/{len(video_containers)} ---")

            # Extract video title and URL using utility function
            video_info = extract_video_info(container, debug)
            if not video_info:
                if debug:
                    logger.debug(f"  Skipping container {i + 1} - could not extract video info.")
                continue

            title, video_url = video_info

            # Extract thumbnail info (similar to original - no utility function yet)
            thumbnail_tag: Optional[Tag] = container.select_one("#thumbnail img")
            thumbnail_url = thumbnail_tag.get("src") if thumbnail_tag else None
            thumbnail_alt = (
                thumbnail_tag.get("alt", "Video thumbnail") if thumbnail_tag else "Video thumbnail"
            )
            if debug and thumbnail_tag:
                logger.debug(f"  Thumbnail URL: {thumbnail_url}")
            elif debug:
                logger.debug("  Thumbnail tag not found.")

            # Extract channel name and URL using utility function
            channel_info = extract_channel_info(container, debug)
            channel_name = channel_info[0] if channel_info else None
            channel_url = channel_info[1] if channel_info else None

            # Metadata line often contains multiple spans for views and time
            metadata_tags = container.select("#metadata-line span.inline-metadata-item")
            metadata_text = " | ".join(tag.text.strip() for tag in metadata_tags)
            if debug:
                logger.debug(f"  Metadata: {metadata_text}")

            # Try to extract a date from metadata if available
            date_info = None
            if metadata_text:
                date_info = extract_date_text(metadata_text)
                if date_info and debug:
                    logger.debug(f"  Extracted date from metadata: {date_info}")

            # --- Assemble Markdown Block --- #
            block_parts = []
            block_parts.append(f"### [{title}]({video_url})")
            if thumbnail_url:
                block_parts.append(f"![{thumbnail_alt}]({thumbnail_url})")
            if channel_name and channel_url:
                block_parts.append(f"Channel: [{channel_name}]({channel_url})")
            elif channel_name:
                block_parts.append(f"Channel: {channel_name}")  # Fallback if URL missing

            # Include date if found, otherwise use the raw metadata
            if date_info:
                block_parts.append(f"Date: {date_info}")
                if metadata_text:
                    block_parts.append(f"Info: {metadata_text}")
            elif metadata_text:
                block_parts.append(f"Info: {metadata_text}")

            markdown_blocks.append("\n".join(block_parts))

        logger.info(f"Processed {len(markdown_blocks)} video blocks into markdown.")

        if not markdown_blocks:
            logger.warning("No video blocks could be successfully processed into markdown.")
            return "<!-- BeautifulSoup: No processable video blocks found -->"

        # Join all blocks with double newlines
        markdown = "\n\n".join(markdown_blocks)

        if debug:
            logger.debug(f"Final markdown length: {len(markdown)} characters")

        return markdown.strip()

    except Exception as e:
        logger.error(
            "Error processing YouTube Home HTML with BeautifulSoup",
            exc_info=True,
        )
        # Return error message in the output for debugging
        return f"Error processing YouTube Home HTML with BeautifulSoup: {e}"
