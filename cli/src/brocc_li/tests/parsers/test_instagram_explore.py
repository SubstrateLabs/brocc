import re

import pytest

from brocc_li.parsers.instagram_explore import instagram_explore_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_instagram-explore.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    # Convert using unstructured-based parser, pass debug parameter
    markdown = instagram_explore_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START INSTAGRAM EXPLORE MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END INSTAGRAM EXPLORE MARKDOWN OUTPUT ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"
    assert "<!-- No elements" not in markdown, "Parser reported no elements found."

    # Structure assertions
    assert "# Instagram Explore" in markdown, "Missing main header"
    assert "## Posts" in markdown, "Missing posts section"

    # Post structure assertions
    assert "### Post 1" in markdown, "Missing Post 1 heading"
    assert "### Post 2" in markdown, "Missing Post 2 heading"

    # Split markdown into posts for more targeted assertions
    posts_split = markdown.split("### Post ")
    assert len(posts_split) > 15, "Expected at least 15 posts after split"

    post1_content = posts_split[1] if len(posts_split) > 1 else ""
    post2_content = posts_split[2] if len(posts_split) > 2 else ""
    # Find corn post (might not always be 18th after refactor)
    corn_post_content = ""
    cocktail_post_content = ""
    for i, content in enumerate(posts_split[1:], 1):
        if "Taiwanese corn steaming with black pebbles" in content:
            corn_post_content = content
            logger.info(f"Found corn content in Post {i}")
        if "ISLAND OLD FASHIONED" in content:
            cocktail_post_content = content
            logger.info(f"Found Island Old Fashioned content in Post {i}")

    # Content-specific assertions for key posts
    assert "Try this full body workout for 30mins" in post1_content, (
        "Missing workout content in Post 1"
    )
    assert "Fun fact about me, one of my absolute favorite shows is" in post2_content, (
        "Missing chef content in Post 2"
    )
    assert "Taiwanese corn steaming with black pebbles" in corn_post_content, (
        "Missing Taiwanese corn content"
    )
    assert "ISLAND OLD FASHIONED" in cocktail_post_content, "Missing cocktail recipe content"

    # Check for metadata
    assert re.search(r"\*\*\d+\.?\d*[KM]?\*\* likes/views", markdown), "Missing engagement counts"
    assert "**596** likes/views" in post2_content, "Missing specific engagement count from post 2"

    # Check hashtag extraction (loosened)
    assert "#workout" in post1_content and "#workoutmotivation" in post1_content, (
        "Missing workout hashtags in Post 1"
    )
    assert (
        "#cocktails" in post2_content
        and "#ramen" in post2_content
        and "#savorycocktails" in post2_content
    ), "Missing key cocktail/ramen hashtags in Post 2"
    assert "#corn" in corn_post_content and "#streetfood" in corn_post_content, (
        "Missing key corn hashtags"
    )
    assert "#cocktails" in cocktail_post_content and "#rumcocktails" in cocktail_post_content, (
        "Missing key old fashioned hashtags"
    )

    # Check image handling
    assert "![Image](https://instagram" in markdown, "Missing image links"
    assert len(re.findall(r"!\[Image\]", markdown)) > 10, "Not enough image references found"

    # Make sure posts are properly separated (already checked post_split length)

    # Check specific URLs included for images (partial match to avoid URL issues)
    assert "instagram.fsig5-1.fna.fbcdn.net" in markdown, "Missing expected image domain"

    # Check for specific location markers
    assert "Location : 寧夏夜市" in corn_post_content, (
        "Missing night market location info in corn post"
    )

    logger.info(
        f"✅ Instagram explore conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else ''}"
    )
