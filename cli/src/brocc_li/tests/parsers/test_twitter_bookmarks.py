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

    # Check for tweet structure
    assert "### " in markdown, "Missing H3 headers for tweets"
    assert "@" in markdown, "Missing user handles"
    assert "![" in markdown or "http" in markdown, "Missing media or links"

    # Check for engagement metrics format
    assert "💬" in markdown, "Missing replies emoji in engagement metrics"
    assert "⟲" in markdown, "Missing retweets emoji in engagement metrics"
    assert "❤️" in markdown, "Missing likes emoji in engagement metrics"

    logger.info(
        f"✅ Twitter bookmarks conversion test passed for {FIXTURE_NAME}. "
        f"Markdown length: {len(markdown)}. {'Output printed above.' if debug else ''}"
    )
