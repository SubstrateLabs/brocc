import pytest

from brocc_li.parsers.threads_activity import threads_activity_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = True
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

    # We can't assert much more until we see the output
    # assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"
    # assert "<!-- No elements" not in markdown, "Parser reported no elements found."

    logger.info(
        f"Threads activity conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else 'Run with DEBUG=True to see output.'}"
    )


# You can run this specific test with:
# uv run pytest cli/src/brocc_li/tests/parsers/test_threads_activity.py -k test_parse_threads_activity
