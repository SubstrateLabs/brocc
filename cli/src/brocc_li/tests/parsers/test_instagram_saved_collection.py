import re

import pytest

from brocc_li.parsers.instagram_saved_collection import instagram_saved_collection_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = True
FIXTURE_NAME = "_instagram-saved-collection.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    # Convert using unstructured-based parser, pass debug parameter
    markdown = instagram_saved_collection_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START INSTAGRAM SAVED COLLECTION MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END INSTAGRAM SAVED COLLECTION MARKDOWN OUTPUT ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"
    assert "<!-- No elements" not in markdown, "Parser reported no elements found."

    # Structure assertions
    assert "# bali" in markdown, "Missing correct collection name in header"
    assert "## Saved Posts" in markdown, "Missing saved posts section"

    # Post structure assertions
    assert "### Post 1" in markdown, "Missing Post 1 heading"
    assert "### Post 2" in markdown, "Missing Post 2 heading"
    assert "### Post 3" in markdown, "Missing Post 3 heading"
    assert "### Post 4" in markdown, "Missing Post 4 heading"

    # Check post count
    post_sections = markdown.split("### Post ")
    assert len(post_sections) == 5, f"Expected 4 posts, found {len(post_sections) - 1}"

    # Content-specific assertions for specific posts
    assert "The most amazing experiences were always unplanned" in markdown, (
        "Missing key content from Post 1"
    )
    assert "These boys are the sweetest" in markdown, "Missing descriptive text from Post 1"
    assert "Tiu Kelep Waterfall" in markdown, "Missing location reference from Post 1"

    # Check for specific hashtags in posts
    assert "**Tags**: #travelindonesia #solotravel #solotrip #adventure" in markdown, (
        "Missing hashtags from Post 1"
    )
    assert "BROMO 15 07 23" in markdown, "Missing BROMO content in Post 2"
    assert "**Tags**: #bromo #wonderfulindonesia #beautifuldestinations" in markdown, (
        "Missing hashtags from Post 2"
    )

    # Image URL assertions
    assert "![Image](https://instagram" in markdown, "Missing image links"
    assert "instagram.fsig5-1.fna.fbcdn.net" in markdown, "Missing expected image domain"

    # Image count assertions
    image_urls = re.findall(r"!\[Image\]\(https://instagram[^\)]+\)", markdown)
    assert len(image_urls) >= 4, f"Expected at least 4 image URLs, found {len(image_urls)}"

    # Check post 3 and 4 formatting
    assert "Image" in post_sections[3], "Post 3 should contain generic image content"
    assert "Image" in post_sections[4], "Post 4 should contain generic image content"

    logger.info(
        f"✅ Instagram saved collection conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else ''}"
    )
