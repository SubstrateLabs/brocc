"""Test suite for the Twitter likes parser."""

import pytest

DEBUG = False


@pytest.fixture
def x_likes_html() -> str:
    """Load the sample X likes HTML fixture."""
    # Corrected path based on previous error message
    fixture_path = "src/brocc_li/tests/html_fixtures/_x-likes.html"
    # Ensure the file exists or handle FileNotFoundError appropriately
    try:
        with open(fixture_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        pytest.fail(f"Fixture file not found at {fixture_path}")


def test_twitter_likes_html_to_md(x_likes_html: str):
    """Basic test for parsing Twitter likes HTML to Markdown."""
    from brocc_li.parsers.twitter_likes import twitter_likes_html_to_md

    markdown = twitter_likes_html_to_md(x_likes_html, debug=DEBUG)

    # Basic assertion for now
    assert markdown is not None
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"
    assert "Error converting" not in markdown, f"Conversion failed: {markdown}"
    assert "###" in markdown, "Missing H3 headers for tweets"
    assert "@drishanarora" in markdown, "Missing expected handle @drishanarora"
    assert "@_xjdr" in markdown, "Missing expected handle @_xjdr"
