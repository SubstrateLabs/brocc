import pytest

from brocc_li.parsers.linkedin_connections_me import linkedin_connections_me_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = True
FIXTURE_NAME = "_linkedin-connections-me.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(
            f"Fixture {FIXTURE_NAME} not found. Please create it in the fixtures directory."
        )
    except Exception as e:
        pytest.fail(f"Failed to load fixture {FIXTURE_NAME}: {e}")

    markdown = linkedin_connections_me_html_to_md(html, debug=debug)

    if debug:
        print(f"\n--- START LINKEDIN CONNECTIONS/ME MARKDOWN OUTPUT ({FIXTURE_NAME}) ---")
        if markdown:
            print(markdown)
        else:
            print("<<< MARKDOWN OUTPUT IS NONE >>>")
        print(f"--- END LINKEDIN CONNECTIONS/ME MARKDOWN OUTPUT ({FIXTURE_NAME}) ---\n")

    # Basic assertions - will likely need refinement once a real fixture exists
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, "Parser reported an error during processing"
    assert "unstructured found no elements" not in markdown, "Parser reported no elements found"
    assert "No elements remaining after filtering" not in markdown, (
        "Parser reported no elements after filtering"
    )

    # --- Specific Assertions based on the fixture content --- #

    # Check for main headers
    assert "# 2,399 Connections" in markdown, "Main connection count header missing"
    assert "## Recently added" in markdown, "'Recently added' subheader missing"

    # Check for specific connection blocks (using H3 for name)
    assert "### Ken Aizawa" in markdown, "Ken Aizawa header missing"
    assert "- VP of Engineering at TheTake.ai" in markdown, "Ken Aizawa title missing"
    assert "- connected on January 27, 2025" in markdown, "Ken Aizawa connection date missing"

    assert "### John Keane" in markdown, "John Keane header missing"
    assert "- Director of Engineering | AI & ML Strategist" in markdown, (
        "John Keane title missing (partial)"
    )
    assert "- connected on January 21, 2025" in markdown, "John Keane connection date missing"

    assert "### Morgante ⚡ Pell" in markdown, "Morgante Pell header missing"
    assert "- Let Grit automate your software toil" in markdown, "Morgante Pell description missing"
    assert "- connected on September 24, 2024" in markdown, "Morgante Pell connection date missing"

    # Check for rough number of connections parsed (count H3 headers)
    # Based on the log, we processed 8 connections correctly.
    # Eli Brosh and Rish Gupta were skipped.
    connection_headers = [line for line in markdown.split("\n") if line.startswith("### ")]
    assert len(connection_headers) == 8, (
        f"Expected 8 connection headers (###), found {len(connection_headers)}"
    )

    # Check that noisy elements were removed
    assert "Message" not in markdown, "'Message' action button should be filtered out"
    assert "Sort by:" not in markdown, "'Sort by:' should be filtered out"
    assert "Search with filters" not in markdown, "'Search with filters' should be filtered out"
    assert "LinkedIn Corporation" not in markdown, "Footer content should be filtered out"

    logger.info(
        f"✅ LinkedIn connections/me conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else 'Debug output disabled.'}"
    )
