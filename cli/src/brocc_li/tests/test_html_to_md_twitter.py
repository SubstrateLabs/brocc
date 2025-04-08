from pathlib import Path

import pytest

# Import the Element base class to check types
from unstructured.partition.html import partition_html

from brocc_li.html_to_md.twitter import convert_twitter_feed_html_to_md
from brocc_li.utils.logger import logger


@pytest.fixture
def fixtures_dir() -> Path:
    """Get the path to the fixtures directory."""
    # Assumes the tests directory is structured like the existing test_html_to_md.py
    return Path(__file__).parent.parent / "tests" / "html_fixtures"


def test_x_home(fixtures_dir: Path):
    """Test unstructured conversion against the _x-home.html fixture."""
    fixture_name = "_x-home.html"
    fixture_path = fixtures_dir / fixture_name
    slug = fixture_name.removeprefix("_").removesuffix(".html")

    logger.info(f"Testing unstructured conversion with fixture: {fixture_name}")

    assert fixture_path.exists(), f"Fixture {fixture_name} not found at {fixture_path}"

    with open(fixture_path, encoding="utf-8") as f:
        html = f.read()

    logger.info(f"  HTML size: {len(html)} bytes for {fixture_name}")

    # Partition the HTML
    try:
        elements = partition_html(text=html)
        logger.info(f"Found {len(elements)} elements from unstructured partitioning.")
    except Exception as e:
        logger.error(f"partition_html failed for {fixture_name}: {e}", exc_info=True)
        pytest.fail(f"partition_html failed: {e}")

    # Log the types and metadata of ALL elements found
    element_info = []
    for i, el in enumerate(elements):
        metadata_dict = el.metadata.to_dict() if hasattr(el, "metadata") else {}
        element_info.append(f"Element [{i}] Type: {type(el).__name__}, Metadata: {metadata_dict}")
    logger.info("\n".join(element_info))

    # Convert using the unstructured method (our custom formatting)
    markdown = convert_twitter_feed_html_to_md(html, url=slug)

    # Basic assertions
    assert markdown is not None, f"Unstructured conversion returned None for {fixture_name}"
    assert isinstance(markdown, str), (
        f"Unstructured conversion did not return a string for {fixture_name}"
    )
    assert "Error converting" not in markdown, (
        f"Unstructured conversion failed for {fixture_name}: {markdown}"
    )
    assert len(markdown.strip()) > 0, (
        f"Unstructured conversion resulted in empty markdown for {fixture_name}"
    )

    # --- Assertions for Content Presence ---
    # Check for section headers
    assert "## Your Home Timeline" in markdown, "Missing Home Timeline header"
    assert "## Trending now" in markdown, "Missing Trending now header"

    # Check for specific tweet headers (name, handle, timestamp)
    assert "### tiff [@bytheophana](/bytheophana) 6m" in markdown, "Missing tiff tweet header"
    assert "### Danielle Fong  [@DanielleFong](/DanielleFong) 16h" in markdown, (
        "Missing Danielle Fong tweet header"
    )
    assert "### Jai Malik [@Jai__Malik](/Jai__Malik) 1h" in markdown, (
        "Missing Jai Malik tweet header"
    )

    # Check for fragments of tweet content
    assert "large announcement dropping tomorrow" in markdown, "Missing tiff tweet content fragment"
    assert "ran a hot plasma experiment at [@lightcellenergy](/lightcellenergy)" in markdown, (
        "Missing Danielle Fong tweet content fragment"
    )
    assert "Advanced Manufacturing Company of America" in markdown, (
        "Missing Jai Malik tweet content fragment"
    )

    # Check for trending section content (example)
    assert "Predator: Killer of Killers" in markdown, "Missing example trending content"

    # --- Assertions for Content Absence ---
    # Check that Who to Follow section is gone
    assert "Who to follow" not in markdown, "'Who to follow' section header present"
    assert "Nuño Sempere" not in markdown, "'Nuño Sempere' text present"
    assert "@NunoSempere" not in markdown, "'@NunoSempere' handle present"
    assert "Click to Follow" not in markdown, "'Click to Follow' text present"

    # Check that separators are gone
    assert "\n---\n" not in markdown, "Markdown triple dash separator present"

    # Check filtered noise
    assert "/analytics" not in markdown, "Analytics links present"
    assert "abs-0.twimg.com/emoji/v2/svg" not in markdown, "Emoji image URLs present"
    assert "_normal.jpg" not in markdown, "_normal profile image URLs present"
    assert " posts" not in markdown, "'X posts' text present"
    assert "Explore" not in markdown, "'Explore' UI text present"
    assert "Beta" not in markdown, "'Beta' UI text present"
    assert "Quote" not in markdown, "'Quote' boilerplate text present"
    assert "Live on X" not in markdown, "'Live on X' boilerplate text present"

    # Note: Absence of the final "Show more" is implicitly tested by checking that the
    # "Who to follow" section content (like Nuño Sempere) is not present, as the filter
    # for "Show more" related to /i/connect_people was confirmed working in the logs.

    logger.info(
        f"✅ Unstructured conversion test passed for {fixture_name}. Markdown length: {len(markdown)}"
    )
