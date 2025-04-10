import re

import pytest

from brocc_li.parsers.linkedin_feed_v2 import linkedin_feed_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG_1 = False
FIXTURE_1 = "_linkedin-feed-3.html"
DEBUG_2 = False
FIXTURE_2 = "_linkedin-company-feed.html"
DEBUG_3 = False
FIXTURE_3 = "_linkedin-person-feed.html"


def test_parse_1(debug: bool = DEBUG_1):
    """Tests the basic parsing of the LinkedIn feed v2 HTML."""
    try:
        html_content = get_fixture(FIXTURE_1)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_1} not found in cli/src/brocc_li/tests/html_fixtures/")

    # Pass the debug flag to the parser
    markdown_output = linkedin_feed_html_to_md(html_content, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START LINKEDIN V2 MARKDOWN OUTPUT (PLACEHOLDERS) ---")
        if markdown_output:
            print(markdown_output)
        else:
            print("(No markdown output generated)")
        print("--- END LINKEDIN V2 MARKDOWN OUTPUT ---\n")

    # Basic assertions for the initial parser implementation
    assert markdown_output is not None, "Parser returned None"
    assert isinstance(markdown_output, str), "Parser did not return a string"
    assert "Error converting" not in markdown_output, (
        f"Parser failed with an error: {markdown_output[:500]}..."
    )

    # Check if we got *any* output
    assert len(markdown_output.strip()) > 0, (
        "Parser resulted in empty markdown. Check selector and logs."
    )

    # --- Specific content assertions ---

    # Check for specific authors we know should be in the feed
    expected_authors = ["Steffen Holm", "Together AI", "Dustin Beaudoin", "Yoko Li"]
    for author in expected_authors:
        assert author in markdown_output, f"Missing expected author: {author}"

    # Check for "None" authors - should not have any after our filtering
    assert "### None" not in markdown_output, "Found 'None' author that should have been filtered"

    # Check for metrics formatting
    assert "❤️" in markdown_output, "Missing heart emoji for likes/reactions"
    assert "💬" in markdown_output, "Missing speech bubble emoji for comments"
    assert "🔄" in markdown_output, "Missing refresh emoji for reposts"

    # Check for specific reaction counts that should be present
    reaction_patterns = [r"❤️ 5 reactions", r"❤️ 126 reactions", r"❤️ 7 reactions"]
    for pattern in reaction_patterns:
        assert re.search(pattern, markdown_output), f"Missing expected reaction pattern: {pattern}"

    # Check for comment extractions
    assert "**Comments" in markdown_output, "Missing comments section"
    assert "**Ethan Yeh**" in markdown_output, "Missing specific commenter 'Ethan Yeh'"
    assert "**Orlando Kalossakas**" in markdown_output, (
        "Missing specific commenter 'Orlando Kalossakas'"
    )

    # Check for proper formatting of tagged content
    # In the example output, we had formatting issues with Stripe post:
    # "Shopify, Woo, and Monzo Bank" should be on same line, not broken by newlines
    if "Neetika Bansal" in markdown_output:
        # Check the entire markdown for Shopify close to Neetika Bansal
        # Instead of just looking at the first paragraph
        stripe_post_exists = "Neetika Bansal" in markdown_output and "Shopify" in markdown_output
        assert stripe_post_exists, "Missing expected Stripe post with Shopify reference"

        # Get the specific paragraph containing Shopify if it exists
        shopify_paragraph = None
        for para in markdown_output.split("\n\n"):
            if "Shopify" in para and "Woo" in para and "Monzo Bank" in para:
                shopify_paragraph = para
                break

        if shopify_paragraph:
            # Check that we don't have problematic newlines between Shopify and Monzo
            assert "Shopify\n,\nWoo" not in shopify_paragraph, (
                "Found improper newline formatting in Stripe post"
            )

    # Check for media content
    assert "![" in markdown_output, "No images found in the output"
    assert "](" in markdown_output, "No links found in the output"

    logger.info(
        f"✅ LinkedIn feed v2 parser test ran for {FIXTURE_1}. "
        f"Markdown length: {len(markdown_output)}. "
        f"{'Output printed above.' if debug else 'Run with DEBUG=True to see output.'}"
    )


def test_parse_2(debug: bool = DEBUG_2):
    """Tests parsing LinkedIn company feed HTML - outputs markdown for iteration."""
    try:
        html_content = get_fixture(FIXTURE_2)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_2} not found in cli/src/brocc_li/tests/html_fixtures/")

    # Parse the HTML content
    markdown_output = linkedin_feed_html_to_md(html_content, debug=debug)

    # Print the output for inspection
    if debug:
        print("\n--- START LINKEDIN COMPANY FEED MARKDOWN OUTPUT ---")
        if markdown_output:
            print(markdown_output)
        else:
            print("(No markdown output generated)")
        print("--- END LINKEDIN COMPANY FEED MARKDOWN OUTPUT ---\n")

    # Basic validity check
    assert markdown_output is not None, "Parser returned None"
    assert isinstance(markdown_output, str), "Parser did not return a string"
    assert "Error converting" not in markdown_output, (
        f"Parser failed with an error: {markdown_output[:500]}..."
    )

    # Company specific assertions
    assert "### Lorikeet" in markdown_output, "Missing company name Lorikeet"
    assert "2,928 followers" in markdown_output, "Missing follower count"

    # Check for timestamps - company posts from different time periods
    timestamps = ["17h •", "2d •", "3w •", "4w •"]
    for timestamp in timestamps:
        assert timestamp in markdown_output, f"Missing timestamp: {timestamp}"

    # Check for specific content snippets
    assert "helping our customers solve gnarly problems" in markdown_output, (
        "Missing first post content"
    )
    assert "You miss 100% of shots you don't take" in markdown_output, "Missing second post content"
    assert "The easiest thing to do in the world" in markdown_output, "Missing third post content"

    # Check for engagement metrics
    reaction_patterns = [r"❤️ 18 reactions", r"❤️ 9 reactions", r"❤️ 28 reactions", r"❤️ 17 reactions"]
    for pattern in reaction_patterns:
        assert re.search(pattern, markdown_output), f"Missing expected reaction pattern: {pattern}"

    # Check for media content
    assert "![graphical user interface, text, application]" in markdown_output, (
        "Missing image in second post"
    )

    # Check for post structure elements
    assert "[Profile](https://www.linkedin.com/company/lorikeetcx/posts)" in markdown_output, (
        "Missing profile link"
    )
    assert "[Post](https://www.linkedin.com/feed/update/" in markdown_output, "Missing post link"

    logger.info(
        f"✅ LinkedIn feed v2 parser test ran for {FIXTURE_2}. "
        f"Markdown length: {len(markdown_output) if markdown_output else 0}."
    )


def test_parse_3(debug: bool = DEBUG_3):
    """Tests parsing LinkedIn person feed HTML - outputs markdown for iteration."""
    try:
        html_content = get_fixture(FIXTURE_3)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_3} not found in cli/src/brocc_li/tests/html_fixtures/")

    # Parse the HTML content
    markdown_output = linkedin_feed_html_to_md(html_content, debug=debug)

    # Print the output for inspection
    if debug:
        print("\n--- START LINKEDIN PERSON FEED MARKDOWN OUTPUT ---")
        if markdown_output:
            print(markdown_output)
        else:
            print("(No markdown output generated)")
        print("--- END LINKEDIN PERSON FEED MARKDOWN OUTPUT ---\n")

    # Basic validity check
    assert markdown_output is not None, "Parser returned None"
    assert isinstance(markdown_output, str), "Parser did not return a string"
    assert "Error converting" not in markdown_output, (
        f"Parser failed with an error: {markdown_output[:500]}..."
    )

    # Person specific assertions
    assert "### Steve Hind" in markdown_output, "Missing person name: Steve Hind"
    assert "Co-founder at Lorikeet" in markdown_output, "Missing person title/subtitle"

    # Check for timestamps - person posts from different time periods
    timestamps = ["1d •", "2d •", "1w •", "2w •", "3w •", "4w •"]
    for timestamp in timestamps:
        assert timestamp in markdown_output, f"Missing timestamp: {timestamp}"

    # Check for specific content snippets
    assert "When Jamie Hall and I started Lorikeet" in markdown_output, "Missing first post content"
    assert "One of the biggest threats to successful AI rollouts" in markdown_output, (
        "Missing second post content"
    )
    assert 'My number one "WTF ARE THEY DOING" product thing' in markdown_output, (
        "Missing third post content"
    )

    # Check for engagement metrics
    reaction_patterns = [r"❤️ 38 reactions", r"❤️ 42 reactions", r"❤️ 28 reactions", r"❤️ 84 reactions"]
    for pattern in reaction_patterns:
        assert re.search(pattern, markdown_output), f"Missing expected reaction pattern: {pattern}"

    # Check for comments
    comment_patterns = [
        r"💬 2 comments",
        r"💬 14 comments",
        r"💬 3 comments",
        r"💬 4 comments",
        r"💬 5 comments",
    ]
    for pattern in comment_patterns:
        assert re.search(pattern, markdown_output), f"Missing expected comment pattern: {pattern}"

    # Check for media content
    assert "![graphical user interface, text, application]" in markdown_output, (
        "Missing image description"
    )

    # Check for profile and post links
    assert "[Profile](https://www.linkedin.com/in/shind" in markdown_output, "Missing profile link"
    assert "[Post](https://www.linkedin.com/feed/update/" in markdown_output, "Missing post link"

    logger.info(
        f"✅ LinkedIn feed v2 parser test ran for {FIXTURE_3}. "
        f"Markdown length: {len(markdown_output) if markdown_output else 0}."
    )
