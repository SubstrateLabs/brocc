"""Test suite for the Twitter likes parser."""

import pytest

# Assuming the parser exists here, adjust if needed
from brocc_li.parsers.twitter_likes import parse_twitter_likes

DEBUG = True


@pytest.fixture
def x_likes_html() -> str:
    """Load the sample X likes HTML fixture."""
    # Corrected path based on previous error message
    fixture_path = "cli/src/brocc_li/tests/html_fixtures/_x-likes.html"
    # Ensure the file exists or handle FileNotFoundError appropriately
    try:
        with open(fixture_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        pytest.fail(f"Fixture file not found at {fixture_path}")


def test_parse_twitter_likes(x_likes_html: str):
    """Basic test for parsing Twitter likes."""
    if DEBUG:
        print("\n--- Raw HTML Fixture ---")
        print(x_likes_html[:500] + "...")  # Print first 500 chars for brevity
        print("--- End Raw HTML ---")

    # Placeholder for actual parsing logic - assume it returns something
    # You'll need to implement parse_twitter_likes in the respective module
    parsed_data = parse_twitter_likes(x_likes_html)

    if DEBUG:
        print("\n--- Parsed Data ---")
        # TODO: Implement actual printing or meaningful checks
        print(parsed_data)
        print("--- End Parsed Data ---")

    # Basic assertion for now
    assert parsed_data is not None
    # TODO: Add more specific assertions once parsing logic is implemented
    # e.g., assert len(parsed_data) > 0
    # assert "expected_field" in parsed_data[0]
