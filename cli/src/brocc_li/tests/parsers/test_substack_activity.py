import pytest

from brocc_li.parsers.substack_activity import substack_activity_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_substack-activity.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    # Convert using unstructured-based parser, pass debug parameter
    markdown = substack_activity_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START SUBSTACK ACTIVITY MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END SUBSTACK ACTIVITY MARKDOWN OUTPUT ---\n")

    # Basic assertions (keep minimal checks)
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"

    # Light focused assertions on the structure and content
    assert "### " in markdown, "No H3 headers found in the output"

    # Check for expected users - keep this minimal and focused
    expected_users = ["Zach Magdovitz", "Chris Finlayson"]
    for user in expected_users:
        assert user in markdown, f"Expected user not found: {user}"

    # Check for types of activities - keeping this high level
    activity_types = ["subscribed", "liked", "followed"]
    activity_found = False
    for activity in activity_types:
        if activity in markdown:
            activity_found = True
            break
    assert activity_found, "No expected activity types found in output"

    # Check for formatting elements
    assert "**" in markdown, "No bold formatting found for activities"

    # Check proper date/time formatting in some form
    time_indicators = ["d)", "h)", "Mar", "Feb"]
    timestamp_found = False
    for indicator in time_indicators:
        if indicator in markdown:
            timestamp_found = True
            break
    assert timestamp_found, "No timestamp formatting found in output"

    logger.info(
        f"✅ Substack activity conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else ''}"
    )
