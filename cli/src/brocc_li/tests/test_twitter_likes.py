"""Test suite for the Twitter likes parser."""

from pathlib import Path

import pytest

# Assuming the parser exists here, adjust if needed
from brocc_li.parsers.twitter_likes import twitter_likes_html_to_md
from brocc_li.utils.logger import logger

DEBUG = True


@pytest.fixture
def x_likes_html(fixtures_dir: Path) -> str:
    """Load the sample X likes HTML fixture."""
    fixture_name = "_x-likes.html"
    fixture_path = fixtures_dir / fixture_name
    assert fixture_path.exists(), f"Fixture {fixture_name} not found at {fixture_path}"
    try:
        with open(fixture_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        pytest.fail(f"Fixture file not found at {fixture_path}")


@pytest.fixture
def fixtures_dir() -> Path:
    """Get the path to the fixtures directory."""
    # Assumes the tests directory is structured correctly relative to this file
    return Path(__file__).parent / "html_fixtures"


def test_parse_twitter_likes_to_md(x_likes_html: str):
    """Basic test for parsing Twitter likes to Markdown."""
    if DEBUG:
        logger.debug(f"--- Input HTML Length: {len(x_likes_html)} ---")
        # Optional: print a snippet if needed
        # logger.debug(f"HTML Snippet:\n{x_likes_html[:500]}...")

    markdown_output = twitter_likes_html_to_md(x_likes_html, debug=DEBUG)

    if DEBUG:
        print("\n--- START MARKDOWN OUTPUT ---")
        print(markdown_output)
        print("--- END MARKDOWN OUTPUT ---\n")

    # Basic assertion for now
    assert markdown_output is not None, "Markdown conversion returned None"
    assert isinstance(markdown_output, str), "Output is not a string"
    assert "Error converting" not in markdown_output, f"Conversion error: {markdown_output}"

    # --- Assertions for Tweet Content & Format (similar to home feed test) ---
    # Check for page title
    assert "# ben g" in markdown_output, "Missing expected page title '# ben g'"

    # Check for specific usernames and handles from the liked tweets
    assert "Drishan Arora" in markdown_output, "Missing username 'Drishan Arora'"
    assert "@drishanarora" in markdown_output, "Missing handle '@drishanarora'"
    assert "ben g" in markdown_output, "Missing username 'ben g'"
    assert "@0thernet" in markdown_output, "Missing handle '@0thernet'"
    assert "xjdr" in markdown_output, "Missing username 'xjdr'"
    assert "@_xjdr" in markdown_output, "Missing handle '@_xjdr'"
    assert "The Bulwark" in markdown_output, "Missing username 'The Bulwark'"
    assert "@BulwarkOnline" in markdown_output, "Missing handle '@BulwarkOnline'"

    # Check for tweet content snippets
    assert "general superintelligence" in markdown_output, "Missing Drishan's tweet content snippet"
    assert "desk has been migrated" in markdown_output, "Missing Ben's tweet content snippet"
    assert "programming with AI is significantly" in markdown_output, (
        "Missing xjdr's tweet content snippet"
    )
    assert "Heard and McDonald Islands" in markdown_output, "Missing Bulwark tweet content snippet"

    # Check for media attachments (general image/video format)
    assert "![Image]" in markdown_output or "![Timeline:" in markdown_output, (
        "Missing expected media format"
    )

    # Check for engagement metrics format
    assert "💬" in markdown_output, "Missing replies emoji"
    assert "⟲" in markdown_output, "Missing retweets emoji"
    assert "❤️" in markdown_output, "Missing likes emoji"
    assert "👁️" in markdown_output, "Missing views emoji"

    # Check header formatting
    assert "### " in markdown_output, "Missing H3 headers for tweets"

    # We can add more specific assertions later as the implementation progresses
    logger.info(f"✅ Twitter likes conversion test passed. Markdown length: {len(markdown_output)}")
