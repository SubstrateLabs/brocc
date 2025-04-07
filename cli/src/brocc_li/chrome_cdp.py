import json
import re
import time
from typing import List, Optional

import requests
import websocket
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


def get_tab_html_content(ws_url: str, timeout: int = 1, max_retries: int = 0) -> str:
    """
    Connect to a Chrome tab via WebSocket debugger URL and get HTML content.

    Uses single-attempt approach without retries to quickly detect if CDP will work.
    If this fails, ChromeManager will fallback to Playwright approach.

    Args:
        ws_url: WebSocket debugger URL for the tab
        timeout: Connection and command timeout in seconds
        max_retries: Maximum number of retry attempts (default 0 = no retries)

    Returns:
        HTML content as string, empty string if fails
    """
    if not ws_url:
        logger.error("Missing WebSocket URL for tab")
        return ""

    # Do a quick check if the page is in a viable state for extraction
    if not _is_page_viable(ws_url, timeout=0.5):
        logger.warning("Tab is completely unresponsive, skipping HTML extraction")
        return ""

    # Try primary method without retries
    html = _get_html_using_dom(ws_url, timeout, 0)  # Force max_retries=0
    if html:
        return html

    logger.error("CDP HTML extraction failed, will try fallback")
    return ""


def _is_page_viable(ws_url: str, timeout: float = 0.5) -> bool:
    """
    Quick check to determine if a page is in a viable state for HTML extraction.

    This does minimal checks to avoid spending time on completely unresponsive tabs,
    but should allow most normal tabs to pass even if they're still loading.

    Args:
        ws_url: WebSocket debugger URL for the tab
        timeout: Short timeout for quick checks

    Returns:
        bool: True if page appears viable for extraction, False otherwise
    """
    try:
        # Try to establish a websocket connection with very short timeout
        ws = websocket.create_connection(ws_url, timeout=timeout)

        try:
            # Just do a basic ping test - if we can communicate at all, consider it viable
            ping_msg = json.dumps({"id": 50, "method": "Browser.getVersion"})
            ws.send(ping_msg)

            # If we can send and receive anything, consider it viable
            try:
                ws.recv()  # Just try to receive anything
                return True
            except websocket.WebSocketTimeoutException:
                # Even timeout on response is acceptable - the page may be busy but viable
                return True

        except Exception as e:
            logger.debug(f"Error during basic viability check: {e}")
            return False
        finally:
            ws.close()

    except websocket.WebSocketTimeoutException:
        logger.debug("Connection timed out during viability check")
        return False
    except Exception as e:
        logger.debug(f"Failed to connect to tab for viability check: {e}")
        return False


def _get_html_using_dom(ws_url: str, timeout: int, max_retries: int) -> str:
    """Get HTML content using DOM.getOuterHTML CDP method"""
    # No retry loop - just try once
    try:
        logger.debug(f"Connecting to tab via WebSocket: {ws_url}")
        ws = websocket.create_connection(ws_url, timeout=timeout)

        try:
            # First check if page is ready using Page.getResourceTree
            # This will tell us quickly if it's a blank/loading page
            try:
                page_enable_msg = json.dumps({"id": 1, "method": "Page.enable"})
                ws.send(page_enable_msg)
                ws.recv()  # Get response

                resource_msg = json.dumps({"id": 2, "method": "Page.getResourceTree"})
                ws.send(resource_msg)
                resource_result = json.loads(ws.recv())

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
            ws.send(enable_msg)
            result = json.loads(ws.recv())

            # Get document root node
            get_doc_msg = json.dumps({"id": 4, "method": "DOM.getDocument"})
            ws.send(get_doc_msg)
            result = json.loads(ws.recv())

            # Extract root node ID from response
            root_node_id = result.get("result", {}).get("root", {}).get("nodeId")
            if not root_node_id:
                logger.error("Failed to get root node ID")
                return ""

            # Get outer HTML using the root node ID
            get_html_msg = json.dumps(
                {"id": 5, "method": "DOM.getOuterHTML", "params": {"nodeId": root_node_id}}
            )
            ws.send(get_html_msg)
            result = json.loads(ws.recv())

            # Extract HTML content
            html_content = result.get("result", {}).get("outerHTML", "")

            if html_content:
                logger.debug("Successfully retrieved HTML content using DOM method")
                return html_content
            else:
                logger.warning("DOM method returned empty HTML")
                return ""

        except Exception as e:
            logger.error(f"Error during DOM commands: {e}")
            return ""
        finally:
            # Always close the websocket connection
            ws.close()

    except websocket.WebSocketTimeoutException:
        logger.warning("WebSocket connection timed out")
        return ""
    except websocket.WebSocketBadStatusException as e:
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


def _get_html_using_snapshot(ws_url: str, timeout: int, max_retries: int) -> str:
    """Get HTML content using Page.captureSnapshot CDP method"""
    for attempt in range(max_retries + 1):
        try:
            # Add backoff between retries (use smaller backoff)
            if attempt > 0:
                backoff = 0.2  # Fixed small backoff
                logger.debug(
                    f"Retrying snapshot method (attempt {attempt}/{max_retries}), waiting {backoff}s"
                )
                time.sleep(backoff)

            ws = websocket.create_connection(ws_url, timeout=timeout)

            try:
                # Check if page is really blank first
                try:
                    resource_msg = json.dumps({"id": 10, "method": "Page.getResourceTree"})
                    ws.send(resource_msg)
                    resource_result = json.loads(ws.recv())

                    # Check if this is an about:blank or empty page
                    frame = resource_result.get("result", {}).get("frameTree", {}).get("frame", {})
                    url = frame.get("url", "")
                    if url in ["about:blank", ""]:
                        logger.debug("Detected blank/empty page - skipping snapshot method")
                        return ""
                except Exception:
                    # If this fails, just continue with normal snapshot method
                    pass

                # Enable Page domain
                enable_msg = json.dumps({"id": 11, "method": "Page.enable"})
                ws.send(enable_msg)
                result = json.loads(ws.recv())

                # Capture snapshot
                snapshot_msg = json.dumps(
                    {"id": 12, "method": "Page.captureSnapshot", "params": {"format": "html"}}
                )
                ws.send(snapshot_msg)
                result = json.loads(ws.recv())

                # Extract HTML snapshot
                html_content = result.get("result", {}).get("data", "")

                if html_content:
                    logger.debug("Successfully retrieved HTML content using snapshot method")
                    return html_content
                else:
                    logger.warning("Snapshot method returned empty HTML")

            except Exception as e:
                logger.error(f"Error during snapshot commands: {e}")
            finally:
                ws.close()

        except Exception as e:
            logger.error(f"Failed in snapshot method: {e}")

    return ""


def _get_html_using_runtime(ws_url: str, timeout: int, max_retries: int) -> str:
    """Get HTML content using Runtime.evaluate to execute JavaScript"""
    for attempt in range(max_retries + 1):
        try:
            # Add backoff between retries (use smaller backoff)
            if attempt > 0:
                backoff = 0.2  # Fixed small backoff
                logger.debug(
                    f"Retrying runtime method (attempt {attempt}/{max_retries}), waiting {backoff}s"
                )
                time.sleep(backoff)

            ws = websocket.create_connection(ws_url, timeout=timeout)

            try:
                # Check if page is blank first
                try:
                    navigate_msg = json.dumps({"id": 20, "method": "Page.getNavigationHistory"})
                    ws.send(navigate_msg)
                    nav_result = json.loads(ws.recv())

                    entries = nav_result.get("result", {}).get("entries", [])
                    current_entry = next(
                        (
                            e
                            for e in entries
                            if e.get("id") == nav_result.get("result", {}).get("currentIndex")
                        ),
                        {},
                    )
                    url = current_entry.get("url", "")

                    if url in ["about:blank", ""]:
                        logger.debug("Detected blank/empty page in runtime method - skipping")
                        return ""
                except Exception:
                    # If this fails, just continue with normal runtime method
                    pass

                # Enable Runtime domain
                enable_msg = json.dumps({"id": 21, "method": "Runtime.enable"})
                ws.send(enable_msg)
                result = json.loads(ws.recv())

                # Execute JavaScript to get HTML
                js_msg = json.dumps(
                    {
                        "id": 22,
                        "method": "Runtime.evaluate",
                        "params": {
                            "expression": "document.documentElement.outerHTML",
                            "returnByValue": True,
                        },
                    }
                )
                ws.send(js_msg)
                result = json.loads(ws.recv())

                # Extract HTML from JavaScript result
                html_content = result.get("result", {}).get("result", {}).get("value", "")

                if html_content:
                    logger.debug("Successfully retrieved HTML content using runtime method")
                    return html_content
                else:
                    logger.warning("Runtime method returned empty HTML")

            except Exception as e:
                logger.error(f"Error during runtime commands: {e}")
            finally:
                ws.close()

        except Exception as e:
            logger.error(f"Failed in runtime method: {e}")

    return ""
