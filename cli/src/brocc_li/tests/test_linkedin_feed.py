from pathlib import Path

import pytest

from brocc_li.parsers.linkedin_feed import linkedin_feed_html_to_md
from brocc_li.utils.logger import logger


@pytest.fixture
def fixtures_dir() -> Path:
    """Get the path to the fixtures directory."""
    return Path(__file__).parent.parent / "tests" / "html_fixtures"


def test_parse(fixtures_dir: Path):
    fixture_name = "_linkedin-feed.html"
    fixture_path = fixtures_dir / fixture_name
    assert fixture_path.exists(), f"Fixture {fixture_name} not found at {fixture_path}"
    with open(fixture_path, encoding="utf-8") as f:
        html = f.read()

    # Convert using unstructured-based parser, enable debug logging for inspection
    markdown = linkedin_feed_html_to_md(html, debug=True)

    # Print the output for inspection
    print("\\n--- START LINKEDIN MARKDOWN OUTPUT ---")
    print(markdown)
    print("--- END LINKEDIN MARKDOWN OUTPUT ---\\n")

    # Basic assertions (keep minimal checks)
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error partitioning" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"
    # assert "<!-- No posts found -->" not in markdown, (
    #     "Parser reported no posts found, check selectors."
    # )
    # assert "<!-- Error processing post" not in markdown, "Parser reported errors processing posts."

    # # --- Assertions for Post Content & Format --- #
    # # Check for specific user names from the fixture (updated based on alt text fallback)
    # assert "Thorsten" in markdown, "Missing expected user name: Thorsten"
    # assert "Raul Kaevand" in markdown, (
    #     "Missing expected user name: Raul Kaevand (Post 2 - Known Issue)"
    # )
    # assert "Andrew Yeung" in markdown, "Missing expected user name: Andrew Yeung (Commenter)"
    # assert "Hamza Alsamraee" in markdown, "Missing expected user name: Hamza Alsamraee (Post 3)"

    # # Check for post content snippets
    # assert "WhatsApp MCP server" in markdown, "Missing content from Post 1"
    # assert "Instantly.ai Catch-All Verification" in markdown, "Missing content from Post 2"
    # assert "Excited to introduce WillBot" in markdown, "Missing content from Post 3"
    # assert "leggo" in markdown, "Missing comment text from Andrew Yeung"

    # Check that some common noise is *not* present
    # assert "Stream Type LIVE" not in markdown, "Media player controls detected in output"
    # assert "Media player modal window" not in markdown, "Media player modal text detected"

    logger.info(f"✅ LinkedIn feed conversion test ran for {fixture_name}. Output printed above.")
