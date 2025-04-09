import pytest

from brocc_li.parsers.linkedin_followers import linkedin_followers_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_linkedin-followers.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(
            f"Fixture {FIXTURE_NAME} not found. Please create it in the fixtures directory."
        )
    except Exception as e:
        pytest.fail(f"Failed to load fixture {FIXTURE_NAME}: {e}")

    markdown = linkedin_followers_html_to_md(html, debug=debug)

    if debug:
        print(f"\n--- START LINKEDIN FOLLOWERS MARKDOWN OUTPUT ({FIXTURE_NAME}) ---")
        if markdown:
            print(markdown)
        else:
            print("<<< MARKDOWN OUTPUT IS NONE >>>")
        print(f"--- END LINKEDIN FOLLOWERS MARKDOWN OUTPUT ({FIXTURE_NAME}) ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, "Parser reported an error during processing"
    assert "unstructured found no elements" not in markdown, "Parser reported no elements found"
    assert "No elements remaining after filtering" not in markdown, (
        "Parser reported no elements after filtering"
    )

    # Check for main header
    assert "# LinkedIn Followers" in markdown, "Main header missing"

    # Check for profile links
    assert (
        "[Shubhangi Sharma](https://www.linkedin.com/in/ACoAAD8bw7wBRm2jCAyK7d5Maln1flX01Im31rI)"
        in markdown
    ), "Expected profile link not found"
    assert (
        "[Satwik Vaishnava](https://www.linkedin.com/in/ACoAADeHxwMB8jhi1ImxYuGotzyDqRi2TUIli90)"
        in markdown
    ), "Expected profile link not found"

    # Check for section separators
    assert "### Garrett, Bond Leung and 3 others you know followed" in markdown, (
        "Section separator missing"
    )

    # Check for job descriptions (bullet points)
    assert "- Outbound lead generation for B2B SaaS and Agencies" in markdown, (
        "Job description missing"
    )
    assert (
        "- Co-founder at Forty | Ex-Google | Marketing Strategist & Business Growth Specialist"
        in markdown
    ), "Job description missing"

    # Check for profiles after the section separator
    assert (
        "[Divjot Singh](https://www.linkedin.com/in/ACoAADeWmHAB9A0GopfRo-2WqAnuyyffuegYKNk)"
        in markdown
    ), "Profile after section separator missing"

    # Verify proper structure - count specific elements
    profile_headers = len(
        [line for line in markdown.split("\n") if line.startswith("## [") and "](" in line]
    )
    assert profile_headers >= 8, f"Expected at least 8 profile headers, got {profile_headers}"

    descriptions = len([line for line in markdown.split("\n") if line.startswith("- ")])
    assert descriptions >= 8, f"Expected at least 8 descriptions, got {descriptions}"

    section_headers = len([line for line in markdown.split("\n") if line.startswith("### ")])
    assert section_headers >= 1, f"Expected at least 1 section header, got {section_headers}"

    # Basic content checks - very minimal for now since we're just setting up
    assert len(markdown.split("\n")) > 3, "Expected more than 3 lines in output"

    logger.info(
        f"✅ LinkedIn followers conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else 'Debug output disabled.'}"
    )
