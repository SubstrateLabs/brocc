import asyncio
import json
import re
from typing import List, Optional, Tuple

import aiohttp
import websockets
import websockets.protocol
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


async def get_tab_html_content(ws_url: str) -> Tuple[Optional[str], Optional[str]]:
    """Get HTML and URL with hard timeout using asyncio.wait_for"""
    try:
        # Give up after 10 seconds total for entire CDP operation
        return await asyncio.wait_for(_get_html_using_dom(ws_url), timeout=10.0)
    except asyncio.TimeoutError:
        logger.error("CDP HTML retrieval timed out after 10 seconds")
        return None, None
    except Exception as e:
        logger.error(f"CDP failed: {e}")
        return None, None


async def _send_cdp_command(ws, msg_id: int, method: str, params: Optional[dict] = None) -> dict:
    """Send a CDP command and wait for the specific response matching the ID."""
    command = {"id": msg_id, "method": method}
    if params:
        command["params"] = params

    # logger.debug(f"Sending CDP command (id={msg_id}): {method}")
    await ws.send(json.dumps(command))

    # Loop until we get the response matching our msg_id
    while True:
        response_raw = await ws.recv()
        response = json.loads(response_raw)

        # Check if it's the response we are waiting for
        if response.get("id") == msg_id:
            # logger.debug(f"Received response for id={msg_id}")
            return response
        elif "method" in response:  # It's an event, ignore
            pass
        else:  # Unexpected message format
            pass


async def _get_html_using_dom(ws_url: str) -> Tuple[Optional[str], Optional[str]]:
    """Get HTML content and final URL using DOM.getOuterHTML CDP method"""
    msg_counter = 1  # Use a counter for unique message IDs
    current_url: Optional[str] = None  # Store the URL found
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
                # Enable Page domain (required for getResourceTree)
                await _send_cdp_command(ws, msg_counter, "Page.enable")
                msg_counter += 1

                # Get Resource Tree
                resource_result = await _send_cdp_command(ws, msg_counter, "Page.getResourceTree")
                msg_counter += 1

                # Check if this is an about:blank or empty page
                frame = resource_result.get("result", {}).get("frameTree", {}).get("frame", {})
                current_url = frame.get("url", None)  # Store the URL from frame
                if current_url in ["about:blank", ""]:
                    logger.debug("Detected blank/empty page - returning empty HTML")
                    return None, current_url  # Return None HTML, but the URL
            except Exception as e:
                # If this fails, just continue with normal DOM method
                logger.debug(f"Resource check failed: {e}, continuing with DOM method")

            # Enable DOM domain
            await _send_cdp_command(ws, msg_counter, "DOM.enable")
            msg_counter += 1

            # Get document root node
            doc_result = await _send_cdp_command(ws, msg_counter, "DOM.getDocument")
            msg_counter += 1
            # logger.debug(f"DOM.getDocument result: {doc_result}")

            # Extract document URL if available (more reliable than frame URL sometimes)
            root_data = doc_result.get("result", {}).get("root", {})
            doc_url = root_data.get("documentURL")
            if doc_url:
                current_url = doc_url  # Prefer documentURL if found
                logger.debug(f"Updated current URL from DOM.getDocument: {current_url}")

            # Extract root node ID from response
            root_node_id = root_data.get("nodeId")
            if not root_node_id:
                logger.error("Failed to get root node ID")
                return None, current_url  # Return None HTML, but potentially URL

            # Get outer HTML using the root node ID
            html_result = await _send_cdp_command(
                ws, msg_counter, "DOM.getOuterHTML", {"nodeId": root_node_id}
            )
            msg_counter += 1

            # Extract HTML content and log summary
            html_content = html_result.get("result", {}).get("outerHTML", "")
            if "error" in html_result:
                error_message = html_result["error"].get("message", "Unknown error")
                logger.warning(f"DOM.getOuterHTML failed: {error_message}")
            elif html_content:
                # logger.debug(f"DOM.getOuterHTML success: HTML length = {len(html_content)}")
                pass
            else:
                logger.warning("DOM.getOuterHTML succeeded but returned empty HTML")

            if html_content:
                return html_content, current_url
            else:
                return None, current_url  # Return None HTML, but the URL we found

    except asyncio.TimeoutError:
        # websockets uses asyncio.TimeoutError for connection timeouts?
        logger.warning("WebSocket connection timed out")
        return None, None
    except websockets.ConnectionClosedError as e:
        if "403 Forbidden" in str(e):
            logger.error(
                "Chrome rejected WebSocket connection. "
                "Please relaunch Chrome with --remote-allow-origins=* flag. "
                "You may need to quit all Chrome instances and restart the app."
            )
        else:
            logger.error(f"WebSocket connection error: {e}")
        return None, None
    except Exception as e:
        logger.error(f"Failed to connect to tab via WebSocket: {e}")
        return None, None


async def monitor_user_interactions(ws_url: str):
    """
    Monitor clicks and scrolls in a tab using CDP and yield events.

    Connects to the tab's WebSocket, injects JS listeners, and listens
    for console messages indicating user interaction.

    Yields:
        dict: Structured event data like {"type": "click", "data": {...}} or {"type": "scroll", "data": {...}}
    """
    msg_counter = 1
    connection = None  # Keep track of the connection to close it reliably
    try:
        logger.debug(f"Monitoring interactions for: {ws_url}")
        connection = await websockets.connect(
            ws_url,
            open_timeout=5.0,  # Slightly longer timeout for initial connection
            close_timeout=5.0,
            max_size=20 * 1024 * 1024,
        )
        ws = connection

        # === Step 1: Enable Runtime domain FIRST ===
        await _send_cdp_command(ws, msg_counter, "Runtime.enable")
        msg_counter += 1
        logger.info(f"[{ws_url[-10:]}] Runtime domain enabled.")

        # === Step 2: Enable dependent domains (Page, Log) ===
        await _send_cdp_command(ws, msg_counter, "Page.enable")
        msg_counter += 1
        logger.info(f"[{ws_url[-10:]}] Page domain enabled.")

        # === Step 3: Subscribe to consoleAPICalled event (Reverting from Log.entryAdded) ===
        # Note: We are testing if consoleAPICalled is more reliable here than Log.entryAdded
        # await _send_cdp_command(ws, msg_counter, "Log.enable") # Previous method
        # msg_counter += 1
        logger.info(
            f"[{ws_url[-10:]}] Subscribing via Runtime.enable (for consoleAPICalled)...done."
        )

        # Inject JS listeners
        js_code = """
        (function() {
            console.log('BROCC_DEBUG: Injecting listeners...'); // Debug log
            // Use a closure to prevent polluting the global scope too much
            let lastScrollTimestamp = 0;
            let lastClickTimestamp = 0;
            const DEBOUNCE_MS = 250; // Only log if events are spaced out

            document.addEventListener('click', e => {
                const now = Date.now();
                if (now - lastClickTimestamp > DEBOUNCE_MS) {
                    const clickData = {
                        x: e.clientX,
                        y: e.clientY,
                        target: e.target ? e.target.tagName : 'unknown',
                        timestamp: now
                    };
                    console.log('BROCC_CLICK_EVENT', JSON.stringify(clickData));
                    lastClickTimestamp = now;
                }
            }, { capture: true, passive: true }); // Use capture phase, non-blocking

            document.addEventListener('scroll', e => {
                 const now = Date.now();
                 if (now - lastScrollTimestamp > DEBOUNCE_MS) {
                    const scrollData = {
                        scrollX: window.scrollX,
                        scrollY: window.scrollY,
                        timestamp: now
                    };
                    console.log('BROCC_SCROLL_EVENT', JSON.stringify(scrollData));
                    lastScrollTimestamp = now;
                 }
            }, { capture: true, passive: true }); // Use capture phase, non-blocking

            console.log('BROCC_DEBUG: Listeners successfully installed.'); // Debug log
            return "Interaction listeners installed.";
        })();
        """
        eval_result = await _send_cdp_command(
            ws,
            msg_counter,
            "Runtime.evaluate",
            {"expression": js_code, "awaitPromise": False, "returnByValue": True},
        )
        msg_counter += 1
        # Log the result of the script injection
        injected_status = (
            eval_result.get("result", {}).get("result", {}).get("value", "Failed to inject")
        )
        logger.debug(f"{ws_url}: {injected_status}")

        # Listen for console entries
        while True:
            response_raw = await ws.recv()
            response = json.loads(response_raw)

            if response.get("method") == "Runtime.consoleAPICalled":
                call_type = response.get("params", {}).get("type")
                args = response.get("params", {}).get("args", [])

                # Check if it's a log message with our specific prefix
                if call_type == "log" and len(args) >= 1:
                    first_arg_value = args[0].get("value")

                    # --- Handle BROCC_DEBUG messages ---
                    if first_arg_value == "BROCC_DEBUG: Injecting listeners...":
                        logger.info(f"[{ws_url[-10:]}] JS Injection: Starting setup.")
                    elif first_arg_value == "BROCC_DEBUG: Listeners successfully installed.":
                        logger.success(
                            f"[{ws_url[-10:]}] JS Injection: Listeners confirmed installed."
                        )
                    # --- Handle BROCC_CLICK_EVENT ---
                    elif first_arg_value == "BROCC_CLICK_EVENT" and len(args) >= 2:
                        try:
                            click_data = json.loads(args[1].get("value", "{}"))
                            logger.debug(f"Detected click via CDP console: {click_data}")
                            yield {"type": "click", "data": click_data}
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse click event data from CDP console")
                    elif first_arg_value == "BROCC_SCROLL_EVENT" and len(args) >= 2:
                        try:
                            scroll_data = json.loads(args[1].get("value", "{}"))
                            logger.debug(f"Detected scroll via CDP console: {scroll_data}")
                            yield {"type": "scroll", "data": scroll_data}
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse scroll event data from CDP console")

    except (
        websockets.ConnectionClosedOK,
        websockets.ConnectionClosedError,
        websockets.ConnectionClosed,
    ) as e:
        logger.info(f"WebSocket connection closed for {ws_url}: {e}")
    except asyncio.TimeoutError:
        logger.warning(f"WebSocket connection attempt timed out for {ws_url}")
    except Exception as e:
        logger.error(
            f"Error monitoring interactions for {ws_url}: {type(e).__name__} - {e}", exc_info=True
        )
    finally:
        # Check state before attempting to close
        if connection and connection.state != websockets.protocol.State.CLOSED:
            await connection.close()
            logger.debug(f"Closed WebSocket connection for {ws_url}")
        # This generator stops yielding when an error occurs or connection closes.
