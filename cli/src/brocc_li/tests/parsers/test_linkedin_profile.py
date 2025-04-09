from pathlib import Path

import pytest

from brocc_li.parsers.linkedin_profile import linkedin_profile_html_to_md
from brocc_li.utils.logger import logger


@pytest.fixture
def fixtures_dir() -> Path:
    """Get the path to the fixtures directory."""
    return Path(__file__).parent.parent / "html_fixtures"


DEBUG = False  # Enable debug output by default


def test_parse_profile(fixtures_dir: Path, debug: bool = DEBUG):
    fixture_name = "_linkedin-profile.html"
    fixture_path = fixtures_dir / fixture_name

    if not fixture_path.exists():
        logger.warning(f"Fixture {fixture_name} not found at {fixture_path}, skipping test")
        return

    with open(fixture_path, encoding="utf-8") as f:
        html = f.read()

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

    logger.info(f"✅ LinkedIn profile conversion test ran for {fixture_name}.")
