import pytest

from brocc_li.parsers.twitter_profile_followers import twitter_followers_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = False
FIXTURE_NAME = "_x-profile-followers.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")

    markdown = twitter_followers_html_to_md(html, debug=debug)

    if debug:
        print("\n--- START TWITTER FOLLOWERS MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END TWITTER FOLLOWERS MARKDOWN OUTPUT ---\n")

    # Basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error converting" not in markdown, f"Conversion failed: {markdown}"
    assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"

    # Test specific user profiles are present
    assert "[Luis](https://x.com/luis30843964) (@luis30843964)" in markdown, "Missing Luis profile"
    assert "[giacomo](https://x.com/giacomo_ran) (@giacomo_ran)" in markdown, (
        "Missing giacomo profile"
    )
    assert "[F. B.](https://x.com/FB84648795) (@FB84648795)" in markdown, "Missing F. B. profile"

    # Test bio extraction for users with known bios
    assert "what enlightens me" in markdown, "Missing Luis's bio"
    assert "flashcards app →http://rember.com" in markdown, "Missing giacomo's bio"
    assert "Web3 developer and memecoin trader" in markdown, "Missing Ata's bio"

    # Test users without bios are formatted correctly
    # These users should have their name/handle but no additional text follows until the next header
    no_bio_users = [
        ("F. B.", "FB84648795"),
        ("zzzijunnn", "zzzzijunnn"),
        ("mustafa", "zagor531453"),
    ]

    for name, handle in no_bio_users:
        user_section = f"### [{name}](https://x.com/{handle}) (@{handle})"
        # Find the user's section and verify no extra text follows until the next header
        user_idx = markdown.find(user_section)
        assert user_idx != -1, f"Missing user section for {name}"
        next_header = markdown.find("###", user_idx + len(user_section))
        if next_header == -1:
            next_header = len(markdown)
        section_text = markdown[user_idx + len(user_section) : next_header].strip()
        assert section_text == "", f"Unexpected bio text for {name}: {section_text}"

    # Test special character handling
    assert "[محمد | Mohammad]" in markdown, "Missing Arabic name"
    assert "[Jay₿ee]" in markdown, "Missing Bitcoin symbol in name"
    assert "(@__jaybee1)" in markdown, "Missing double underscore handle"

    # Test link formatting
    assert "](https://x.com/" in markdown, "Missing proper URL format"
    assert "https://x.com/FB84648795" in markdown, "Missing numeric handle URL"

    # Verify total number of profiles
    header_count = markdown.count("### [")
    assert header_count == 44, f"Expected 44 profiles, found {header_count}"

    logger.info(
        f"✅ Twitter followers conversion test passed for {FIXTURE_NAME}. "
        f"Markdown length: {len(markdown)}. {'Output printed above.' if debug else ''}"
    )
