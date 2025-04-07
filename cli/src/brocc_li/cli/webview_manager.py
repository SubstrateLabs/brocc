import atexit

import requests

from brocc_li.fastapi_server import FASTAPI_HOST, FASTAPI_PORT
from brocc_li.frontend_server import WEBAPP_HOST, WEBAPP_PORT
from brocc_li.utils.logger import logger
from brocc_li.utils.version import get_version

# URL for the App
WEBAPP_URL = f"http://{WEBAPP_HOST}:{WEBAPP_PORT}"
# URL for the API
API_URL = f"http://{FASTAPI_HOST}:{FASTAPI_PORT}"


def is_webview_open():
    """Check if webview is marked as open via the API"""
    try:
        response = requests.get(f"{API_URL}/webview/status")
        if response.status_code == 200:
            status = response.json()
            return status.get("active", False) and status.get("process_running", False)
        else:
            logger.error(f"Failed to check webview status: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error checking webview status via API: {e}")
        return False


def check_webview_health():
    """Simple health check for webview"""
    return is_webview_open()


def close_webview():
    """Close webview via API"""
    try:
        response = requests.post(f"{API_URL}/webview/close")
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "closed":
                # Don't log this since it often happens during shutdown
                return True
            elif result.get("status") == "not_running":
                # Don't log this since it often happens during shutdown
                return True
            else:
                logger.warning(f"Unexpected close result: {result}")
                return False
        else:
            logger.error(f"Failed to close webview: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error closing webview via API: {e}")
        return False


# Register cleanup function
atexit.register(close_webview)


def open_webview():
    """
    Open a webview by calling the API endpoint
    """
    # Don't open if already active
    if is_webview_open():
        logger.debug("Webview is already open, trying to bring it to foreground")
        try:
            # Try to focus the existing window
            response = requests.post(f"{API_URL}/webview/focus")
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "focused":
                    logger.debug("Successfully brought existing webview to the foreground")
                    return True
                else:
                    logger.warning("Webview is running but couldn't bring to foreground")
                    return True  # Still return success since it's running
        except Exception as e:
            logger.error(f"Error focusing webview: {e}")
            return True  # Return true since it's running, even if focus failed

    try:
        # Call the API to launch the webview
        response = requests.post(
            f"{API_URL}/webview/launch",
            params={"webapp_url": WEBAPP_URL, "title": f"🥦 Brocc v{get_version()}"},
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "launching":
                logger.debug("Successfully triggered webview launch")
                return True
            elif result.get("status") == "already_running":
                logger.debug("Webview is already running but couldn't bring to foreground")
                return True
            elif result.get("status") == "focused":
                logger.debug("Successfully brought existing webview to the foreground")
                return True
            else:
                logger.warning(f"Unexpected launch result: {result}")
                return False
        else:
            logger.error(f"Failed to launch webview: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Failed to launch webview via API: {e}")
        return False


# For compatibility with existing code
def launch_webview_in_thread(*args, **kwargs):
    """Wrapper around open_webview for backwards compatibility"""
    return open_webview()


if __name__ == "__main__":
    # Example of direct usage
    open_webview()
