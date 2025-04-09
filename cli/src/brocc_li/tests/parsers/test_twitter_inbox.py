import pytest

from brocc_li.parsers.twitter_inbox import twitter_inbox_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_x-inbox.html"


def test_twitter_inbox(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    # Convert using BeautifulSoup-based parser
    markdown = twitter_inbox_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START TWITTER INBOX MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END TWITTER INBOX MARKDOWN OUTPUT ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error converting" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"

    # Check for expected elements - these might need adjustment after seeing actual output
    assert "#" in markdown, "Missing header"

    # Count number of followers (each starts with ###)
    follower_count = markdown.count("### ")
    assert follower_count > 0, f"Expected at least one follower entry, found {follower_count}"

    logger.info(
        f"✅ Twitter inbox conversion test passed for {FIXTURE_NAME}. "
        f"Markdown length: {len(markdown)}. {'Output printed above.' if debug else ''}"
    )
