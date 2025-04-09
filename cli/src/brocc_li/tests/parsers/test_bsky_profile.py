import pytest

from brocc_li.parsers.bsky_profile import bsky_profile_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_bsky-profile.html"


def test_parse_bsky_profile(debug: bool = DEBUG):
    logger.info(f"--- Starting test_parse_bsky_profile for {FIXTURE_NAME} ---")
    try:
        html = get_fixture(FIXTURE_NAME)
        logger.info(f"Successfully loaded fixture: {FIXTURE_NAME} (length: {len(html)})")
    except FileNotFoundError:
        logger.error(f"Fixture {FIXTURE_NAME} not found.")
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    # Convert using the new Bluesky parser
    markdown = bsky_profile_html_to_md(html, debug=debug)

    # Print the output for inspection
    if debug:
        print("\n--- START BLUESKY PROFILE MARKDOWN OUTPUT ---")
        if markdown:
            print(markdown)
        else:
            print("!!! MARKDOWN OUTPUT IS NONE !!!")
        print("--- END BLUESKY PROFILE MARKDOWN OUTPUT ---\n")

    # Basic check to ensure *something* was returned
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"

    # --- Add Focused Assertions based on _bsky-profile.html fixture ---
    assert "# Kyle Pitzen @kpitzen.io" in markdown, "Profile name/handle missing or incorrect"
    assert "kpitzen.io](https://www.kpitzen.io)" in markdown, "Bio link missing or incorrect"
    assert "**21 followers • 151 following • 0 posts**" in markdown, "Stats missing or incorrect"
    assert "\n## Posts" in markdown, "Posts section header missing"
    # Check for first post's header
    assert (
        "### [‪The New York Times‬](https://bsky.app/profile/nytimes.com) (‪@nytimes.com‬)" in markdown
    ), "First post header missing or incorrect"
    # Check for first post's metrics
    assert "💬 33   🔄 168   ❤️ 476" in markdown, "First post metrics missing or incorrect"
    # Check number of posts (count the H3 headers)
    assert markdown.count("\n### ") == 5, (
        f"Expected 5 posts (### headers), found {markdown.count('\n### ')}"
    )
    # --- End Focused Assertions ---

    logger.info(
        f"✅ Bluesky profile conversion test ran for {FIXTURE_NAME}. "
        f"Markdown length: {len(markdown) if markdown else 0}. Output printed above."
    )
    logger.info(f"--- Finished test_parse_bsky_profile for {FIXTURE_NAME} ---")


# You can run this test specifically using:
# cd cli && uv run pytest src/brocc_li/tests/parsers/test_bsky_profile.py
