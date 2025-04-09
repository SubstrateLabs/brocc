"""Test suite for the Twitter likes parser."""

import pytest

from brocc_li.parsers.twitter_likes import twitter_likes_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_x-likes.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    markdown = twitter_likes_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START TWITTER LIKES MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END TWITTER LIKES MARKDOWN OUTPUT ---\n")

    # Basic assertion for now
    assert markdown is not None
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"
    assert "Error converting" not in markdown, f"Conversion failed: {markdown}"
    assert "###" in markdown, "Missing H3 headers for tweets"
    assert "@drishanarora" in markdown, "Missing expected handle @drishanarora"
    assert "@_xjdr" in markdown, "Missing expected handle @_xjdr"

    # Add standardized log message
    logger.info(
        f"✅ Twitter likes conversion test passed for {FIXTURE_NAME}. "
        f"Markdown length: {len(markdown)}. {'Output printed above.' if debug else ''}"
    )
