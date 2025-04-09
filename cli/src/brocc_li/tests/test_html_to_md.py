"""
Files in the fixtures directory prefixed with underscore (_) are automatically tested.
For example:
- _example-site.html - Will be tested by this module
- example-site.html - Will not be tested (no underscore prefix)

Running `make chrome` saves new fixtures from open Chrome tabs.
"""

import re
import time
from pathlib import Path

import pytest

import brocc_li.html_to_md
from brocc_li.html_to_md import convert_html_to_markdown, run_with_timeout
from brocc_li.playwright_fallback import BANNER_TEXT
from brocc_li.utils.logger import logger

# Set to True to enable debug logging
DEBUG = True

# Sync debug setting with the HTML-to-MD module
if DEBUG:
    # Override the html_to_md module's DEBUG setting
    import brocc_li.html_to_md

    brocc_li.html_to_md.DEBUG = DEBUG


@pytest.fixture
def fixtures_dir() -> Path:
    """Get the path to the fixtures directory."""
    return Path(__file__).parent.parent / "tests" / "html_fixtures"


def assert_valid_markdown(markdown: str, fixture_name: str):
    """Helper function to check common markdown conversion assertions."""
    # Basic sanity checks for the markdown output
    if not markdown:
        if DEBUG:
            logger.error(f"❌ {fixture_name}: Markdown output is empty")
        assert markdown, f"Markdown output for {fixture_name} should not be empty"

    if "Error converting" in markdown:
        if DEBUG:
            logger.error(f"❌ {fixture_name}: Conversion error: {markdown}")
        assert "Error converting" not in markdown, (
            f"Conversion for {fixture_name} should not produce errors"
        )

    # Get the lines and analyze document structure
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    if not lines:
        if DEBUG:
            logger.error(f"❌ {fixture_name}: Output has no non-empty lines")
        pytest.fail(f"Output for {fixture_name} has no non-empty lines")

    # Check document structure - should start with valid markdown syntax
    first_line = lines[0]
    valid_md_starters = [
        lambda s: s.startswith("#"),  # Heading
        lambda s: s.startswith("!["),  # Image
        lambda s: s.startswith("["),  # Link
        lambda s: s.startswith(">"),  # Blockquote
        lambda s: s.startswith("-") or s.startswith("*") or re.match(r"^\d+\.", s),  # List
        lambda s: s.startswith("```"),  # Code block
        lambda s: s[0].isalpha(),  # Plain text
        lambda s: s.startswith("|"),  # Table
        lambda s: re.match(r"^\d", s),  # Start with numbers (for counts, stats, etc.)
    ]

    is_valid_md_start = any(checker(first_line) for checker in valid_md_starters)
    if not is_valid_md_start and DEBUG:
        logger.error(f"❌ {fixture_name}: Invalid markdown start: '{first_line}'")
    assert is_valid_md_start, (
        f"Document for {fixture_name} should start with valid markdown syntax, got: {first_line}"
    )

    # Check for content structure - either headings, lists, links, paragraphs, or tables
    has_headings = any(line.startswith("#") for line in lines)
    has_lists = any(line.startswith(("-", "*", "1.")) for line in lines)
    has_links = any(line.startswith("[") for line in lines)
    has_tables = any(line.startswith("|") for line in lines)
    has_paragraphs = any(
        len(line) > 20 and not line.startswith(("#", "-", "*", "1.", "[", ">", "```", "|"))
        for line in lines
    )

    if not (has_headings or has_lists or has_links or has_paragraphs or has_tables):
        if DEBUG:
            logger.error(
                f"❌ {fixture_name}: No headings, lists, links, tables, or substantial paragraphs found"
            )
        pytest.fail(
            f"Output for {fixture_name} should contain either headings, lists, links, tables, or substantial paragraphs"
        )

    # Make sure the first 5 lines don't contain obvious JS/framework patterns
    js_patterns = [
        r"function\s*\(",
        r"const\s+\w+\s*=",
        r"var\s+\w+\s*=",
        r"let\s+\w+\s*=",
        r"import\s+\{",
        r"export\s+",
        r"document\.",
        r"window\.",
        r"<script",
        r"React\.",
    ]

    for i, line in enumerate(lines[:5]):
        # Skip JS pattern checks for image URLs
        if (
            "![" in line
            and "](http" in line
            and (".png" in line or ".jpg" in line or ".jpeg" in line or ".gif" in line)
        ):
            continue

        for pattern in js_patterns:
            if re.search(pattern, line):
                if DEBUG:
                    logger.error(
                        f"❌ {fixture_name}: Line {i + 1} contains JS pattern '{pattern}': {line}"
                    )
                pytest.fail(
                    f"Line {i + 1} of {fixture_name} contains JS pattern '{pattern}': {line}"
                )

    # Look for suspicious combinations of HTML and JS-specific content
    html_patterns = ["<div", "<span", "className=", "onClick=", "data-", "style="]
    for line in lines:
        html_matches = sum(1 for pattern in html_patterns if pattern.lower() in line.lower())
        if html_matches >= 2:
            if DEBUG:
                logger.error(f"❌ {fixture_name}: Line has multiple HTML/JS patterns: {line}")
            pytest.fail(f"Line has multiple HTML/JS patterns: {line}")

    # Check for overall document coherence - should have reasonable structure
    text_lines = [line for line in lines if not line.startswith(("#", ">", "-", "*", "```", "|"))]
    if text_lines and len(text_lines) >= 5:  # Only check if we have enough lines
        pass

    # Ensure banner text is not present in the output
    if BANNER_TEXT in markdown and DEBUG:
        logger.error(f"❌ {fixture_name}: Banner text found in output")
    assert BANNER_TEXT not in markdown, (
        f"Banner text should not be present in output for {fixture_name}"
    )

    if DEBUG:
        logger.info(f"✅ {fixture_name}: Passed all markdown validation checks")


def get_test_fixtures(fixtures_dir: Path):
    """Get all test fixtures (HTML files prefixed with underscore)."""
    return list(fixtures_dir.glob("_*.html"))


def get_fixture_params(fixtures_dir: Path):
    """Get parameters for pytest parametrization from fixtures."""
    fixtures = get_test_fixtures(fixtures_dir)
    return [fixture.name for fixture in fixtures]


@pytest.mark.parametrize(
    "fixture_name", get_fixture_params(Path(__file__).parent.parent / "tests" / "html_fixtures")
)
def test_fixture_conversion(fixtures_dir: Path, fixture_name: str):
    """Test conversion of a single HTML fixture."""
    fixture_path = fixtures_dir / fixture_name
    slug = fixture_name.removeprefix("_").removesuffix(".html")

    if DEBUG:
        logger.info(f"Testing fixture: {fixture_name}")

    with open(fixture_path, encoding="utf-8") as f:
        html = f.read()

    if DEBUG:
        logger.info(f"  HTML size: {len(html)} bytes")

    # Convert and validate
    markdown = convert_html_to_markdown(html, url=slug)

    # Check if conversion returned None (e.g., for PDF pages)
    if markdown is None:
        if DEBUG:
            logger.info(f"✅ {fixture_name}: Successfully returned None (expected for this type)")
        return  # Skip validation for None results

    if DEBUG:
        logger.info(f"  Markdown size: {len(markdown)} bytes")

    assert_valid_markdown(markdown, fixture_name)


def test_parser_timeout():
    """Test that parser timeout works correctly."""

    # Create a mock parser function that sleeps longer than the timeout
    def slow_parser(html: str, debug: bool = False) -> str:
        time.sleep(0.3)  # Sleep for just 0.3 seconds
        return "Parsed content"

    # Run with a very short timeout (0.1 second)
    result = run_with_timeout(slow_parser, "<html></html>", timeout=0.1, debug=False)

    # Should return None due to timeout
    assert result is None

    # Test with a longer timeout - should succeed
    result = run_with_timeout(slow_parser, "<html></html>", timeout=0.5, debug=False)

    # Should return the expected result
    assert result == "Parsed content"

    # Test directly with convert_html_to_markdown function
    # Register a test pattern temporarily
    original_registry = brocc_li.html_to_md.PARSER_REGISTRY.copy()

    # Create minimal HTML that the generic parser can handle
    minimal_html = """<html><body><h1>Test</h1><p>Content</p></body></html>"""

    try:
        # Add our slow parser to the registry with a real regex pattern
        brocc_li.html_to_md.PARSER_REGISTRY[r"https://test-timeout-url\.com"] = slow_parser

        # Call with short timeout using a matching URL
        result = convert_html_to_markdown(
            minimal_html, url="https://test-timeout-url.com", timeout=0.1
        )

        # Should fall back to generic parser and produce a result from the html
        assert result is not None
        assert "Test" in result
        assert "Parsed content" not in result  # Our slow parser's output shouldn't be there
    finally:
        # Restore original registry
        brocc_li.html_to_md.PARSER_REGISTRY = original_registry
