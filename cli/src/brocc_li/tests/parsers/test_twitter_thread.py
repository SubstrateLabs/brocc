import pytest

from brocc_li.parsers.twitter_thread import twitter_thread_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_x-thread.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    markdown = twitter_thread_html_to_md(html, debug=debug)

    if debug:
        print("\n--- START TWITTER THREAD MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END TWITTER THREAD MARKDOWN OUTPUT ---\n")

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

    logger.info(
        f"✅ Twitter thread conversion test passed for {FIXTURE_NAME}. "
        f"Markdown length: {len(markdown)}. {'Output printed above.' if debug else ''}"
    )
