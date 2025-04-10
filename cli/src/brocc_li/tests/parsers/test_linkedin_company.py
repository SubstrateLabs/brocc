import pytest

from brocc_li.parsers.linkedin_company import linkedin_company_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_linkedin-company.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    # Convert using the company profile parser
    markdown = linkedin_company_html_to_md(html, debug=debug)

    # Print the output for inspection only in debug mode
    if debug:
        print("\n--- START LINKEDIN COMPANY PROFILE MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END LINKEDIN COMPANY PROFILE MARKDOWN OUTPUT ---\n")

    # Basic checks
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"

    # Check for specific company content based on what we see in the test output
    assert "# Motion" in markdown, "Company name 'Motion' not found"
    assert "![Company Logo]" in markdown, "Company logo not found"
    assert "World's only AI project manager" in markdown, "Company description not found"
    assert "**Industry:** Software Development" in markdown, "Industry not found or incorrect"
    assert "**Location:** Mountain View, CA" in markdown, "Location not found or incorrect"
    assert "**Followers:** 8K followers" in markdown, "Followers count not found or incorrect"
    assert "**Size:** 51-200 employees" in markdown, "Company size not found or incorrect"

    # Check for section headers
    assert "## Overview" in markdown, "Overview section header not found"
    assert "## Funding" in markdown, "Funding section header not found"

    # Check for specific section content - use flexible matching
    # The overview content might have trailing "..." or "see more" or other variations
    overview_content_exists = any(
        phrase in markdown
        for phrase in ["Motion's AI Project", "maximizes efficiency", "eliminates busywork"]
    )
    assert overview_content_exists, "Overview content not found"

    assert "**Stage:** Series C" in markdown, "Funding stage not found or incorrect"
    assert "**Investors:** 0 total investors" in markdown, "Investors info not found or incorrect"

    # Check no sections exist that we've removed
    assert "## Job Openings" not in markdown, "Job Openings section should not be present"
    assert "## Company Insights" not in markdown, "Company Insights section should not be present"

    # Count sections to ensure we have the expected structure
    section_count = sum(
        1
        for section in [
            "## Overview",
            "## Contact Information",
            "## Funding",
            "## People Highlights",
        ]
        if section in markdown
    )

    # We know from the test output that at least Overview and Funding are present
    assert section_count >= 2, "Expected at least 2 sections (Overview and Funding)"

    logger.info(
        f"✅ LinkedIn company profile conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else ''}"
    )
