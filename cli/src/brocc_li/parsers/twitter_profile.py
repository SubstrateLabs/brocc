from typing import Optional

from bs4 import BeautifulSoup

from brocc_li.utils.logger import logger


def twitter_profile_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    try:
        soup = BeautifulSoup(html, "html.parser")
        if debug:
            logger.debug("Starting Twitter profile HTML parsing")

        # Extract basic profile info
        name = soup.select_one('div[data-testid="UserName"]')
        if name:
            name = name.get_text(strip=True)
            if debug:
                logger.debug(f"Found profile name: {name}")

        handle = soup.select_one('div[data-testid="UserScreenName"]')
        if handle:
            handle = handle.get_text(strip=True)
            if debug:
                logger.debug(f"Found handle: {handle}")

        bio = soup.select_one('div[data-testid="UserDescription"]')
        if bio:
            bio = bio.get_text(strip=True)
            if debug:
                logger.debug(f"Found bio text: {bio}")

        # Format the markdown
        output_blocks = []
        if name and handle:
            output_blocks.append(f"# {name} ({handle})")
        if bio:
            output_blocks.append(bio)

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
