import requests
from packaging import version

from brocc_li.utils.logger import logger
from brocc_li.utils.version import get_version

PYPI_PACKAGE_NAME = "brocc-li"
PYPI_JSON_URL = f"https://pypi.org/pypi/{PYPI_PACKAGE_NAME}/json"


def check_for_updates() -> str | None:
    """
    Checks PyPI for a newer version of the package.

    Returns:
        An update message string if an update is available, otherwise None.
    """
    try:
        response = requests.get(PYPI_JSON_URL, timeout=5)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        latest_version_str = data.get("info", {}).get("version")

        if not latest_version_str:
            logger.warning("Could not find version info in PyPI response.")
            return None

        current_v = version.parse(get_version())
        latest_v = version.parse(latest_version_str)

        if latest_v > current_v:
            logger.info(f"Update available: {current_v} -> {latest_v}")
            return f"Update available: v{latest_v}\n\nRun: [bold]pipx upgrade {PYPI_PACKAGE_NAME}[/bold]"
        else:
            logger.debug(f"App is up-to-date (v{current_v})")
            return None

    except requests.exceptions.Timeout:
        logger.warning("Timed out checking for updates on PyPI.")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"Could not check for updates on PyPI: {e}")
        return None
    except version.InvalidVersion:
        logger.error(
            f"Invalid version format found. Current: '{get_version()}', Latest: '{latest_version_str}'"
        )
        return None
    except Exception as e:
        logger.error(f"Unexpected error checking for updates: {e}")
        return None
