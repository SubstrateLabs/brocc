import pytest

from brocc_li.parsers.linkedin_profile import linkedin_profile_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_linkedin-profile.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    # Convert using unstructured-based parser, pass debug parameter
    markdown = linkedin_profile_html_to_md(html, debug=debug)

    if debug:
        # Print the output for inspection
        print("\n--- START LINKEDIN PROFILE MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END LINKEDIN PROFILE MARKDOWN OUTPUT ---\n")

    # No assertions, just basic checks to ensure parsing completed
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"

    # --- Specific Content Assertions ---
    assert "# Rob Cheung" in markdown, "Profile name not found"
    assert "![Profile Image](" in markdown, "Profile image markdown not found"
    assert "## Experience" in markdown, "Experience section not found"
    assert "Co-Founder, CEO" in markdown, "Specific job title not found in Experience"
    assert "꩜Substrate · Full-time" in markdown, "Company info not found in Experience"
    assert "## Education" in markdown, "Education section not found"
    assert "University of Illinois Urbana-Champaign" in markdown, (
        "University not found in Education"
    )
    assert "## Skills" in markdown, "Skills section not found"
    assert "- Android Development" in markdown, "Specific skill not found"
    assert "## Interests" in markdown, "Interests section not found"
    assert "- South Park Commons" in markdown, "Specific interest not found"
    assert "## Activity" in markdown, "Activity section not found"
    assert "### Post 1" in markdown, "First post header not found"
    assert "_Rob Cheung reposted this_" in markdown, "Repost indicator not found in Activity"
    # --- End Specific Content Assertions ---

    logger.info(
        f"✅ LinkedIn profile conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else ''}"
    )
