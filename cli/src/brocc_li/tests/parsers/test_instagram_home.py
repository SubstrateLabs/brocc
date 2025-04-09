import pytest

from brocc_li.parsers.instagram_home import instagram_home_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_instagram-home.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    # Convert using unstructured-based parser, pass debug parameter
    markdown = instagram_home_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START INSTAGRAM HOME MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END INSTAGRAM HOME MARKDOWN OUTPUT ---\n")

    # Basic assertions (keep minimal checks)
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"
    assert "<!-- No elements" not in markdown, "Parser reported no elements found."

    # Feed item assertions
    assert "### Post by robertkarpay" in markdown, "Missing Robert Karpay's post"
    assert "performances coming up" in markdown, "Missing Robert Karpay's post content"
    assert "*48 likes*" in markdown, "Missing likes count for Robert Karpay's post"

    assert "### Post by julianconnor_" in markdown, "Missing Julian Connor's post"
    assert "moments from everywhere this year thus far" in markdown, (
        "Missing Julian Connor's post content"
    )
    assert "*130 likes*" in markdown, "Missing likes count for Julian Connor's post"

    assert "### Post by slexaxton" in markdown, "Missing Alex Sexton's post"
    assert "🐈‍⬛" in markdown, "Missing Alex Sexton's post content"
    assert "*13 likes*" in markdown, "Missing likes count for Alex Sexton's post"

    # Verify post ordering (most recent first)
    posts = markdown.split("\n\n\n")
    assert len(posts) >= 3, "Expected at least 3 posts"
    assert "robertkarpay" in posts[0], "Robert Karpay's post should be first"
    assert "julianconnor_" in posts[1], "Julian Connor's post should be second"
    assert "slexaxton" in posts[2], "Alex Sexton's post should be third"

    logger.info(
        f"✅ Instagram home conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else ''}"
    )
