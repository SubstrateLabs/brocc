import pytest

from brocc_li.parsers.instagram_profile import instagram_profile_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_instagram-profile.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    # Convert using unstructured-based parser, pass debug parameter
    markdown = instagram_profile_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START INSTAGRAM PROFILE MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END INSTAGRAM PROFILE MARKDOWN OUTPUT ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"
    assert "<!-- No elements" not in markdown, "Parser reported no elements found."

    # Profile info assertions - Updated based on debug logs and refined parser
    assert "# hausoftiffany" in markdown, "Missing profile header with correct username"
    assert "**Posts**: 85" in markdown, "Missing or incorrect posts count"
    assert "**Followers**: 2,067" in markdown, "Missing or incorrect followers count"
    assert "**Following**: 1,944" in markdown, "Missing or incorrect following count"
    assert "writer find me on X instead" in markdown, "Missing bio text"
    assert "x.com/hausoftiffany" in markdown, "Missing link in bio text"

    # Posts assertions
    assert "## Recent Posts" in markdown, "Missing recent posts section"
    assert "hausoftiffany's profile picture" not in markdown.split("## Recent Posts")[1], (
        "Profile picture included as a post"
    )
    assert "### Post 1" in markdown, "Missing post 1 header"
    assert "*Out of all the days to learn you have an autoimmune disorder" in markdown, (
        "Missing text for post 1"
    )
    assert "### Post 12" in markdown, "Missing post 12 header"
    assert "*it’s hard to explain the state i’ve been in." in markdown, "Missing text for post 12"

    logger.info(
        f"✅ Instagram profile conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else ''}"
    )
