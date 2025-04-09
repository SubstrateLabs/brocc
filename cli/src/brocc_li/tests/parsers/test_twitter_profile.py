import re

import pytest

from brocc_li.parsers.twitter_profile import twitter_profile_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
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

    # Detailed assertions for profile content
    assert "# rob cheung @perceptnet" in markdown, "Profile header incorrect"
    assert "co-founder@SubstrateLabs" in markdown, "Bio text missing or incorrect"
    assert "Following" in markdown, "Following count missing"
    assert "Followers" in markdown, "Followers count missing"

    # Check for tweets section
    assert "## Tweets" in markdown, "Tweets section header missing"

    # Check for tweet formatting
    assert "### [rob cheung](https://x.com/perceptnet) (@perceptnet)" in markdown, (
        "Tweet author formatting incorrect"
    )

    # Check for tweet metrics
    assert "❤️" in markdown, "Like metrics missing"
    assert "👁️" in markdown, "View metrics missing"

    # Check for media content
    assert "![" in markdown, "Images or media missing"
    assert "format=jpg" in markdown, "Image URLs not properly formatted"

    # Count number of tweets (each starts with ###)
    tweet_count = markdown.count("### [")
    assert tweet_count >= 5, f"Expected at least 5 tweets, found {tweet_count}"

    # Check for timestamps in tweets
    assert re.search(r"· Mar \d+", markdown), "Tweet timestamps missing"

    # Check for engagement metrics pattern
    assert re.search(r"❤️ \d+ 👁️ \d+", markdown), "Engagement metrics pattern missing"

    logger.info(
        f"✅ Twitter profile conversion test passed for {FIXTURE_NAME}. "
        f"Markdown length: {len(markdown)}. {'Output printed above.' if debug else ''}"
    )
