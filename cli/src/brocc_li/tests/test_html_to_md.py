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


@pytest.fixture
def fixtures_dir() -> Path:
    """Get the path to the fixtures directory."""
    return Path(__file__).parent.parent / "fixtures"


def assert_valid_markdown(markdown: str, url: str):
    """Helper function to check common markdown conversion assertions."""
    # Basic sanity checks for the markdown output
    assert markdown, f"Markdown output for {url} should not be empty"
    assert "Error converting" not in markdown, f"Conversion for {url} should not produce errors"

    # Get the lines and analyze document structure
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    if not lines:
        pytest.fail(f"Output for {url} has no non-empty lines")

    # Check document structure - should start with heading or text
    first_line = lines[0]
    assert first_line.startswith("#") or first_line[0].isalpha(), (
        f"Document for {url} should start with heading or text, got: {first_line}"
    )

    # Check for headings existing anywhere in the document
    assert any(line.startswith("#") for line in lines), (
        f"Output for {url} should contain at least one heading"
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
                pytest.fail(f"Line {i + 1} of {url} contains JS pattern '{pattern}': {line}")

    # Look for suspicious combinations of HTML and JS-specific content
    html_patterns = ["<div", "<span", "className=", "onClick=", "data-", "style="]
    for line in lines:
        html_matches = sum(1 for pattern in html_patterns if pattern.lower() in line.lower())
        if html_matches >= 2:
            pytest.fail(f"Line has multiple HTML/JS patterns: {line}")

    # Check for overall document coherence - should have reasonable paragraph structure
    text_lines = [line for line in lines if not line.startswith(("#", ">", "-", "*", "```", "|"))]
    if text_lines and len(text_lines) >= 5:  # Only check if we have enough lines
        # Analyze line length characteristics
        avg_line_length = sum(len(line) for line in text_lines) / len(text_lines)
        assert 20 <= avg_line_length <= 200, (
            f"Average text line length ({avg_line_length}) outside normal range for {url}"
        )


def get_test_fixtures(fixtures_dir: Path):
    """Get all test fixtures (HTML files prefixed with underscore)."""
    return list(fixtures_dir.glob("_*.html"))


def test_all_underscore_fixtures(fixtures_dir: Path):
    """Test conversion of all underscore-prefixed HTML fixtures."""
    fixtures = get_test_fixtures(fixtures_dir)
    assert fixtures, "No underscore-prefixed fixtures found"

    for fixture_path in fixtures:
        fixture_name = fixture_path.name
        with open(fixture_path, encoding="utf-8") as f:
            html = f.read()

        # Create a mock URL based on the filename
        url_name = fixture_name.removeprefix("_").removesuffix(".html")
        url = f"https://example.com/{url_name}"

        # Convert and validate
        markdown = convert_html_to_markdown(html, url=url)
        assert_valid_markdown(markdown, url)
