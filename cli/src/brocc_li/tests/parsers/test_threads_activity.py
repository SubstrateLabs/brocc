import pytest

from brocc_li.parsers.threads_activity import threads_activity_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_threads-activity.html"


def test_parse_threads_activity(debug: bool = DEBUG):
    """Tests the basic parsing of Threads activity HTML."""
    try:
        # NOTE: This fixture doesn't exist yet! The test will fail until created.
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        logger.warning(f"Fixture {FIXTURE_NAME} not found. Skipping test.")
        pytest.skip(f"Fixture {FIXTURE_NAME} not found")
        return  # Explicit return to satisfy linters

    # Convert using the parser, pass debug parameter
    markdown = threads_activity_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START THREADS ACTIVITY MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END THREADS ACTIVITY MARKDOWN OUTPUT ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"
    assert "<!-- No elements" not in markdown, "Parser reported no elements found."

    # Focused high-level assertions
    # Check for specific users and content patterns
    assert "### Started a thread by [stoopingnyc]" in markdown, "Missing stoopingnyc's thread"
    assert "Is everyone putting out their large sideboards?" in markdown, (
        "Missing stoopingnyc's content"
    )

    # Verify profile links format
    assert "https://www.threads.net/@" in markdown, "Missing profile links"

    # Check for timestamp format
    assert "*   5h" in markdown, "Missing timestamp in expected format"

    # Verify likes and replies stats exist only for appropriate entries
    assert "102 likes" in markdown, "Missing likes count for walter.chen's post"
    assert "18 replies" in markdown, "Missing replies count for walter.chen's post"

    # Check some other key activity types
    assert "### Followed you by [godstears]" in markdown, "Missing 'Followed you' activity"
    assert "### Picked for you by [nytimes]" in markdown, "Missing 'Picked for you' activity"

    # Verify item count (we should have at least 8 activity items based on the debug output)
    activity_sections = markdown.split("\n\n\n")
    assert len(activity_sections) >= 8, (
        f"Expected at least 8 activity items, got {len(activity_sections)}"
    )

    # Verify disco_stevo item was excluded (as it had no unique content)
    assert "disco_stevo" not in markdown, (
        "disco_stevo item should be excluded due to lack of content"
    )

    logger.info(
        f"Threads activity conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else 'Run with DEBUG=True to see output.'}"
    )
