from pathlib import Path

import pytest

from brocc_li.parsers.twitter_home import twitter_feed_html_to_md
from brocc_li.utils.logger import logger

DEBUG = False


@pytest.fixture
def fixtures_dir() -> Path:
    """Get the path to the fixtures directory."""
    # Assumes the tests directory is structured like the existing test_html_to_md.py
    return Path(__file__).parent.parent / "tests" / "html_fixtures"


def test_parse(fixtures_dir: Path):
    fixture_name = "_x-home.html"
    fixture_path = fixtures_dir / fixture_name
    assert fixture_path.exists(), f"Fixture {fixture_name} not found at {fixture_path}"
    with open(fixture_path, encoding="utf-8") as f:
        html = f.read()

    # Convert using BeautifulSoup-based parser
    markdown = twitter_feed_html_to_md(html)

    # Print markdown if DEBUG flag is enabled
    if DEBUG:
        print("\n--- START MARKDOWN ---")
        print(markdown)
        print("--- END MARKDOWN ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error converting" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"

    # --- Assertions for Tweet Content & Format ---
    # Check for specific usernames and handles
    assert "@bytheophana" in markdown, "Missing @bytheophana handle"
    assert "Danielle Fong" in markdown, "Missing Danielle Fong username"
    assert "@DanielleFong" in markdown, "Missing @DanielleFong handle"
    assert "Jai Malik" in markdown, "Missing Jai Malik username"
    assert "@Jai__Malik" in markdown, "Missing @Jai__Malik handle"

    # Check for tweet content snippets
    assert "large announcement dropping tomorrow" in markdown, "Missing tiff's tweet content"
    assert "ran a hot plasma experiment" in markdown, "Missing Danielle's tweet content"
    assert "Advanced Manufacturing Company of America" in markdown, "Missing Jai's tweet content"

    # Check for media attachments
    assert "![Video Thumbnail](" in markdown or "![Embedded video](" in markdown, (
        "Missing video attachment"
    )
    assert "![" in markdown, "Missing image attachment"

    # Check for engagement metrics format
    assert "💬" in markdown, "Missing replies emoji in engagement metrics"
    assert "⟲" in markdown, "Missing retweets emoji in engagement metrics"
    assert "❤️" in markdown, "Missing likes emoji in engagement metrics"

    # Check header formatting
    assert "### " in markdown, "Missing H3 headers for tweets"

    logger.info(
        f"✅ Twitter feed conversion test passed for {fixture_name}. Markdown length: {len(markdown)}"
    )
