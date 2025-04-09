from typing import Optional

from brocc_li.parsers.instagram_utils import (
    common_instagram_parser,
)


def instagram_explore_search_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """Convert Instagram explore/search HTML to Markdown."""
    return common_instagram_parser(
        html=html,
        page_title="Instagram Search Results",
        section_title="Posts",
        debug=debug,
        empty_warning_msg="No search result posts extracted from elements.",
        empty_placeholder_msg="<!-- No search result posts extracted -->",
    )
