import pytest

from brocc_li.parsers.gmail_inbox import gmail_inbox_html_to_md
from brocc_li.tests.parsers.get_fixture import get_fixture
from brocc_li.utils.logger import logger

DEBUG = True  # Set to True to see debug output
FIXTURE_NAME = "_gmail-inbox.html"


def test_parse(debug: bool = DEBUG):
    try:
        html = get_fixture(FIXTURE_NAME)
    except FileNotFoundError:
        pytest.fail(
            f"Fixture {FIXTURE_NAME} not found. Please create it in the fixtures directory."
        )
    except Exception as e:
        pytest.fail(f"Failed to load fixture {FIXTURE_NAME}: {e}")

    markdown = gmail_inbox_html_to_md(html, debug=debug)

    if debug:
        print(f"\n--- START GMAIL INBOX MARKDOWN OUTPUT ({FIXTURE_NAME}) ---")
        if markdown:
            print(markdown)
        else:
            print("<<< MARKDOWN OUTPUT IS NONE >>>")
        print(f"--- END GMAIL INBOX MARKDOWN OUTPUT ({FIXTURE_NAME}) ---\n")

    # Just basic assertions
    assert markdown is not None, "Conversion returned None"
    assert isinstance(markdown, str), "Conversion did not return a string"
    assert "Error processing" not in markdown, "Parser reported an error during processing"

    logger.info(
        f"✅ Gmail inbox conversion test ran for {FIXTURE_NAME}. "
        f"{'Output printed above.' if debug else 'Debug output disabled.'}"
    )
