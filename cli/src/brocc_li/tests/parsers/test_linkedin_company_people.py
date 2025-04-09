import pytest

from brocc_li.parsers.linkedin_company_people import (
    linkedin_company_people_html_to_md,
)
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False  # Set to True to print output
FIXTURE_NAME = "_linkedin-company-people.html"  # Make sure this fixture exists


def test_parse_linkedin_company_people(debug: bool = DEBUG):
    """Tests the basic parsing of LinkedIn company people HTML."""
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found. Please add it to the fixtures directory.")

    # Convert using the new parser
    markdown = linkedin_company_people_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START LINKEDIN COMPANY PEOPLE MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END LINKEDIN COMPANY PEOPLE MARKDOWN OUTPUT ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"
    assert "<!-- No elements" not in markdown, "Parser reported no elements found."

    # TODO: Add more specific assertions once the expected output is known
    # For now, we just check that it ran and produced something.

    logger.info(
        f"✅ LinkedIn company people conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else ''}"
    )
