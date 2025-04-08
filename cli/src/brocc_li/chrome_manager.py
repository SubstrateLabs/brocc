import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
from typing import List, NamedTuple

from rich.console import Console

from brocc_li.chrome_cdp import get_chrome_info, get_tab_html_content, get_tabs, open_new_tab
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
    """Machine-readable status codes for Chrome connection state."""

    CONNECTED = "connected"
    NOT_RUNNING = "not_running"
    RUNNING_WITHOUT_DEBUG_PORT = "running_without_debug_port"
    CONNECTING = "connecting"


# Tab reference for tracking
class TabReference(NamedTuple):
    id: str
    url: str
    html: str = ""


class ChromeManager:
    """Manages the connection to a Chrome instance with remote debugging."""

    def __init__(self, auto_connect: bool = False):
        """
        Initialize the Chrome Manager.

        Args:
            auto_connect: If True, will automatically try to connect to Chrome
                         if a debug port is detected.
        """
        self._state: ChromeState = self._get_chrome_state()
        self._connected: bool = False
        self._auto_connect = auto_connect

        # Only log detailed status when used directly, not during import
        if auto_connect and self._state.has_debug_port:
            # Attempt auto-connect without detailed logging during import
            # We'll just log the final result if successful
            self._try_auto_connect(quiet=True)

    def _try_auto_connect(self, quiet: bool = False) -> bool:
        """
        Attempt to automatically connect to Chrome with debug port.

        Args:
            quiet: If True, suppress most log output during connection

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Try to connect
            chrome_info = get_chrome_info()
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

    def _get_chrome_state(self) -> ChromeState:
        """Get the current state of Chrome (running and debug port status)."""
        has_debug_port = is_chrome_debug_port_active()
        is_running = has_debug_port or is_chrome_process_running()
        return ChromeState(
            is_running=is_running,
            has_debug_port=has_debug_port,
        )

    def _check_chrome_connection(self) -> bool:
        """Check if we can connect to Chrome via CDP."""
        chrome_info = get_chrome_info()
        return chrome_info["connected"]

    def _get_chrome_version(self) -> str:
        """Get Chrome version from CDP."""
        chrome_info = get_chrome_info()
        return chrome_info["version"]

    @property
    def status_code(self) -> ChromeStatus:
        """Returns the machine-readable enum status of Chrome."""
        self._state = self._get_chrome_state()
        if self._connected and self._state.has_debug_port:
            return ChromeStatus.CONNECTED
        elif not self._state.is_running:
            return ChromeStatus.NOT_RUNNING
        elif self._state.is_running and not self._state.has_debug_port:
            return ChromeStatus.RUNNING_WITHOUT_DEBUG_PORT
        else:
            return ChromeStatus.CONNECTING

    @property
    def connected(self) -> bool:
        """Return whether we're connected to Chrome."""
        return self._connected and self._state.has_debug_port

    def refresh_state(self) -> ChromeState:
        """Refresh and return the current Chrome state."""
        self._state = self._get_chrome_state()
        # Try to auto-connect if configured and debug port is active
        if self._auto_connect and self._state.has_debug_port and not self._connected:
            self._try_auto_connect()
        return self._state

    def test_connection(
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
        self._state = self._get_chrome_state()

        # Check if we already have a connected browser
        if self._connected and self._state.has_debug_port:
            if not quiet:
                logger.debug("Already connected to Chrome browser")
            return True

        if self._state.has_debug_port:
            if not quiet:
                logger.debug("Chrome already running with debug port. Attempting to connect...")

            # Get connection status and version in one call
            chrome_info = get_chrome_info()
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

                # Always proceed with quitting Chrome and relaunching
                if not quit_chrome():
                    if not quiet:
                        logger.error("Failed to quit existing Chrome instance(s). Cannot proceed.")
                    return False
                # Fall through to launch logic

        elif self._state.is_running:
            if not quiet:
                logger.warning("Chrome is running without the debug port.")

            # Always proceed with quitting Chrome and relaunching
            if not quit_chrome():
                if not quiet:
                    logger.error("Failed to quit existing Chrome instance(s). Cannot proceed.")
                return False
            # Fall through to launch logic

        else:
            if not quiet:
                logger.debug("Chrome is not running.")

            # Always proceed with launching Chrome
            # Fall through to launch logic

        # Launch logic (reached if not running, or after quitting)
        if launch_chrome(quiet=quiet):
            time.sleep(2)
            if not quiet:
                logger.debug("Attempting to connect to newly launched Chrome...")
            if self._check_chrome_connection():
                self._connected = True
                chrome_version = self._get_chrome_version()
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

    def open_new_tab(self, url: str = "") -> bool:
        """
        Open a new tab with the given URL.

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._connected or not self._state.has_debug_port:
            logger.error("Not connected to Chrome. Cannot open new tab.")
            return False

        result = open_new_tab(url)
        if result:
            logger.success(f"Successfully opened new tab with URL: {url}")
        return result

    def get_all_tabs(self) -> List[dict]:
        """
        Get information about all open tabs in Chrome using CDP HTTP API.

        Uses Chrome DevTools Protocol HTTP API to get detailed tab information including:
        - Title and URL
        - Tab IDs
        - Debug URLs

        Returns:
            List of dictionaries with detailed tab information
        """
        # Use the new get_tabs function from chrome_cdp
        tabs_data = get_tabs()

        # Convert the Pydantic models to dictionaries for backward compatibility
        tabs = []
        for tab in tabs_data:
            tab_dict = tab.model_dump()

            # If window_id exists but not part of the dict, add it
            if tab.window_id and "window_id" not in tab_dict:
                tab_dict["window_id"] = tab.window_id

            tabs.append(tab_dict)

        return tabs

    def get_tab_html(self, tab_id: str, cdp_only: bool = False) -> str:
        """
        Get the HTML content from a specific tab using its ID.

        Uses a multi-strategy approach:
        1. Quick check with Chrome DevTools Protocol (fast but fails on anti-bot sites)
        2. If CDP fails and cdp_only is False, fall back to Playwright (better for anti-bot sites)

        Args:
            tab_id: The ID of the tab to get HTML from
            cdp_only: If True, only try CDP method without Playwright fallback

        Returns:
            HTML content as string, empty string if tab not found or connection fails
        """
        # Refresh our state first to ensure we have the latest connection status
        self._state = self._get_chrome_state()

        if not self._state.has_debug_port:
            logger.error("Chrome debug port is not active. Cannot get tab HTML.")
            return ""

        if not self._connected:
            # Try to establish connection first
            logger.warning("Not connected to Chrome. Attempting to connect...")
            if not self.test_connection(quiet=True):
                logger.error("Failed to connect to Chrome. Cannot get tab HTML.")
                return ""

        # Find the tab with the specified ID
        tabs = get_tabs()
        tab = next((t for t in tabs if t.id == tab_id), None)

        if not tab or not tab.webSocketDebuggerUrl:
            logger.error(f"Tab with ID {tab_id} not found or has no WebSocket URL")
            return ""

        # Strategy 1: Try CDP approach first (very quick check, no retries)
        logger.debug(f"Trying to get HTML from tab {tab_id} via CDP")
        html = get_tab_html_content(tab.webSocketDebuggerUrl)

        # Strategy 2: If CDP failed and we're not in CDP-only mode, try Playwright fallback
        if not html and not cdp_only:
            logger.debug(f"CDP failed, trying Playwright fallback for tab {tab_id}")
            try:
                # Import here to avoid circular imports
                from brocc_li.playwright_fallback import playwright_fallback

                # Use our fallback method which opens a new tab with anti-detection features
                html = playwright_fallback.get_html_from_tab(tab_id)

                if html:
                    logger.debug(
                        f"Successfully retrieved HTML via Playwright fallback ({len(html)} chars)"
                    )
                else:
                    logger.warning(f"Playwright fallback also failed for tab {tab_id}")
            except Exception as e:
                logger.error(f"Playwright fallback error: {e}")

        return html

    def get_parallel_tab_html(self, tabs):
        """
        Efficiently get HTML content from multiple tabs.

        First tries CDP in parallel for all tabs, then handles Playwright fallbacks sequentially.

        Args:
            tabs: List of tab dictionaries containing id and other info

        Returns:
            List of (tab, html) tuples with HTML content
        """
        result_tabs_with_html = []
        tabs_needing_fallback = []
        console = Console()

        if not tabs:
            return []

        # Step 0: Log the start of the process
        console.print(f"[cyan]Starting HTML extraction for {len(tabs)} tabs...[/cyan]")

        # Function for ThreadPoolExecutor to process a single tab with CDP only
        def process_tab_with_cdp(tab):
            tab_id = tab.get("id")
            if not tab_id:
                return tab, "", False

            title = tab.get("title", "Untitled")
            short_title = (title[:30] + "...") if len(title) > 30 else title

            # Try CDP first (will skip Playwright fallback)
            console.print(f"[dim]CDP: Getting HTML for {short_title}...[/dim]")
            html = self.get_tab_html(tab_id, cdp_only=True)

            # If CDP failed, mark for fallback
            needs_fallback = not bool(html)
            if needs_fallback:
                console.print(
                    f"[yellow]CDP failed for {short_title} - queuing for Playwright fallback[/yellow]"
                )
            else:
                char_count = len(html)
                line_count = html.count("\n") + 1
                console.print(
                    f"[green]✓[/green] CDP success: {short_title} ({char_count:,} chars, {line_count:,} lines)"
                )

            return tab, html, needs_fallback

        # Step 1: Try all tabs with CDP in parallel
        console.print(
            f"[bold cyan]Phase 1: Parallel CDP extraction for {len(tabs)} tabs...[/bold cyan]"
        )

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_tab = {executor.submit(process_tab_with_cdp, tab): tab for tab in tabs}

            for future in as_completed(future_to_tab):
                tab, html, needs_fallback = future.result()

                if needs_fallback:
                    # Queue for fallback if CDP failed
                    tabs_needing_fallback.append(tab)
                else:
                    # Add successful CDP result
                    result_tabs_with_html.append((tab, html))

        # Step 2: Process fallbacks sequentially
        if tabs_needing_fallback:
            console.print(
                f"\n[bold cyan]Phase 2: Sequential Playwright fallbacks for {len(tabs_needing_fallback)} tabs...[/bold cyan]"
            )

            try:
                # Import here to avoid circular imports
                from brocc_li.playwright_fallback import playwright_fallback
            except ImportError as e:
                logger.error(f"Failed to import Playwright fallback: {e}")
                # Return what we have so far
                return result_tabs_with_html

            for i, tab in enumerate(tabs_needing_fallback):
                tab_id = tab.get("id")
                if tab_id:
                    title = tab.get("title", "Untitled")
                    short_title = (title[:30] + "...") if len(title) > 30 else title

                    console.print(
                        f"[dim]Playwright ({i + 1}/{len(tabs_needing_fallback)}): {short_title}...[/dim]"
                    )

                    # Run fallback with full Playwright pipeline
                    html = playwright_fallback.get_html_from_tab(tab_id)

                    if html:
                        char_count = len(html)
                        line_count = html.count("\n") + 1
                        console.print(
                            f"[green]✓[/green] Playwright success: {short_title} ({char_count:,} chars, {line_count:,} lines)"
                        )
                    else:
                        console.print(f"[red]✗[/red] Playwright also failed for {short_title}")

                    result_tabs_with_html.append((tab, html))

        # Step 3: Report final stats
        success_count = sum(1 for _, html in result_tabs_with_html if html)
        failure_count = len(tabs) - success_count

        if success_count == len(tabs):
            console.print(
                f"[bold green]Successfully extracted HTML from all {len(tabs)} tabs![/bold green]"
            )
        else:
            console.print(
                f"[bold yellow]Extracted HTML from {success_count}/{len(tabs)} tabs ({failure_count} failed)[/bold yellow]"
            )

        return result_tabs_with_html
