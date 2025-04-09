import pytest

from brocc_li.parsers.linkedin_feed import linkedin_feed_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_linkedin-feed.html"
FIXTURE_NAME_2 = "_linkedin-feed-2.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    # Convert using unstructured-based parser, pass debug parameter
    markdown = linkedin_feed_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START LINKEDIN FEED MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END LINKEDIN FEED MARKDOWN OUTPUT ---\n")

    # Basic assertions (keep minimal checks)
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error partitioning" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"
    assert "<!-- No posts found -->" not in markdown, (
        "Parser reported no posts found, check selectors."
    )
    assert "<!-- Error processing post" not in markdown, "Parser reported errors processing posts."

    # --- Assertions for Post Content & Format --- #
    # Check for specific user names from the fixture
    assert "Thorsten" in markdown, "Missing expected user name: Thorsten"
    assert "Nils Schneider" in markdown, "Missing expected user name: Nils Schneider (Post 2)"
    assert "Andrew Yeung" in markdown, "Missing expected user name: Andrew Yeung (Commenter)"
    assert "Hamza Alsamraee" in markdown, "Missing expected user name: Hamza Alsamraee (Post 3)"

    # Check for post content snippets
    assert "WhatsApp MCP server" in markdown, "Missing content from Post 1"
    assert "Instantly.ai Catch-All Verification" in markdown, "Missing content from Post 2"
    assert "Excited to introduce WillBot" in markdown, "Missing content from Post 3"
    assert "leggo" in markdown, "Missing comment text from Andrew Yeung"

    # Check that some common noise is *not* present
    assert "Stream Type LIVE" not in markdown, "Media player controls detected in output"
    assert "Media player modal window" not in markdown, "Media player modal text detected"

    logger.info(
        f"✅ LinkedIn feed conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else ''}"
    )


def test_parse_feed2():
    try:
        html = get_fixture(FIXTURE_NAME_2)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME_2} not found")

    # Convert using unstructured-based parser with debug controlled by global DEBUG flag
    markdown = linkedin_feed_html_to_md(html, debug=DEBUG)

    # Print the output for inspection only when debug is enabled
    if DEBUG:
        print("\n--- START LINKEDIN FEED 2 MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END LINKEDIN FEED 2 MARKDOWN OUTPUT ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"

    # Check for specific noise patterns that should be filtered out
    assert "Current time" not in markdown, "Video player 'Current time' element not filtered out"
    assert "Duration" not in markdown, "Video player 'Duration' element not filtered out"
    assert "Activate to view larger image" not in markdown, "Image UI element not filtered out"

    # Expected content check
    assert "Josh Wymer" in markdown, "Missing expected user name: Josh Wymer"
    assert "Central (YC)" in markdown, "Missing expected content from Josh's post"
    # This company block is empty and gets filtered out
    # assert "ChatAE" in markdown, "Missing expected company: ChatAE"
