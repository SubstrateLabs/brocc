import pytest
import re

from brocc_li.parsers.bsky_feed import bsky_feed_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False  # Enable debug logging and printing by default
FIXTURE_NAME = "_bsky-feed.html"  # TODO: Create this fixture file


def test_parse_bsky_feed():
    logger.info(f"--- Starting test_parse_bsky_feed for {FIXTURE_NAME} ---")
    try:
        # Attempt to load the fixture file
        html = get_fixture(FIXTURE_NAME)
        logger.info(f"Successfully loaded fixture: {FIXTURE_NAME}")
    except FileNotFoundError:
        logger.error(f"Fixture file {FIXTURE_NAME} not found. Skipping test.")
        pytest.skip(f"Fixture {FIXTURE_NAME} not found")
    except Exception as e:
        logger.error(f"Error loading fixture {FIXTURE_NAME}: {e}", exc_info=True)
        pytest.fail(f"Failed to load fixture {FIXTURE_NAME}: {e}")

    # Convert using the placeholder parser
    logger.info("Calling bsky_feed_html_to_md...")
    markdown = bsky_feed_html_to_md(html, debug=DEBUG)

    # Print the output for inspection
    if DEBUG:
        print("\n--- START BLUESKY FEED MARKDOWN OUTPUT (Placeholder) ---")
        # Handle potential None return, though current placeholder returns empty string or error
        print(markdown if markdown is not None else "[Parser returned None]")
        print("--- END BLUESKY FEED MARKDOWN OUTPUT (Placeholder) ---\n")

    # Basic assertions (will likely fail until real parser/fixture exists)
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    # Re-enable error check now that placeholders are gone
    assert "Error converting" not in markdown, f"Conversion failed: {markdown}"
    # Re-enable non-empty check
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"

    # --- Assertions for Content & Format (Based on _bsky-feed.html fixture) ---
    logger.info("Performing content assertions...")

    # Check for post header format
    assert "### " in markdown, "Missing H3 headers for posts"

    # Check for specific user
    assert "Kara Swisher" in markdown, "Missing 'Kara Swisher' display name"
    assert "@karaswisher.bsky.social" in markdown, "Missing '@karaswisher.bsky.social' handle"

    # Check for content snippet from Kara's post
    assert "peak beta chode for Ackman" in markdown, (
        "Missing content snippet from Kara Swisher post"
    )

    # Check for metric emojis
    assert "💬" in markdown, "Missing replies emoji"
    assert "🔄" in markdown, "Missing reposts emoji"
    assert "❤️" in markdown, "Missing likes emoji"

    # Check for reasonable metrics on the first post (Kara Swisher's)
    # Find the first metrics line
    first_post_match = re.search(r"💬 (\d+)   🔄 (\d+)   ❤️ (\d+)", markdown)
    assert first_post_match, "Could not find first post's metrics line using regex"

    replies = int(first_post_match.group(1))
    reposts = int(first_post_match.group(2))
    likes = int(first_post_match.group(3))

    logger.info(f"First post metrics found: Replies={replies}, Reposts={reposts}, Likes={likes}")
    assert replies > 100, f"Expected >100 replies for first post, got {replies}"
    assert reposts > 1000, (
        f"Expected >1000 reposts for first post, got {reposts}"
    )  # Based on sample output: 2300
    assert likes > 10000, (
        f"Expected >10000 likes for first post, got {likes}"
    )  # Based on sample output: 15500

    logger.info(f"--- Finished test_parse_bsky_feed for {FIXTURE_NAME} ---")
