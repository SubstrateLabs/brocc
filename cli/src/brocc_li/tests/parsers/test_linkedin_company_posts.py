import pytest

from brocc_li.parsers.linkedin_company_posts import linkedin_company_posts_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_linkedin-company-posts.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

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

    logger.info(
        f"✅ LinkedIn company posts conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else ''}"
    )
