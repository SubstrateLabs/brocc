import pytest

from brocc_li.parsers.twitter_bookmarks import twitter_bookmarks_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_x-bookmarks.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    # Convert using BeautifulSoup-based parser
    markdown = twitter_bookmarks_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START TWITTER BOOKMARKS MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END TWITTER BOOKMARKS MARKDOWN OUTPUT ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error converting" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"

    # Check for bookmarks header
    assert "## Your Bookmarks" in markdown, "Missing bookmarks header"

    # Verify specific users and content
    assert "@_xjdr" in markdown, "Missing xjdr tweet"
    assert "@yishan" in markdown, "Missing Yishan tweet"
    assert "@eli_lifland" in markdown, "Missing Eli Lifland tweet"
    assert "@BulwarkOnline" in markdown, "Missing Bulwark tweet"
    assert "@0xIlyy" in markdown, "Missing ily tweet"

    # Check for specific content snippets
    assert "Scout is best at summarization" in markdown, "Missing xjdr tweet content"
    assert "tariff policy" in markdown, "Missing Yishan tweet content"
    assert "AI 2027" in markdown, "Missing Eli tweet content"
    assert "Heard and McDonald Islands" in markdown, "Missing Bulwark tweet content"
    assert "Tierlist of autism levels" in markdown, "Missing ily tweet content"

    # Check for media handling
    assert "pbs.twimg.com" in markdown, "Missing media URLs"
    assert "![Image]" in markdown or "![Timeline: Bookmarks]" in markdown, "Missing image markdown"

    # Check for timestamp formats
    assert "2025-04-07T16:15:16.000Z" in markdown, "Missing ISO timestamp"
    assert "Apr 7" in markdown, "Missing human readable timestamp"

    # Check for engagement metrics format and specific values
    assert "💬 26 ⟲ 54 ❤️ 461 👁️ 38614" in markdown, "Missing or incorrect xjdr metrics"
    assert "💬 249 ⟲ 352 ❤️ 2274 👁️ 861097" in markdown, "Missing or incorrect Yishan metrics"
    assert "💬 796 ⟲ 1488 ❤️ 11766 👁️ 1872345" in markdown, "Missing or incorrect Bulwark metrics"

    # Check for proper markdown link formatting
    assert "[xjdr](https://x.com/_xjdr)" in markdown, "Missing or incorrect user link format"
    assert "[Yishan](https://x.com/yishan)" in markdown, "Missing or incorrect user link format"

    logger.info(
        f"✅ Twitter bookmarks conversion test passed for {FIXTURE_NAME}. "
        f"Markdown length: {len(markdown)}. {'Output printed above.' if debug else ''}"
    )
