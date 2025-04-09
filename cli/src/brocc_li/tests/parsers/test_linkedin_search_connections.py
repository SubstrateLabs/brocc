import pytest

from brocc_li.parsers.linkedin_search_connections import linkedin_search_connections_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_linkedin-search-connections.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(
            f"Fixture {FIXTURE_NAME} not found. Please create it in the fixtures directory."
        )
    except Exception as e:
        pytest.fail(f"Failed to load fixture {FIXTURE_NAME}: {e}")

    markdown = linkedin_search_connections_html_to_md(html, debug=debug)

    if debug:
        print(f"\n--- START LINKEDIN SEARCH CONNECTIONS MARKDOWN OUTPUT ({FIXTURE_NAME}) ---")
        if markdown:
            print(markdown)
        else:
            print("<<< MARKDOWN OUTPUT IS NONE >>>")
        print(f"--- END LINKEDIN SEARCH CONNECTIONS MARKDOWN OUTPUT ({FIXTURE_NAME}) ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, "Parser reported an error during processing"
    assert "unstructured found no elements" not in markdown, "Parser reported no elements found"
    assert "No elements remaining after filtering" not in markdown, (
        "Parser reported no elements after filtering"
    )

    # Check for main header
    assert "# LinkedIn Search Connections" in markdown, "Main header missing"

    # Check for specific people we expect to find with markdown links
    assert "## [Si Kai Lee](https://www.linkedin.com/in/sikailee)" in markdown, (
        "Si Kai Lee link missing or wrong format"
    )
    assert "## [Jake Nyquist](https://www.linkedin.com/in/jake-nyquist)" in markdown, (
        "Jake Nyquist link missing or wrong format"
    )
    assert "## [Sidharth Shanker](https://www.linkedin.com/in/sidharthshanker)" in markdown, (
        "Sidharth Shanker link missing or wrong format"
    )

    # Check for specific details
    assert "Data Scientist @ Gaimin" in markdown, "Expected job title not found"
    assert "Head of Protocol at Caldera" in markdown, "Expected job title not found"
    assert "New York, NY" in markdown, "Expected location not found"

    # Check for connection information
    assert "mutual connections" in markdown, "Connection information missing"

    # Verify noise has been filtered out
    assert "Status is" not in markdown, "Status indicators should be filtered out"
    assert "2nd degree connection" not in markdown, "Connection degree should be filtered out"
    assert "Search with Recruiter" not in markdown, "Recruiter info should be filtered out"

    # Verify profile formatting
    # Check that we have some bullet points (details)
    bullet_points = [line for line in markdown.split("\n") if line.startswith("- ")]
    assert len(bullet_points) > 5, "Expected more profile details as bullet points"

    # Check that profiles are properly separated
    profile_headers = [line for line in markdown.split("\n") if line.startswith("## [")]
    assert len(profile_headers) >= 5, "Expected at least 5 profile headers"

    logger.info(
        f"✅ LinkedIn search connections conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else 'Debug output disabled.'}"
    )
