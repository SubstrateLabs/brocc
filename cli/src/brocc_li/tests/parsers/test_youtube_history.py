import pytest

from brocc_li.parsers.youtube_history import youtube_history_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_youtube-history.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    # Convert using unstructured-based parser, pass debug parameter
    markdown = youtube_history_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START YOUTUBE HISTORY MARKDOWN OUTPUT (Truncated) ---")
        if markdown is not None:
            TRUNCATED_LINES = 30
            lines = markdown.splitlines()
            print("\n".join(lines[:TRUNCATED_LINES]))
            if len(lines) > TRUNCATED_LINES:
                print("[... Output truncated ...]")
        else:
            print("!!! MARKDOWN WAS NONE !!!")
        print("--- END YOUTUBE HISTORY MARKDOWN OUTPUT ---\n")

    # Basic assertions (keep minimal checks)
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"
    assert "<!-- No elements found -->" not in markdown, "Parser reported no elements found."
    assert "<!-- BeautifulSoup:" not in markdown, "Parser reported BeautifulSoup errors."

    # Content assertions
    assert "Clawtype v2.1" in markdown, "Missing expected video title"
    assert "Kurzgesagt" in markdown, "Missing expected channel name"
    assert "### [" in markdown, "Markdown header format missing or incorrect"
    assert "Channel: [" in markdown, "Channel format missing or incorrect"
    assert "https://www.youtube.com" in markdown, "Absolute video/channel URLs missing"

    # Noise assertions
    assert "Watched " not in markdown, "'Watched ' prefix should be removed"
    assert "Time:" not in markdown, "Timestamp labels should not be present"

    logger.info(
        f"✅ YouTube history conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else ''}"
    )
