import pytest

from brocc_li.parsers.instagram_explore_search import instagram_explore_search_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_instagram-explore-search.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    # Convert using unstructured-based parser, pass debug parameter
    markdown = instagram_explore_search_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START INSTAGRAM EXPLORE SEARCH MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END INSTAGRAM EXPLORE SEARCH MARKDOWN OUTPUT ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"
    assert "<!-- No elements" not in markdown, "Parser reported no elements found."

    # Simple content assertions
    assert "# Instagram Search Results" in markdown, "Missing header"
    assert "### Post" in markdown, "Missing any post content"

    # Focused content assertions
    assert "Ramen" in markdown, "Missing search term 'Ramen'"

    # Check post count (at least 15 posts)
    post_count = markdown.count("### Post")
    assert post_count >= 15, f"Expected at least 15 posts, but found {post_count}"

    # Check specific post content
    assert "Spicy Miso Ramen! I find few things more" in markdown, "Missing specific ramen post"
    assert "Gon be a spicy one 🔥🌶️🌶️" in markdown, "Missing spicy ramen post"
    assert "All the food (almost) you need to try in Japan & Korea" in markdown, (
        "Missing food list post"
    )

    # Check image URLs are being truncated
    assert "[...]" in markdown, "Image URLs are not being truncated"

    # Check duplicate handling
    assert markdown.count("Photo by Serious Eats") <= 1, "Duplicate caption not filtered"

    # Check engagement metrics
    assert "garlic" in markdown.lower() and "chili" in markdown.lower(), "Missing recipe content"

    logger.info(
        f"✅ Instagram explore/search conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else ''}"
    )
