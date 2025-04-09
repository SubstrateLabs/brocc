import pytest

from brocc_li.parsers.bsky_followers import bsky_followers_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

# Enable debug logging FOR THE TEST to see parser logs
DEBUG = False
FIXTURE_NAME = "_bsky-followers.html"


def test_parse_bsky_followers(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found")
    except Exception as e:
        pytest.fail(f"Error loading fixture {FIXTURE_NAME}: {e}")

    markdown = bsky_followers_html_to_md(html, debug=debug)
    if debug:
        print("\n\n--- START BLUESKY FOLLOWERS MARKDOWN OUTPUT ---")
        if markdown is not None:
            print(markdown)
            logger.info(f"Markdown generated. Length: {len(markdown)}")
        else:
            print("!!! MARKDOWN CONVERSION RETURNED NONE !!!")
            logger.warning("Markdown conversion returned None.")
        print("--- END BLUESKY FOLLOWERS MARKDOWN OUTPUT ---\n")

    # Real assertions that validate specific content
    assert markdown is not None, "Parser returned None instead of markdown"

    # Check total number of profiles by counting headers
    profile_count = markdown.count("### [")
    assert profile_count == 14, f"Expected 14 profiles, found {profile_count}"

    # Check specific profiles exist in the output
    expected_profiles = [
        "JAMs on Steam",
        "Siege_Almighty",
        "Women of Street Fighter",
        "𝙥𝙖𝙮𝙣𝙚𝙭𝙠𝙞𝙡𝙡𝙚𝙧",
        "Chud Grassley",
    ]

    for profile in expected_profiles:
        assert profile in markdown, f"Expected profile '{profile}' not found in output"

    # Check that handles are properly extracted and formatted
    expected_handles = [
        "(@blacksails.com)",
        "(@siegealmighty.bsky.social)",
        "(@streetfighterwomen.bsky.social)",
        "(@dff123.bsky.social)",
    ]

    for handle in expected_handles:
        assert handle in markdown, f"Expected handle '{handle}' not found in output"

    # Check that links are properly formed
    expected_links = [
        "https://bsky.app/profile/blacksails.com",
        "https://bsky.app/profile/principalengineer.com",
        "https://bsky.app/profile/rangoonn.bsky.social",
    ]

    for link in expected_links:
        assert link in markdown, f"Expected link '{link}' not found in output"

    # Check that bios are correctly extracted
    expected_bio_snippets = [
        "Very tired dude who likes fighting games and pokemon",
        "Lead FGC Player Development and Scout for Pulse Esports",
        "Pictures and Videos dedicated to the strong ladies of the Street Fighter",
        "Avid ADHD proponent. Lover of dopamine",
    ]

    for bio in expected_bio_snippets:
        assert bio in markdown, f"Expected bio snippet '{bio}' not found in output"

    # Check special cases are handled correctly
    # Unicode profile name renders correctly
    assert "𝙥𝙖𝙮𝙣𝙚𝙭𝙠𝙞𝙡𝙡𝙚𝙧 ᴬᵏᵃ ᴶᵒˢʰ" in markdown, "Unicode in profile name not preserved"

    # Profile with emoji renders correctly
    assert "STAY FADED 🍃" in markdown, "Emoji in profile name not preserved"

    # Profile with no bio still renders correctly (empty line after header)
    assert "### [Trevor](https://bsky.app/profile/trevorboeckmann.bsky.social)" in markdown, (
        "Profile with no bio not rendered correctly"
    )

    logger.info(
        f"✅ Bluesky followers conversion test executed for {FIXTURE_NAME}. All assertions passed."
    )
