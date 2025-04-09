import pytest

from brocc_li.parsers.gmail_inbox import gmail_inbox_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_gmail-inbox.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(
            f"Fixture {FIXTURE_NAME} not found. Please create it in the fixtures directory."
        )
    except Exception as e:
        pytest.fail(f"Failed to load fixture {FIXTURE_NAME}: {e}")

    markdown = gmail_inbox_html_to_md(html, debug=debug)

    if debug:
        print(f"\n--- START GMAIL INBOX MARKDOWN OUTPUT ({FIXTURE_NAME}) ---")
        if markdown:
            print(markdown)
        else:
            print("<<< MARKDOWN OUTPUT IS NONE >>>")
        print(f"--- END GMAIL INBOX MARKDOWN OUTPUT ({FIXTURE_NAME}) ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, "Parser reported an error during processing"

    # Content structure assertions
    assert markdown.startswith("# Gmail Inbox"), "Output should start with inbox header"
    assert "## " in markdown, "Output should contain email headers"
    assert "**From:**" in markdown, "Output should contain sender info"
    assert ">" in markdown, "Output should contain preview text in blockquotes"

    # Specific content assertions
    lines = markdown.split("\n")

    # Check for expected emails
    assert any("Kyle Pitzen" in line for line in lines), "Should contain Kyle Pitzen email"
    assert any("SWL Week in Review" in line for line in lines), (
        "Should contain SWL Week in Review email"
    )
    assert any("Substrate books" in line for line in lines), "Should contain Substrate books email"

    # Check date formatting
    # Look for common date patterns in the output - updated for dateparser format
    date_patterns = [
        # Either the old format or the new dateparser format should work
        "Apr 4",
        "Apr 04, 2023",
        "Apr 04,",
        "Mar 13",
        "Mar 13, 2023",
        "9/7/24",
        "Sep 07, 2024",
    ]

    # Check for at least one date pattern - don't require all to match
    date_found = False
    for date in date_patterns:
        if date in markdown:
            date_found = True
            break
    assert date_found, f"Should contain at least one of the date formats: {date_patterns}"

    sender_lines = [line for line in lines if line.startswith("**From:**")]
    assert len(sender_lines) > 0, "Should have sender lines"

    # Check preview text formatting
    preview_lines = [line for line in lines if line.startswith(">")]
    assert len(preview_lines) > 0, "Should have preview text"
    # Preview text should be reasonably sized (not too long)
    for preview in preview_lines:
        assert len(preview) < 300, "Preview text should be truncated"

    # Check for duplicate headers
    headers = [line for line in lines if line.startswith("##")]
    header_texts = [h.strip("# ") for h in headers]
    assert len(header_texts) == len(set(header_texts)), "Should not have duplicate headers"

    logger.info(
        f"✅ Gmail inbox conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else 'Debug output disabled.'}"
    )
