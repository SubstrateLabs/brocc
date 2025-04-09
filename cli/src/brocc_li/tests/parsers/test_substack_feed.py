import pytest

from brocc_li.parsers.substack_feed import substack_feed_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_substack-feed.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    # Convert using unstructured-based parser, pass debug parameter
    markdown = substack_feed_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START SUBSTACK FEED MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END SUBSTACK FEED MARKDOWN OUTPUT ---\n")

    # Basic assertions (keep minimal checks)
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"
    assert "<!-- unstructured found no elements -->" not in markdown, (
        "Parser reported no elements found."
    )

    # Focused assertions for key content
    assert "### " in markdown, "No section headers found"

    # Check for content types
    assert "read" in markdown, "Missing reading time indicators"
    assert "Followed by" in markdown, "Missing follower information"

    # Verify some post content exists
    assert any(keyword in markdown for keyword in ["AI", "Trump", "LLM"]), (
        "Missing expected content keywords"
    )

    logger.info(
        f"✅ Substack feed conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else ''}"
    )
