from pathlib import Path

import pytest

from brocc_li.parsers.linkedin_company_about import linkedin_company_about_html_to_md
from brocc_li.utils.logger import logger


@pytest.fixture
def fixtures_dir() -> Path:
    """Get the path to the fixtures directory."""
    # Adjust path relative to this test file
    return Path(__file__).parent.parent / "tests" / "html_fixtures"


DEBUG = False  # Set to True to enable debug output


def test_parse_company_about_page(fixtures_dir: Path, debug: bool = DEBUG):
    fixture_name = "_linkedin-company-about.html"
    fixture_path = fixtures_dir / fixture_name

    if not fixture_path.exists():
        logger.warning(f"Fixture {fixture_name} not found at {fixture_path}, skipping test")
        pytest.skip(f"Fixture {fixture_name} not found")
        return

    with open(fixture_path, encoding="utf-8") as f:
        html = f.read()

    # Convert using the company about page parser
    markdown = linkedin_company_about_html_to_md(html, debug=debug)

    # Print the output for inspection when debug is enabled
    if debug:
        print("\n--- START LINKEDIN COMPANY ABOUT PAGE MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END LINKEDIN COMPANY ABOUT PAGE MARKDOWN OUTPUT ---\n")

    # Basic checks
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert len(markdown) > 100, "Markdown content is too short to be valid"

    # Check for expected company metadata
    assert "# Motion" in markdown, "Company name not found or incorrect"
    assert "**Industry:** Software Development" in markdown, "Industry not correctly extracted"
    assert "**Company Size:** 51-200 employees" in markdown, "Company size not correctly extracted"
    assert "usemotion.com" in markdown, "Website not found in output"

    # Make sure we don't have duplicate logo entries
    logo_count = markdown.count("![Company Logo]")
    assert logo_count == 1, f"Expected 1 company logo, found {logo_count}"

    # Check for expected section headers
    assert "## About" in markdown, "About section missing"
    assert "## Locations" in markdown, "Locations section missing"

    # Check for the known location
    assert "Mountain View, CA" in markdown, "Expected location not found in output"

    # Make sure we don't have headquarters field
    assert "**Headquarters:**" not in markdown, "Headquarters should be removed"

    logger.info(f"✅ LinkedIn company about page conversion test ran for {fixture_name}.")
