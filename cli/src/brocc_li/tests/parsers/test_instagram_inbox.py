import pytest

from brocc_li.parsers.instagram_inbox import instagram_inbox_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_instagram-inbox.html"


def test_parse_inbox(debug: bool = DEBUG):
    """Tests the basic parsing of Instagram Inbox HTML."""
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found. Please add it to tests/fixtures.")

    # Convert using the new parser, pass debug parameter
    markdown = instagram_inbox_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START INSTAGRAM INBOX MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END INSTAGRAM INBOX MARKDOWN OUTPUT ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"
    assert "<!-- No elements" not in markdown, "Parser reported no elements found by unstructured."
    assert (
        "<!-- unstructured parsing completed, but resulted in empty output -->" not in markdown
    ), "Parser resulted in empty output after processing."

    # User-specific assertions
    assert "**Austin Whittier**" in markdown, "Missing Austin's message thread"
    assert "Austin sent an attachment" in markdown, "Missing Austin's message content"
    assert "(2w)" in markdown, "Missing timestamp for Austin's message"

    assert "**LZ**" in markdown, "Missing LZ's message thread"
    assert "Hi its ben and tiff" in markdown, "Missing LZ's message content"
    assert "[Unread]" in markdown, "Missing unread status indicator"

    assert "**Robert Karpay**" in markdown, "Missing Robert's message thread"
    assert "Pretty alright. You?" in markdown, "Missing Robert's message content"
    assert "(6w)" in markdown, "Missing timestamp for Robert's message"

    assert "**Ski Team**" in markdown, "Missing Ski Team's message thread"
    assert "Ski sent an attachment" in markdown, "Missing Ski Team's message content"

    assert "**Dan Demmitt**" in markdown, "Missing Dan's message thread"
    assert "(Active 9h ago)" in markdown, "Missing active status for Dan's thread"

    assert "**Raisa Ahmed**" in markdown, "Missing Raisa's message thread"
    assert "(Active 27m ago)" in markdown, "Missing minute-based active status"

    assert "**Quan Pratt**" in markdown, "Missing Quan's message thread"
    assert "(Active now)" in markdown, "Missing 'Active now' status"

    assert "**Daisy Vagabond**" in markdown, "Missing Daisy's message thread"
    assert "😂" in markdown, "Missing emoji content in Daisy's message"
    assert "(16w)" in markdown, "Missing timestamp for Daisy's message"

    # Format validation
    assert markdown.count("* **") >= 12, "Expected at least 12 message threads"
    assert markdown.count("(") >= 12, "Expected at least 12 timestamps or activity indicators"

    logger.info(
        f"✅ Instagram inbox conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else 'Run with DEBUG=True to see output.'}"
    )
