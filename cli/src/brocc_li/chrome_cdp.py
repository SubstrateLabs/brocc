import asyncio
import json
import re
from typing import List, Optional

import aiohttp
import websockets
from pydantic import BaseModel, Field

from brocc_li.utils.chrome import REMOTE_DEBUG_PORT
from brocc_li.utils.logger import logger

# Default timeout for Chrome info retrieval via CDP (seconds)
CHROME_INFO_TIMEOUT = 2

# Default timeout for HTML content retrieval via CDP (seconds)
GET_HTML_TIMEOUT = 2


class ChromeTab(BaseModel):
    id: str
    title: str = Field(default="Untitled")
    url: str = Field(default="about:blank")
    window_id: Optional[int] = None
    webSocketDebuggerUrl: Optional[str] = None
    devtoolsFrontendUrl: Optional[str] = None


async def get_tabs() -> List[ChromeTab]:
    """
    Get all Chrome browser tabs via CDP HTTP API.

    Connects to Chrome DevTools Protocol to retrieve tab information.
    Only returns actual page tabs (not DevTools, extensions, etc).

    Returns:
        List of ChromeTab objects representing open browser tabs
    """
    tabs = []

    try:
        # Get list of tabs via Chrome DevTools HTTP API
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://localhost:{REMOTE_DEBUG_PORT}/json/list",
                timeout=aiohttp.ClientTimeout(total=2),
            ) as response:
                if response.status != 200:
                    logger.error(f"Failed to get tabs: HTTP {response.status}")
                    return []

                cdp_tabs_json = await response.json()

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

    except aiohttp.ClientError as e:
        logger.error(f"Failed to connect to Chrome DevTools API: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Chrome DevTools API response: {e}")
    except Exception as e:
        logger.error(f"Error getting tabs via Chrome DevTools API: {e}")

    # Return empty list if we couldn't get tabs
    return []


async def open_new_tab(url: str = "") -> bool:
    """
    Open a new tab in Chrome via CDP HTTP API.

    Args:
        url: URL to open in the new tab (empty for blank tab)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Use CDP HTTP API to create a new tab
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://localhost:{REMOTE_DEBUG_PORT}/json/new",
                params={"url": url},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                if response.status == 200:
                    logger.debug(f"Successfully opened new tab with URL: {url}")
                    return True
                else:
                    logger.error(f"Failed to open URL {url}: HTTP {response.status}")
                    return False
    except Exception as e:
        logger.error(f"Failed to open URL {url}: {str(e)}")
        return False


async def get_chrome_info():
    """
    Get Chrome version info and check connection via CDP HTTP API.

    Makes a single request to get both connection status and Chrome version.

    Returns:
        dict: {
            "connected": bool indicating if connection succeeded,
            "version": Chrome version string (or "Unknown" if not connected),
            "data": Full response data if connected (or None if not connected)
        }
    """
    result = {"connected": False, "version": "Unknown", "data": None}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://localhost:{REMOTE_DEBUG_PORT}/json/version",
                timeout=aiohttp.ClientTimeout(total=CHROME_INFO_TIMEOUT),
            ) as response:
                result["connected"] = response.status == 200

                if result["connected"]:
                    data = await response.json()
                    result["data"] = data
                    result["version"] = data.get("Browser", "Unknown")

    except Exception as e:
        logger.debug(f"Error getting Chrome info: {e}")
        # Keep defaults (not connected, Unknown version)

    return result


async def get_tab_html_content(ws_url: str) -> str:
    """Get HTML with hard timeout using asyncio.wait_for"""
    try:
        # Give up after 5 seconds total for entire CDP operation
        return await asyncio.wait_for(_get_html_using_dom(ws_url), timeout=5.0)
    except asyncio.TimeoutError:
        logger.error("CDP HTML retrieval timed out after 5 seconds")
        return ""
    except Exception as e:
        logger.error(f"CDP failed: {e}")
        return ""


async def _get_html_using_dom(ws_url: str) -> str:
    """Get HTML content using DOM.getOuterHTML CDP method"""
    # No retry loop - just try once
    try:
        logger.debug(f"Connecting to tab via WebSocket: {ws_url}")
        async with websockets.connect(
            ws_url,
            open_timeout=GET_HTML_TIMEOUT,
            close_timeout=GET_HTML_TIMEOUT,
            max_size=20 * 1024 * 1024,  # default is 1mb, we use 20mb
        ) as ws:
            # First check if page is ready using Page.getResourceTree
            # This will tell us quickly if it's a blank/loading page
            try:
                page_enable_msg = json.dumps({"id": 1, "method": "Page.enable"})
                await ws.send(page_enable_msg)
                await ws.recv()  # Get response

                resource_msg = json.dumps({"id": 2, "method": "Page.getResourceTree"})
                await ws.send(resource_msg)
                resource_result = json.loads(await ws.recv())

                # Check if this is an about:blank or empty page
                frame = resource_result.get("result", {}).get("frameTree", {}).get("frame", {})
                url = frame.get("url", "")
                if url in ["about:blank", ""]:
                    logger.debug("Detected blank/empty page - returning empty HTML")
                    return ""
            except Exception as e:
                # If this fails, just continue with normal DOM method
                logger.debug(f"Resource check failed: {e}, continuing with DOM method")

            # Enable DOM domain
            enable_msg = json.dumps({"id": 3, "method": "DOM.enable"})
            await ws.send(enable_msg)
            result = json.loads(await ws.recv())

            # Get document root node
            get_doc_msg = json.dumps({"id": 4, "method": "DOM.getDocument"})
            await ws.send(get_doc_msg)
            result = json.loads(await ws.recv())

            # Extract root node ID from response
            root_node_id = result.get("result", {}).get("root", {}).get("nodeId")
            if not root_node_id:
                logger.error("Failed to get root node ID")
                return ""

            # Get outer HTML using the root node ID
            get_html_msg = json.dumps(
                {"id": 5, "method": "DOM.getOuterHTML", "params": {"nodeId": root_node_id}}
            )
            await ws.send(get_html_msg)
            result = json.loads(await ws.recv())

            # Extract HTML content
            html_content = result.get("result", {}).get("outerHTML", "")

            if html_content:
                logger.debug("Successfully retrieved HTML content")
                return html_content
            else:
                logger.warning("DOM method returned empty HTML")
                return ""

    except asyncio.TimeoutError:
        # websockets uses asyncio.TimeoutError for connection timeouts?
        logger.warning("WebSocket connection timed out")
        return ""
    except websockets.ConnectionClosedError as e:
        if "403 Forbidden" in str(e):
            logger.error(
                "Chrome rejected WebSocket connection. "
                "Please relaunch Chrome with --remote-allow-origins=* flag. "
                "You may need to quit all Chrome instances and restart the app."
            )
        else:
            logger.error(f"WebSocket connection error: {e}")
        return ""
    except Exception as e:
        logger.error(f"Failed to connect to tab via WebSocket: {e}")
        return ""
