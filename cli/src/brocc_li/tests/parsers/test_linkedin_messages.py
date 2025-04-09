import pytest

from brocc_li.parsers.linkedin_messages import linkedin_messages_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_linkedin-messages.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(
            f"Fixture {FIXTURE_NAME} not found. Please create it in the fixtures directory."
        )
    except Exception as e:
        pytest.fail(f"Failed to load fixture {FIXTURE_NAME}: {e}")

    markdown = linkedin_messages_html_to_md(html, debug=debug)

    if debug:
        print(f"\n--- START LINKEDIN MESSAGES MARKDOWN OUTPUT ({FIXTURE_NAME}) ---")
        if markdown:
            print(markdown)
        else:
            print("<<< MARKDOWN OUTPUT IS NONE >>>")
        print(f"--- END LINKEDIN MESSAGES MARKDOWN OUTPUT ({FIXTURE_NAME}) ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, "Parser reported an error during processing"
    assert "unstructured found no elements" not in markdown, "Parser reported no elements found"
    assert "No elements remaining after filtering" not in markdown, (
        "Parser reported no elements after filtering"
    )

    # Check for main header
    assert "# LinkedIn Messages" in markdown, "Main header missing"

    # Check for specific people we expect to find with proper date format
    assert "## Talha Khan - Apr 8" in markdown, "Talha Khan with date missing or wrong format"
    assert "## Jack O'Brien - Mar 30" in markdown, "Jack O'Brien with date missing or wrong format"
    assert "## Colton Dempsey - Mar 20" in markdown, (
        "Colton Dempsey with date missing or wrong format"
    )

    # Check for specific message content
    assert "friend from Insight and I are hosting an Ai Agents Dinner" in markdown, (
        "Expected message content not found"
    )
    assert "conversation at a time" in markdown, "Expected conversation details content not found"
    assert "Would love to have you join us" in markdown, "Expected invitation content not found"

    # Verify long messages are formatted in code blocks
    assert "```\nTalha: Hey Ben!" in markdown, "Long message not formatted in code block"
    assert "```\nColton: Hi Ben" in markdown, "Colton message not formatted in code block"

    # Verify shorter messages without code blocks
    assert "Jack: Just grabbed some time Tuesday" in markdown and (
        "```\nJack: Just grabbed" not in markdown
    ), "Short message formatted incorrectly"

    # Check formatting - verify we're not showing status info
    assert "Status is reachable" not in markdown, "Status info should be filtered"
    assert "Status is offline" not in markdown, "Status info should be filtered"

    # Verify date formatting
    assert "Apr 8 Apr 8" not in markdown, "Duplicate date pattern 'Apr 8 Apr 8' should be cleaned"
    assert "Mar 30 Mar 30" not in markdown, (
        "Duplicate date pattern 'Mar 30 Mar 30' should be cleaned"
    )

    # Make sure noise is filtered
    assert "Press return to go to" not in markdown, "Navigation prompts should be filtered"
    assert "new notification" not in markdown, "Notifications should be filtered"
    assert "Jump to active conversation" not in markdown, "Navigation elements should be filtered"

    # Verify we're handling timestamps correctly
    assert "12:18 PM" in markdown, "Timestamp not preserved correctly"

    # Verify we don't have duplicate entries for the same person/message
    person_headers = [line for line in markdown.split("\n") if line.startswith("## Talha Khan")]
    assert len(person_headers) <= 4, (
        f"Too many duplicate headers for Talha Khan: {len(person_headers)}"
    )

    # The test shouldn't have duplicate adjacent lines right next to each other
    lines = markdown.split("\n")
    for i in range(len(lines) - 1):
        if lines[i] and lines[i + 1] and lines[i] == lines[i + 1]:
            # Fix linter warning by using proper exception instead of assert False
            raise AssertionError(f"Found duplicate adjacent lines: {lines[i]}")

    logger.info(
        f"✅ LinkedIn messages conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else 'Debug output disabled.'}"
    )
