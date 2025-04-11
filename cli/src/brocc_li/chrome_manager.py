import asyncio
import os
from enum import Enum
from typing import Dict, List, NamedTuple, Optional, Tuple

from rich.console import Console

from brocc_li.chrome_cdp import get_chrome_info, get_tab_html_content, get_tabs
from brocc_li.utils.chrome import (
    is_chrome_debug_port_active,
    is_chrome_process_running,
    launch_chrome,
    quit_chrome,
)
from brocc_li.utils.logger import logger

# Calculate optimal number of workers for thread pool
# Use min(32, os.cpu_count() + 4) which is Python's default formula
# but cap at 10 to avoid too many simultaneous Chrome connections
CPU_COUNT = os.cpu_count() or 1  # Default to 1 if cpu_count returns None
MAX_WORKERS = min(10, CPU_COUNT + 4)


class ChromeState(NamedTuple):
    is_running: bool
    has_debug_port: bool


class ChromeStatus(Enum):
    CONNECTED = "connected"
    NOT_RUNNING = "not_running"
    RUNNING_WITHOUT_DEBUG_PORT = "running_without_debug_port"
    CONNECTING = "connecting"


class ChromeManager:
    """Manages the connection to a Chrome instance with remote debugging."""

    def __init__(self):
        self._state: ChromeState = ChromeState(False, False)  # Initial state
        self._connected: bool = False
        self._initialized = False

    async def _ensure_initialized(self):
        """Ensure async initialization has been performed"""
        if not self._initialized:
            await self._init_async()
            self._initialized = True

    async def _init_async(self):
        """Initialize the state asynchronously"""
        self._state = await self._get_chrome_state()
        if self._state.has_debug_port:
            await self._test_connection(quiet=True)

    async def _test_connection(self, quiet: bool = False) -> bool:
        """Tests connection to Chrome debug port, updates status"""
        try:
            # Try to connect - directly use async function
            chrome_info = await get_chrome_info()
            if chrome_info["connected"]:
                self._connected = True
                if not quiet:
                    logger.debug(f"Auto-connected to Chrome {chrome_info['version']}")
                return True
            else:
                if not quiet:
                    logger.warning("Auto-connect: Failed to connect despite active debug port")
        except Exception as e:
            if not quiet:
                logger.error(f"Auto-connect error: {e}")

        return False

    async def _get_chrome_state(self) -> ChromeState:
        """Get the current state of Chrome (running and debug port status)."""
        has_debug_port = await is_chrome_debug_port_active()
        is_running = has_debug_port or await is_chrome_process_running()
        return ChromeState(
            is_running=is_running,
            has_debug_port=has_debug_port,
        )

    @property
    def connected(self) -> bool:
        return self._connected and self._state.has_debug_port

    async def status_code(self) -> ChromeStatus:
        """Returns the machine-readable enum status of Chrome."""
        await self._ensure_initialized()
        self._state = await self._get_chrome_state()
        if self._connected and self._state.has_debug_port:
            return ChromeStatus.CONNECTED
        elif not self._state.is_running:
            return ChromeStatus.NOT_RUNNING
        elif self._state.is_running and not self._state.has_debug_port:
            return ChromeStatus.RUNNING_WITHOUT_DEBUG_PORT
        else:
            return ChromeStatus.CONNECTING

    async def refresh_state(self) -> ChromeState:
        """Refresh and return the current Chrome state."""
        await self._ensure_initialized()
        self._state = await self._get_chrome_state()
        # Try to auto-connect if configured and debug port is active
        if self._state.has_debug_port and not self._connected:
            await self._test_connection()
        return self._state

    async def ensure_connection(
        self,
        quiet: bool = False,
    ) -> bool:
        """
        Ensures Chrome is running with the debug port and connects to it.

        Handles launching or relaunching Chrome as needed.

        Args:
            quiet: If True, suppress most logging output.

        Returns:
            A boolean indicating whether connection was successful.
        """
        await self._ensure_initialized()
        self._state = await self._get_chrome_state()

        # Check if we already have a connected browser
        if self._connected and self._state.has_debug_port:
            if not quiet:
                logger.debug("Already connected to Chrome browser")
            return True

        if self._state.has_debug_port:
            if not quiet:
                logger.debug("Chrome already running with debug port. Attempting to connect...")

            # Get connection status and version in one call - directly use async function
            chrome_info = await get_chrome_info()
            if chrome_info["connected"]:
                self._connected = True
                if not quiet:
                    logger.success(
                        f"Successfully connected to Chrome {chrome_info['version']} via debug port"
                    )
                return True
            else:
                if not quiet:
                    logger.warning(
                        "Connection failed despite active debug port. Attempting relaunch."
                    )

                # Quit all Chrome instances directly
                quit_result = await quit_chrome()
                if not quit_result:
                    if not quiet:
                        logger.error("Failed to quit existing Chrome instance(s). Cannot proceed.")
                    return False
                # Fall through to launch logic

        elif self._state.is_running:
            if not quiet:
                logger.warning("Chrome is running without the debug port.")

            # Quit all Chrome instances directly
            quit_result = await quit_chrome()
            if not quit_result:
                if not quiet:
                    logger.error("Failed to quit existing Chrome instance(s). Cannot proceed.")
                return False
            # Fall through to launch logic

        else:
            if not quiet:
                logger.debug("Chrome is not running.")

        # Launch logic (reached if not running, or after quitting)
        launch_result = await launch_chrome(quiet=quiet)
        if launch_result:
            await asyncio.sleep(2)  # Use asyncio.sleep instead of time.sleep
            if not quiet:
                logger.debug("Attempting to connect to newly launched Chrome...")

            # Check connection directly instead of using helper method
            chrome_info = await get_chrome_info()
            chrome_connected = chrome_info["connected"]

            if chrome_connected:
                self._connected = True
                chrome_version = chrome_info["version"]  # Get version from same call
                if not quiet:
                    logger.success(
                        f"Successfully connected to Chrome {chrome_version} via debug port"
                    )
                return True
            else:
                if not quiet:
                    logger.error("Failed to connect even after launching Chrome.")
                return False
        else:
            if not quiet:
                logger.error("Failed to launch Chrome. Cannot connect.")
            return False

    async def get_all_tabs(self) -> List[dict]:
        """
        Get information about all open tabs in Chrome using CDP HTTP API:
        - Title, URL, ID, window_id, webSocketDebuggerUrl, devtoolsFrontendUrl
        """
        await self._ensure_initialized()
        # Directly use async function
        tabs_data = await get_tabs()

        # Convert the Pydantic models to dictionaries for backward compatibility
        tabs = []
        for tab in tabs_data:
            tab_dict = tab.model_dump()

            # If window_id exists but not part of the dict, add it
            if tab.window_id and "window_id" not in tab_dict:
                tab_dict["window_id"] = tab.window_id

            tabs.append(tab_dict)

        return tabs

    async def get_tab_html(self, tab_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get the HTML content and the final URL from a specific tab using its ID via CDP.

        Args:
            tab_id: The ID of the tab to get HTML from

        Returns:
            Tuple (html_content | None, final_url | None)
        """
        await self._ensure_initialized()
        if not self._state.has_debug_port:
            logger.error("Chrome debug port is not active. Cannot get tab HTML.")
            return None, None

        # Refresh our state first to ensure we have the latest connection status
        self._state = await self._get_chrome_state()

        final_url: Optional[str] = None  # Keep track of the best URL we find

        tabs = await get_tabs()
        tab = next((t for t in tabs if t.id == tab_id), None)

        if tab:
            final_url = tab.url
        if not tab or not tab.webSocketDebuggerUrl:
            logger.error(f"Tab with ID {tab_id} not found or has no WebSocket URL")
            return None, final_url

        ws_url = tab.webSocketDebuggerUrl
        html, cdp_url = await get_tab_html_content(ws_url)
        if cdp_url:  # Update URL if CDP returned one
            final_url = cdp_url

        return html, final_url

    async def get_html_for_tabs(
        self, tabs: List[dict]
    ) -> List[Tuple[dict, Optional[str], Optional[str]]]:
        """
        Get HTML content and final URLs from multiple tabs via CDP.

        Args:
            tabs: List of tab dictionaries containing id and other info

        Returns:
            List of (tab_dict, html | None, final_url | None) tuples
        """
        await self._ensure_initialized()
        results: List[Tuple[dict, Optional[str], Optional[str]]] = []  # Explicitly type
        cdp_fetched_urls: Dict[str, str] = {}  # Store URLs found during CDP phase
        console = Console()

        if not tabs:
            return []

        console.print(f"[cyan]get_html_for_tabs: processing {len(tabs)} tabs...[/cyan]")
        semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent CDP tasks

        async def process_tab_with_cdp_async(tab):
            async with semaphore:  # Acquire semaphore before running
                tab_id = tab.get("id")
                title = tab.get("title", "Untitled")
                short_title = (title[:30] + "...") if len(title) > 30 else title

                console.print(f"[dim]get_tab_html: {short_title}...[/dim]")
                html: Optional[str] = None
                url: Optional[str] = tab.get("url")  # Start with the initial URL

                try:
                    # This now returns (html, url) and only uses CDP
                    html, url = await self.get_tab_html(tab_id)

                except asyncio.TimeoutError:
                    console.print(f"[red]⌛[/red] get_tab_html: {short_title} timed out")
                    # html remains None, url might be updated
                except Exception as e:  # Catch other potential errors during CDP
                    console.print(f"[red]✗[/red] get_tab_html: {short_title}: {e}")
                    # html remains None, url might be updated

                if not html:
                    console.print(f"[yellow]get_tab_html: {short_title} failed[/yellow]")
                else:
                    console.print(f"[green]✓[/green] get_tab_html: {short_title} from {url}")
                # Store the URL found by CDP, even if it failed
                if tab_id and url:
                    cdp_fetched_urls[tab_id] = url

                return tab, html, url

        # Process all tabs in parallel
        cdp_results = await asyncio.gather(*[process_tab_with_cdp_async(tab) for tab in tabs])

        # Process results
        for tab, html, url in cdp_results:
            results.append((tab, html, url))

        # Report final stats
        success_count = sum(1 for _, html, _ in results if html)
        if success_count == len(tabs):
            console.print(
                f"[bold green]get_html_for_tabs: all {len(tabs)} tabs succeeded[/bold green]"
            )
        else:
            console.print(
                f"[bold yellow]get_html_for_tabs: {success_count}/{len(tabs)} tabs succeeded[/bold yellow]"
            )

        return results
