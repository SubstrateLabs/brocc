import pytest

from brocc_li.parsers.threads_home import threads_home_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = True
FIXTURE_NAME = "_threads-home.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(f"Fixture {FIXTURE_NAME} not found. Please add it to tests/fixtures.")

    # Convert using the parser, pass debug parameter
    markdown = threads_home_html_to_md(html, debug=debug)

    # Print the output for inspection if debug is enabled
    if debug:
        print("\n--- START THREADS HOME MARKDOWN OUTPUT ---")
        print(markdown)
        print("--- END THREADS HOME MARKDOWN OUTPUT ---\n")

    # Basic assertions (very minimal for now)
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, f"Conversion failed: {markdown}"
    assert (
        "<!-- unstructured parsing completed, but resulted in empty output -->" not in markdown
    ), "Parser reported empty output."
    # We can't assert much about content yet, need to see the output first
    # assert len(markdown.strip()) > 0, "Conversion resulted in empty markdown"

    logger.info(
        f"✅ Threads home conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else 'Set DEBUG=True to print output.'}"
    )
