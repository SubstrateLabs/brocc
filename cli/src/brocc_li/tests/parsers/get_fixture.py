from pathlib import Path

# Determine the absolute path to the 'html_fixtures' directory relative to this file
# __file__ -> get_fixture.py
# .parent -> parsers/
# .parent -> tests/
# .parent -> brocc_li/
# .parent -> src/
# .parent -> cli/  <-- This seems wrong, let's rethink the path
# Should be relative to the tests directory structure
# __file__ -> get_fixture.py
# .parent -> parsers/
# parent.parent -> tests/
# Then find 'html_fixtures' within 'tests/'
_FIXTURES_DIR = Path(__file__).parent.parent / "html_fixtures"


def get_fixture(fixture_name: str) -> str:
    """
    Loads the content of a fixture file from the 'html_fixtures' directory.

    Args:
        fixture_name: The name of the fixture file (e.g., "_linkedin-feed.html").

    Returns:
        The content of the fixture file as a string.

    Raises:
        FileNotFoundError: If the fixture file does not exist.
    """
    fixture_path = _FIXTURES_DIR / fixture_name
    if not fixture_path.exists():
        # Fail loudly if the fixture is missing, pytest will catch this
        raise FileNotFoundError(f"Fixture {fixture_name} not found at {fixture_path}")

    with open(fixture_path, encoding="utf-8") as f:
        return f.read()


def get_fixture_path(fixture_name: str) -> Path:
    """
    Gets the Path object for a fixture file.

    Args:
        fixture_name: The name of the fixture file.

    Returns:
        The Path object for the fixture file.

    Raises:
        FileNotFoundError: If the fixture file does not exist.
    """
    fixture_path = _FIXTURES_DIR / fixture_name
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture {fixture_name} not found at {fixture_path}")
    return fixture_path
