import pytest

from brocc_li.parsers.linkedin_company_people import linkedin_company_people_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_linkedin-company-people.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(
            f"Fixture {FIXTURE_NAME} not found. Please create it in the fixtures directory."
        )
    except Exception as e:
        pytest.fail(f"Failed to load fixture {FIXTURE_NAME}: {e}")

    markdown = linkedin_company_people_html_to_md(html, debug=debug)

    if debug:
        print(f"\n--- START LINKEDIN COMPANY PEOPLE MARKDOWN OUTPUT ({FIXTURE_NAME}) ---")
        if markdown:
            print(markdown)
        else:
            print("<<< MARKDOWN OUTPUT IS NONE >>>")
        print(f"--- END LINKEDIN COMPANY PEOPLE MARKDOWN OUTPUT ({FIXTURE_NAME}) ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, "Parser reported an error during processing"
    assert "unstructured found no elements" not in markdown, "Parser reported no elements found"
    assert "No elements remaining after filtering" not in markdown, (
        "Parser reported no elements after filtering"
    )

    # Check for main header
    assert "# LinkedIn Company People" in markdown, "Main header missing"

    # Check for company information
    assert "## Company Information" in markdown, "Company information section missing"
    assert "World's only AI project manager" in markdown, "Company description missing"
    assert "8K followers" in markdown, "Company followers count missing"
    assert "51-200 employees" in markdown, "Company employee count missing"

    # Check for people section
    assert "## People" in markdown, "People section missing"

    # Check for specific people
    assert "### Omid Rooholfada" in markdown, "Missing specific person: Omid Rooholfada"
    assert "### Brian Wool" in markdown, "Missing specific person: Brian Wool"

    # Check for job titles with the new format
    assert "- *Co-Founder @ Motion*" in markdown, "Missing job title: Co-Founder @ Motion"
    assert "- *Engineering Manager @ Motion*" in markdown, (
        "Missing job title: Engineering Manager @ Motion"
    )

    # Make sure company name isn't duplicated in the people section
    people_section_start = markdown.find("## People")
    assert markdown.find("Motion", people_section_start) > 0, (
        "Company name should be mentioned in people section (e.g., in job titles)"
    )
    assert markdown.count("### Motion") == 0, "Company name should not be listed as a person"

    # Connection information
    assert "mutual connection" in markdown, "Missing connection information"
    assert "2nd degree connection" in markdown, "Missing connection degree information"

    # Verify no duplicate entries for the same person
    person_sections = [line for line in markdown.split("\n") if line.startswith("###")]
    assert len(person_sections) >= 10, "Expected at least 10 people entries"

    # Check that job titles and connection info both use bullet points
    job_title_lines = [line for line in markdown.split("\n") if "@ Motion" in line]
    for line in job_title_lines:
        assert line.startswith("- "), f"Job title should start with bullet point: {line}"

    # The test shouldn't have duplicate adjacent lines
    lines = markdown.split("\n")
    for i in range(len(lines) - 1):
        if lines[i] and lines[i + 1] and lines[i] == lines[i + 1]:
            # Fix linter warning by using proper exception instead of assert False
            raise AssertionError(f"Found duplicate adjacent lines: {lines[i]}")

    logger.info(
        f"✅ LinkedIn company people conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else 'Debug output disabled.'}"
    )
