from pathlib import Path

import pytest

from brocc_li.parsers import twitter_thread
from brocc_li.parsers.twitter_thread import twitter_thread_html_to_md
from brocc_li.utils.logger import logger

# Set to True to print full output
DEBUG = False


@pytest.fixture
def fixtures_dir() -> Path:
    """Get the path to the fixtures directory."""
    # Assumes the tests directory is structured like the existing test_html_to_md.py
    return Path(__file__).parent.parent / "tests" / "html_fixtures"


def test_parse(fixtures_dir: Path):
    # Use the twitter thread fixture
    fixture_name = "_x-thread.html"
    fixture_path = fixtures_dir / fixture_name
    assert fixture_path.exists(), f"Fixture {fixture_name} not found at {fixture_path}"

    logger.info(f"Loading fixture: {fixture_path}")
    with open(fixture_path, encoding="utf-8") as f:
        html = f.read()
    logger.info(f"Loaded {len(html)} bytes of HTML")

    # Set debug mode in the parser to match the test's DEBUG setting
    twitter_thread.DEBUG = DEBUG

    # Convert using our parser
    logger.info("Converting HTML to markdown using twitter_thread_html_to_md")
    markdown = twitter_thread_html_to_md(html)

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error converting" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"

    # Print stats
    if markdown:
        line_count = len(markdown.split("\n"))
        tweet_count = markdown.count("###")
        logger.info(f"Stats: {len(markdown)} chars, {line_count} lines, {tweet_count} tweets")

    # --- Assertions for Tweet Content & Format ---
    # Check for specific usernames and handles
    assert "Eli Lifland" in markdown, "Missing Eli Lifland username"
    assert "@eli_lifland" in markdown, "Missing @eli_lifland handle"

    # Check for tweet content snippets
    assert "AI 2027" in markdown, "Missing discussion of AI 2027"
    assert "positive and negative" in markdown, "Missing expected content about positive/negative"
    assert "doomer agenda" in markdown, "Missing expected content about doomer agenda"

    # Check for media attachments
    assert "![Image](" in markdown, "Missing image attachment"

    # Check for engagement metrics format
    assert "💬" in markdown, "Missing replies emoji in engagement metrics"
    assert "⟲" in markdown, "Missing retweets emoji in engagement metrics"
    assert "❤️" in markdown, "Missing likes emoji in engagement metrics"
    assert "👁️" in markdown, "Missing views emoji in engagement metrics"

    # Check header formatting
    assert "### " in markdown, "Missing H3 headers for tweets"

    # Print final markdown output if DEBUG is enabled
    if DEBUG:
        print("\n\n=== TWITTER THREAD AS MARKDOWN ===\n")
        print(markdown)
        print("\n=== END MARKDOWN OUTPUT ===\n")

    logger.info(
        f"✅ Twitter thread conversion test passed for {fixture_name}. Markdown length: {len(markdown)}"
    )
