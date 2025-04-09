from brocc_li.parsers.instagram_utils import (
    common_instagram_parser,
)


def instagram_explore_html_to_md(html: str, debug: bool = False) -> str:
    return common_instagram_parser(
        html=html,
        page_title="Instagram Explore",
        section_title="Posts",
        debug=debug,
        empty_warning_msg="No posts extracted from elements.",
        empty_placeholder_msg="<!-- No posts extracted -->",
    )
