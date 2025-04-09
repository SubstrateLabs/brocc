import re

import pytest

from brocc_li.parsers.instagram_saved_collection import instagram_saved_collection_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
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
    for hashtag in ["#travelindonesia", "#solotravel", "#solotrip", "#adventure"]:
        assert hashtag in post_sections[1], f"Missing hashtag {hashtag} in Post 1"

    assert "BROMO 15 07 23" in post_sections[2], "Missing BROMO content in Post 2"

    for hashtag in ["#bromo", "#wonderfulindonesia", "#beautifuldestinations"]:
        assert hashtag in post_sections[2], f"Missing hashtag {hashtag} in Post 2"

    # Image URL assertions
    assert "![Image](https://instagram" in markdown, "Missing image links"
    assert "instagram.fsig5-1.fna.fbcdn.net" in markdown, "Missing expected image domain"

    # Image count assertions
    image_urls = re.findall(r"!\[Image\]\(https://instagram[^\)]+\)", markdown)
    assert len(image_urls) >= 4, f"Expected at least 4 image URLs, found {len(image_urls)}"

    # Check post 3 and 4 formatting
    assert "Image" in post_sections[3], "Post 3 should contain generic image content"
    assert "Image" in post_sections[4], "Post 4 should contain generic image content"

    # Additional focused assertions based on output

    # More specific content checks for Post 1
    assert "I felt like a princess surrounded by a bunch of guards" in post_sections[1], (
        "Missing princess metaphor in Post 1"
    )
    assert (
        "📍Not an attraction, just a bridge leading to Tiu Kelep Waterfall" in post_sections[1]
    ), "Missing location emoji and description in Post 1"

    # More specific content checks for Post 2
    assert "⛰️" in post_sections[2], "Missing mountain emoji in Post 2"

    # Check Post 3 attribution format
    assert (
        "Photo by ULEKAN BALI™ | Traditional Indonesian Cuisine on June 01, 2023"
        in post_sections[3]
    ), "Missing correct attribution in Post 3"

    # Check Post 4 attribution format
    assert (
        "Photo shared by Bodyworks Spa on October 25, 2022 tagging @sal.harris" in post_sections[4]
    ), "Missing correct attribution in Post 4"

    # Check URL formats and patterns
    for image_url in image_urls:
        assert "cdn.net" in image_url, f"Image URL missing CDN domain: {image_url}"
        assert re.search(r"_n\.jpg\?", image_url), (
            f"Image URL missing expected jpg format: {image_url}"
        )

    # Check tag formatting consistency
    assert "**Tags**:" in post_sections[1], "Missing Tags section in Post 1"
    assert "**Tags**:" in post_sections[2], "Missing Tags section in Post 2"

    # Check specific image formats in URLs
    assert re.search(r"t51\.2885-15/\d+", markdown), "Missing expected image format pattern in URLs"

    logger.info(
        f"✅ Instagram saved collection conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else ''}"
    )
