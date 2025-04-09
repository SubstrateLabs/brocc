import pytest

from brocc_li.parsers.substack_inbox import substack_inbox_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_substack-inbox.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(
            f"Fixture {FIXTURE_NAME} not found. Please create it in the fixtures directory."
        )
    except Exception as e:
        pytest.fail(f"Failed to load fixture {FIXTURE_NAME}: {e}")

    markdown = substack_inbox_html_to_md(html, debug=debug)

    if debug:
        print(f"\n--- START SUBSTACK INBOX MARKDOWN OUTPUT ({FIXTURE_NAME}) ---")
        if markdown:
            print(markdown)
        else:
            print("<<< MARKDOWN OUTPUT IS NONE >>>")
        print(f"--- END SUBSTACK INBOX MARKDOWN OUTPUT ({FIXTURE_NAME}) ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, "Parser reported an error during processing"
    assert "unstructured found no elements" not in markdown, "Parser reported no elements found"

    # Check for main header
    assert "# Substack Inbox" in markdown, "Main header missing"

    # Content structure assertions
    lines = markdown.splitlines()

    # Check that we have a reasonable number of posts
    h3_titles = [line for line in lines if line.startswith("###")]
    assert len(h3_titles) >= 15, "Expected at least 15 posts"

    # Check that posts have titles and metadata
    assert any("Pivot or Persist?" in line for line in lines if line.startswith("###")), (
        "Missing expected post title"
    )
    assert any("**Newsletter**" in line and "Kyla" in line for line in lines), (
        "Missing newsletter metadata"
    )
    assert any("**Author**" in line and "kyla scanlon" in line for line in lines), (
        "Missing author metadata"
    )
    assert any("**Date**" in line for line in lines), "Missing date metadata"

    # Verify some specific posts exist with their metadata
    assert any("Tariff Q&A:" in line for line in lines if line.startswith("###")), (
        "Missing Tariff Q&A post"
    )
    assert any("Gemini 2.5 Pro" in line for line in lines if line.startswith("###")), (
        "Missing Gemini post"
    )

    # Check for formatting patterns
    newsletter_metadata = [line for line in lines if "- **Newsletter**:" in line]
    assert len(newsletter_metadata) >= 10, "Expected at least 10 newsletter metadata entries"

    # Validate proper section structure
    # Find a title line and check if metadata follows it
    for i, line in enumerate(lines):
        if line.startswith("### ") and i < len(lines) - 1:
            assert lines[i + 1].startswith("- **"), (
                f"Post at line {i + 1} missing metadata after title"
            )

    logger.info(
        f"✅ Substack inbox conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else 'Debug output disabled.'}"
    )
