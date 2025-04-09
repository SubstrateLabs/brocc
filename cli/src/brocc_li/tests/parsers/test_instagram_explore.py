import re

import pytest

from brocc_li.parsers.instagram_explore import instagram_explore_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_instagram-explore.html"
FIXTURE_NAME_SEARCH = "_instagram-explore-search.html"


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


def test_parse_search(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME_SEARCH)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME_SEARCH} not found")

    # Convert using unstructured-based parser, pass debug parameter
    markdown = instagram_explore_html_to_md(html, debug=debug)

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

    # Structure assertions
    assert "# Instagram Explore" in markdown, "Missing main header"
    assert "## Posts" in markdown, "Missing posts section"
    assert "### Post 1" in markdown, "Missing Post 1 heading"

    # Split markdown into posts for targeted assertions
    posts_split = markdown.split("### Post ")
    assert len(posts_split) >= 15, "Expected at least 15 posts after split"

    # Find specific ramen posts
    spicy_miso_post = ""
    shoyu_ramen_post = ""
    all_food_post = ""

    for i, content in enumerate(posts_split[1:], 1):
        if "Spicy Miso Ramen!" in content:
            spicy_miso_post = content
            logger.info(f"Found Spicy Miso Ramen content in Post {i}")
        if "shoyu ramen 醤油ラーメン recipe" in content:
            shoyu_ramen_post = content
            logger.info(f"Found Shoyu Ramen content in Post {i}")
        if "All the food (almost) you need to try in Japan" in content:
            all_food_post = content
            logger.info(f"Found Japan food guide content in Post {i}")

    # Content-specific assertions
    assert "Spicy Miso Ramen!" in spicy_miso_post, "Missing Spicy Miso Ramen content"
    assert (
        "This shoyu ramen 醤油ラーメン recipe comes from Master Ueda of the famous Tokyo ramen shop"
        in shoyu_ramen_post
    ), "Missing Shoyu ramen content"
    assert "All the food (almost) you need to try in Japan" in all_food_post, (
        "Missing Japan food guide content"
    )

    # Check for specific hashtags
    assert "#ramen" in markdown, "Missing #ramen hashtag"
    assert "#japanesecooking" in markdown, "Missing #japanesecooking hashtag"
    assert "#soupseason" in markdown, "Missing #soupseason hashtag"

    # Check metadata
    assert "**2** likes/views" in markdown, "Missing specific engagement count"

    # Check image handling
    assert "![Image](https://instagram" in markdown, "Missing image links"
    assert len(re.findall(r"!\[Image\]", markdown)) > 10, "Not enough image references found"

    logger.info(
        f"✅ Instagram explore search conversion test ran for {FIXTURE_NAME_SEARCH}. "
        f"{'Output printed above.' if debug else ''}"
    )
