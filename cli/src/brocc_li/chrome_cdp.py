import json
import re
from typing import List, Optional

import requests
from pydantic import BaseModel, Field

from brocc_li.utils.logger import logger


class ChromeTab(BaseModel):
    """Representation of a Chrome browser tab from CDP."""

    id: str
    title: str = Field(default="Untitled")
    url: str = Field(default="about:blank")
    window_id: Optional[int] = None
    webSocketDebuggerUrl: Optional[str] = None
    devtoolsFrontendUrl: Optional[str] = None


def get_tabs(debug_port: int = 9222) -> List[ChromeTab]:
    """
    Get all Chrome browser tabs via CDP HTTP API.

    Connects to Chrome DevTools Protocol to retrieve tab information.
    Only returns actual page tabs (not DevTools, extensions, etc).

    Args:
        debug_port: Chrome debug port number (default: 9222)

    Returns:
        List of ChromeTab objects representing open browser tabs
    """
    tabs = []

    try:
        # Get list of tabs via Chrome DevTools HTTP API
        response = requests.get(f"http://localhost:{debug_port}/json/list", timeout=2)
        if response.status_code != 200:
            logger.error(f"Failed to get tabs: HTTP {response.status_code}")
            return []

        cdp_tabs_json = response.json()

        # Process each tab
        for tab_info in cdp_tabs_json:
            # Only include actual tabs (type: page), not devtools, etc.
            if tab_info.get("type") == "page":
                # Create a dict with all fields we want to extract
                tab_data = {
                    "id": tab_info.get("id"),
                    "title": tab_info.get("title", "Untitled"),
                    "url": tab_info.get("url", "about:blank"),
                    "webSocketDebuggerUrl": tab_info.get("webSocketDebuggerUrl"),
                    "devtoolsFrontendUrl": tab_info.get("devtoolsFrontendUrl"),
                }

                # Get window ID from debug URL if available
                devtools_url = tab_info.get("devtoolsFrontendUrl", "")
                if "windowId" in devtools_url:
                    try:
                        window_id_match = re.search(r"windowId=(\d+)", devtools_url)
                        if window_id_match:
                            tab_data["window_id"] = int(window_id_match.group(1))
                    except Exception as e:
                        logger.debug(f"Could not extract window ID: {e}")

                # Create Pydantic model instance
                try:
                    tabs.append(ChromeTab(**tab_data))
                except Exception as e:
                    logger.error(f"Failed to parse tab data: {e}")

        return tabs

    except requests.RequestException as e:
        logger.error(f"Failed to connect to Chrome DevTools API: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Chrome DevTools API response: {e}")
    except Exception as e:
        logger.error(f"Error getting tabs via Chrome DevTools API: {e}")

    # Return empty list if we couldn't get tabs
    return []


def open_new_tab(url: str = "", debug_port: int = 9222) -> bool:
    """
    Open a new tab in Chrome via CDP HTTP API.

    Args:
        url: URL to open in the new tab (empty for blank tab)
        debug_port: Chrome debug port number (default: 9222)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Use CDP HTTP API to create a new tab
        response = requests.get(
            f"http://localhost:{debug_port}/json/new", params={"url": url}, timeout=5
        )
        if response.status_code == 200:
            logger.debug(f"Successfully opened new tab with URL: {url}")
            return True
        else:
            logger.error(f"Failed to open URL {url}: HTTP {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Failed to open URL {url}: {str(e)}")
        return False


def get_chrome_info(debug_port: int = 9222, timeout: int = 2):
    """
    Get Chrome version info and check connection via CDP HTTP API.

    Makes a single request to get both connection status and Chrome version.

    Args:
        debug_port: Chrome debug port number (default: 9222)
        timeout: Request timeout in seconds (default: 2)

    Returns:
        dict: {
            "connected": bool indicating if connection succeeded,
            "version": Chrome version string (or "Unknown" if not connected),
            "data": Full response data if connected (or None if not connected)
        }
    """
    result = {"connected": False, "version": "Unknown", "data": None}

    try:
        response = requests.get(f"http://localhost:{debug_port}/json/version", timeout=timeout)
        result["connected"] = response.status_code == 200

        if result["connected"]:
            data = response.json()
            result["data"] = data
            result["version"] = data.get("Browser", "Unknown")

    except Exception as e:
        logger.debug(f"Error getting Chrome info: {e}")
        # Keep defaults (not connected, Unknown version)

    return result
