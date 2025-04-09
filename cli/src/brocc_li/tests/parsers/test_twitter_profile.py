import pytest

from brocc_li.parsers.twitter_profile import twitter_profile_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = True
FIXTURE_NAME = "_x-profile.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    # Convert using BeautifulSoup-based parser
    markdown = twitter_profile_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START TWITTER PROFILE MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END TWITTER PROFILE MARKDOWN OUTPUT ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error converting" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"

    # Check for expected profile elements
    assert "#" in markdown, "Missing profile name header"
    assert "@" in markdown, "Missing profile handle"

    logger.info(
        f"✅ Twitter profile conversion test passed for {FIXTURE_NAME}. "
        f"Markdown length: {len(markdown)}. {'Output printed above.' if debug else ''}"
    )
