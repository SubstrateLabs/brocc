import pytest

from brocc_li.parsers.twitter_home import twitter_feed_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_x-home.html"


# Added debug parameter
def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    # Convert using BeautifulSoup-based parser
    markdown = twitter_feed_html_to_md(html)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START TWITTER HOME MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END TWITTER HOME MARKDOWN OUTPUT ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error converting" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"

    # --- Assertions for Tweet Content & Format ---
    # Check for specific usernames and handles
    assert "@bytheophana" in markdown, "Missing @bytheophana handle"
    assert "Danielle Fong" in markdown, "Missing Danielle Fong username"
    assert "@DanielleFong" in markdown, "Missing @DanielleFong handle"
    assert "Jai Malik" in markdown, "Missing Jai Malik username"
    assert "@Jai__Malik" in markdown, "Missing @Jai__Malik handle"

    # Check for tweet content snippets
    assert "large announcement dropping tomorrow" in markdown, "Missing tiff's tweet content"
    assert "ran a hot plasma experiment" in markdown, "Missing Danielle's tweet content"
    assert "Advanced Manufacturing Company of America" in markdown, "Missing Jai's tweet content"

    # Check for media attachments
    assert "![Video Thumbnail](" in markdown or "![Embedded video](" in markdown, (
        "Missing video attachment"
    )
    assert "![" in markdown, "Missing image attachment"

    # Check for engagement metrics format
    assert "💬" in markdown, "Missing replies emoji in engagement metrics"
    assert "⟲" in markdown, "Missing retweets emoji in engagement metrics"
    assert "❤️" in markdown, "Missing likes emoji in engagement metrics"

    # Check header formatting
    assert "### " in markdown, "Missing H3 headers for tweets"

    logger.info(
        f"✅ Twitter feed conversion test passed for {FIXTURE_NAME}. "
        f"Markdown length: {len(markdown)}. {'Output printed above.' if debug else ''}"
    )
