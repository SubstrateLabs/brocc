from pathlib import Path

import pytest

from brocc_li.parsers.linkedin_company_posts import linkedin_company_posts_html_to_md
from brocc_li.utils.logger import logger


@pytest.fixture
def fixtures_dir() -> Path:
    """Get the path to the fixtures directory."""
    # Adjust path relative to this test file
    return Path(__file__).parent.parent / "tests" / "html_fixtures"


DEBUG = False  # Enable debug output by default


def test_parse_company_posts(fixtures_dir: Path, debug: bool = DEBUG):
    fixture_name = "_linkedin-company-posts.html"
    fixture_path = fixtures_dir / fixture_name

    if not fixture_path.exists():
        logger.warning(f"Fixture {fixture_name} not found at {fixture_path}, skipping test")
        pytest.skip(f"Fixture {fixture_name} not found")
        return

    with open(fixture_path, encoding="utf-8") as f:
        html = f.read()

    # Convert using the company posts parser
    markdown = linkedin_company_posts_html_to_md(html, debug=debug)

    if debug:
        # Print the output for inspection
        print("\n--- START LINKEDIN COMPANY POSTS MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END LINKEDIN COMPANY POSTS MARKDOWN OUTPUT ---\n")

    # Basic checks
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "## Company Posts" in markdown, "Company Posts header not found"

    # Content assertions
    assert "Motion" in markdown, "Company name not found"
    assert "![Company Logo]" in markdown, "Company logo not found"
    assert "Making sure you keep track of your team's projects" in markdown, (
        "First post content not found"
    )

    # Author attributions
    assert "reposted this" in markdown, "Repost attribution not found"

    logger.info(f"✅ LinkedIn company posts conversion test ran for {fixture_name}.")
