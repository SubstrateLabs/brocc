import pytest

from brocc_li.parsers.youtube_home import youtube_home_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_youtube-home.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    # Convert using unstructured-based parser, pass debug parameter
    markdown = youtube_home_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START YOUTUBE HOME MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END YOUTUBE HOME MARKDOWN OUTPUT ---\n")

    # Basic assertions (keep minimal checks)
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"
    assert "<!-- No elements" not in markdown, "Parser reported no elements found"
    assert "<!-- BeautifulSoup:" not in markdown, "BeautifulSoup parser reported errors"

    # --- Assertions for Content & Format --- #
    # Check for a reasonable number of video blocks
    assert markdown.count("### [") > 10, (
        f"Expected >10 video blocks, found {markdown.count('### [')}"
    )

    # Check for specific content (titles/channels from debug logs)
    assert "Ian Bremmer's Quick Take" in markdown, "Missing expected video title (Bremmer)"
    assert "Dwarkesh Patel" in markdown, "Missing expected channel name (Dwarkesh)"
    assert "Bloomberg Television" in markdown, "Missing expected channel name (Bloomberg)"
    assert "The Rehearsal Season 2" in markdown, "Missing expected video title (Rehearsal)"

    # Check for basic formatting elements
    assert "Channel: [" in markdown, "Missing expected channel link formatting"
    assert "Info: " in markdown, "Missing expected metadata info line"
    assert "![Video thumbnail]" in markdown or "![" in markdown, (
        "Missing expected image/thumbnail formatting"
    )

    logger.info(
        f"✅ YouTube home conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else ''}"
    )
