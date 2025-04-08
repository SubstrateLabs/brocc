"""
Files in the fixtures directory prefixed with underscore (_) are automatically tested.
For example:
- _example-site.html - Will be tested by this module
- example-site.html - Will not be tested (no underscore prefix)

Running `make chrome` saves new fixtures from open Chrome tabs.
"""

import re
from pathlib import Path

import pytest

from brocc_li.html_to_md import convert_html_to_markdown
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
        r"__\w+",
        r"React\.",
    ]

    for i, line in enumerate(lines[:5]):
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


def test_all_underscore_fixtures(fixtures_dir: Path):
    """Test conversion of all underscore-prefixed HTML fixtures."""
    fixtures = get_test_fixtures(fixtures_dir)
    assert fixtures, "No underscore-prefixed fixtures found"

    if DEBUG:
        logger.info(f"Found {len(fixtures)} test fixtures to process")

    passed = []
    failed = []

    for fixture_path in fixtures:
        fixture_name = fixture_path.name
        slug = fixture_name.removeprefix("_").removesuffix(".html")

        if DEBUG:
            logger.info(f"Testing fixture: {fixture_name}")

        try:
            with open(fixture_path, encoding="utf-8") as f:
                html = f.read()

            if DEBUG:
                logger.info(f"  HTML size: {len(html)} bytes")

            # Convert and validate
            markdown = convert_html_to_markdown(html, url=slug)

            if DEBUG:
                logger.info(f"  Markdown size: {len(markdown)} bytes")

            assert_valid_markdown(markdown, fixture_name)
            passed.append(slug)
        except Exception as e:
            failed.append((slug, str(e)))
            if DEBUG:
                logger.error(f"❌ {fixture_name}: Failed with error: {e}")
            raise  # Re-raise to keep pytest's normal behavior

    if DEBUG:
        logger.info(f"Tests completed: {len(passed)} passed, {len(failed)} failed")
        if passed:
            logger.info(f"Passed: {', '.join(passed)}")
        if failed:
            logger.error(f"Failed: {', '.join(name for name, _ in failed)}")
