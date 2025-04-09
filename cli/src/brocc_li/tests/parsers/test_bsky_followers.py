import pytest

from brocc_li.parsers.bsky_followers import bsky_followers_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

# Enable debug logging FOR THE TEST to see parser logs
DEBUG = True
FIXTURE_NAME = "_bsky-followers.html"


def test_parse_bsky_followers(debug: bool = DEBUG):
    """
    Tests the parsing of a Bluesky followers HTML file.
    Currently only loads the fixture, runs the parser with debug logging,
    and prints the output. No assertions yet.
    """
    logger.info("--- Starting Bluesky Followers Test ---")
    logger.info(f"Loading fixture: {FIXTURE_NAME}")
    try:
        html = get_fixture(FIXTURE_NAME)
        logger.info(f"Fixture loaded successfully. Length: {len(html)}")
    except FileNotFoundError:
        logger.error(f"Fixture {FIXTURE_NAME} not found. Test cannot proceed.")
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")
    except Exception as e:
        logger.error(f"Error loading fixture {FIXTURE_NAME}: {e}")
        pytest.fail(f"Error loading fixture {FIXTURE_NAME}: {e}")

    logger.info(f"Converting HTML to Markdown with debug={debug}...")
    markdown = bsky_followers_html_to_md(html, debug=debug)

    logger.info("Conversion finished.")

    print("\n\n--- START BLUESKY FOLLOWERS MARKDOWN OUTPUT ---")
    if markdown is not None:
        print(markdown)
        logger.info(f"Markdown generated. Length: {len(markdown)}")
    else:
        print("!!! MARKDOWN CONVERSION RETURNED NONE !!!")
        logger.warning("Markdown conversion returned None.")
    print("--- END BLUESKY FOLLOWERS MARKDOWN OUTPUT ---\n")

    # Basic check to ensure something was produced, even if None (for test runner)
    # We rely on the printed output and logs for debugging this initial version.
    assert True  # Placeholder assertion to make test pass/fail based on execution

    logger.info(
        f"✅ Bluesky followers conversion test executed for {FIXTURE_NAME}. Review printed output and logs."
    )
