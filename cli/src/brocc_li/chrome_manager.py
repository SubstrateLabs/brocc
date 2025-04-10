import asyncio
import os
from enum import Enum
from typing import Dict, List, NamedTuple, Optional, Tuple

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
    markdown: str = ""
    html: Optional[str] = None


class ChromeManager:
    """Manages the connection to a Chrome instance with remote debugging."""

    def __init__(self, auto_connect: bool = False):
        """
        Initialize the Chrome Manager.

        Args:
            auto_connect: If True, will automatically try to connect to Chrome
                         if a debug port is detected.
        """
        self._state: ChromeState = ChromeState(False, False)  # Initial state
        self._connected: bool = False
        self._auto_connect = auto_connect
        self._initialized = False

        # Don't initialize async state here - defer until an event loop is running

    async def _ensure_initialized(self):
        """Ensure async initialization has been performed"""
        if not self._initialized:
            await self._init_async(self._auto_connect)
            self._initialized = True

    async def _init_async(self, auto_connect: bool):
        """Initialize the state asynchronously"""
        self._state = await self._get_chrome_state()
        # Try auto-connect if configured and debug port is active
        if auto_connect and self._state.has_debug_port:
            await self._try_auto_connect(quiet=True)

    async def _try_auto_connect(self, quiet: bool = False) -> bool:
        """
        Attempt to automatically connect to Chrome with debug port.

        Args:
            quiet: If True, suppress most log output during connection

        Returns:
            bool: True if connection successful, False otherwise
        """
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
        # These functions are now async, so we can call them directly
        has_debug_port = await is_chrome_debug_port_active()
        is_running = has_debug_port or await is_chrome_process_running()
        return ChromeState(
            is_running=is_running,
            has_debug_port=has_debug_port,
        )

    async def _check_chrome_connection(self) -> bool:
        """Check if we can connect to Chrome via CDP."""
        # Directly use async function
        chrome_info = await get_chrome_info()
        return chrome_info["connected"]

    async def _get_chrome_version(self) -> str:
        """Get Chrome version from CDP."""
        # Directly use async function
        chrome_info = await get_chrome_info()
        return chrome_info["version"]

    @property
    def connected(self) -> bool:
        """Return whether we're connected to Chrome.

        Note: This is a non-async property for compatibility with existing code.
        """
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
        if self._auto_connect and self._state.has_debug_port and not self._connected:
            await self._try_auto_connect()
        return self._state

    async def test_connection(
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

    async def open_new_tab(self, url: str = "") -> bool:
        """
        Open a new tab with the given URL.

        Returns:
            bool: True if successful, False otherwise
        """
        await self._ensure_initialized()
        if not self._connected or not self._state.has_debug_port:
            logger.error("Not connected to Chrome. Cannot open new tab.")
            return False

        # Directly use async function
        result = await open_new_tab(url)
        if result:
            logger.success(f"Successfully opened new tab with URL: {url}")
        return result

    async def get_all_tabs(self) -> List[dict]:
        """
        Get information about all open tabs in Chrome using CDP HTTP API.

        Uses Chrome DevTools Protocol HTTP API to get detailed tab information including:
        - Title and URL
        - Tab IDs
        - Debug URLs

        Returns:
            List of dictionaries with detailed tab information
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

    async def get_tab_html(
        self, tab_id: str, cdp_only: bool = False
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Get the HTML content and the final URL from a specific tab using its ID.

        Uses a multi-strategy approach:
        1. Quick check with Chrome DevTools Protocol (fast but flaky)
        2. If CDP fails and cdp_only is False, fall back to Playwright (more robust)

        Args:
            tab_id: The ID of the tab to get HTML from
            cdp_only: If True, only try CDP method without Playwright fallback

        Returns:
            Tuple (html_content | None, final_url | None)
        """
        await self._ensure_initialized()
        # Refresh our state first to ensure we have the latest connection status
        self._state = await self._get_chrome_state()

        final_url: Optional[str] = None  # Keep track of the best URL we find

        if not self._state.has_debug_port:
            logger.error("Chrome debug port is not active. Cannot get tab HTML.")
            return None, None

        if not self._connected:
            # Try to establish connection first
            logger.warning("Not connected to Chrome. Attempting to connect...")
            if not await self.test_connection(quiet=True):
                logger.error("Failed to connect to Chrome. Cannot get tab HTML.")
                return None, None

        # Find the tab with the specified ID - directly use async function
        tabs = await get_tabs()
        tab = next((t for t in tabs if t.id == tab_id), None)

        # Get the URL from the initial tab info if available
        if tab:
            final_url = tab.url

        if not tab or not tab.webSocketDebuggerUrl:
            logger.error(f"Tab with ID {tab_id} not found or has no WebSocket URL")
            return None, final_url  # Return URL found so far

        # Strategy 1: Try CDP approach first
        logger.debug(f"Trying to get HTML from tab {tab_id} ({final_url}) via CDP")

        ws_url = tab.webSocketDebuggerUrl
        if not ws_url:
            logger.error(f"Tab with ID {tab_id} has no WebSocket URL")
            return None, final_url

        # Directly use async function which now returns (html, url)
        html, cdp_url = await get_tab_html_content(ws_url)
        if cdp_url:  # Update URL if CDP returned one
            final_url = cdp_url

        # Strategy 2: If CDP failed and we're not in CDP-only mode, try Playwright fallback
        if not html and not cdp_only:
            logger.debug(f"CDP failed for {final_url}, trying Playwright fallback for tab {tab_id}")
            try:
                # Import here to avoid circular imports
                from brocc_li.playwright_fallback import playwright_fallback

                # Fallback now returns (html, url)
                html, playwright_url = await playwright_fallback.get_html_from_tab(tab_id)
                if playwright_url:  # Update URL if Playwright returned one
                    final_url = playwright_url

                if html:
                    logger.debug(
                        f"Successfully retrieved HTML via Playwright fallback ({len(html)} chars) from {final_url}"
                    )
                else:
                    logger.warning(
                        f"Playwright fallback also failed for tab {tab_id} ({final_url})"
                    )
            except Exception as e:
                logger.error(f"Playwright fallback error for {final_url}: {e}")

        return html, final_url

    async def get_parallel_tab_html(
        self, tabs: List[dict]
    ) -> List[Tuple[dict, Optional[str], Optional[str]]]:
        """
        Efficiently get HTML content and final URLs from multiple tabs asynchronously.

        First tries CDP in parallel, then handles Playwright fallbacks concurrently.

        Args:
            tabs: List of tab dictionaries containing id and other info

        Returns:
            List of (tab_dict, html | None, final_url | None) tuples
        """
        await self._ensure_initialized()
        results: List[Tuple[dict, Optional[str], Optional[str]]] = []  # Explicitly type
        tabs_needing_fallback: List[dict] = []
        cdp_fetched_urls: Dict[str, str] = {}  # Store URLs found during CDP phase
        console = Console()

        if not tabs:
            return []

        # Log the start of the process
        console.print(f"[cyan]Starting HTML extraction for {len(tabs)} tabs...[/cyan]")

        # First phase: Process tabs with CDP in parallel using asyncio.gather, limited by semaphore
        console.print(
            f"[bold cyan]Phase 1: Parallel CDP extraction for {len(tabs)} tabs (max 5 concurrent)...[/bold cyan]"
        )

        semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent CDP tasks

        async def process_tab_with_cdp_async(tab):
            async with semaphore:  # Acquire semaphore before running
                tab_id = tab.get("id")
                title = tab.get("title", "Untitled")
                short_title = (title[:30] + "...") if len(title) > 30 else title

                console.print(f"[dim]CDP: Getting HTML for {short_title}...[/dim]")
                html: Optional[str] = None
                url: Optional[str] = tab.get("url")  # Start with the initial URL
                needs_fallback = True  # Assume fallback needed unless CDP succeeds

                try:
                    # Explicitly set cdp_only=True to skip fallback during initial phase
                    # This now returns (html, url)
                    html, url = await self.get_tab_html(tab_id, cdp_only=True)
                    needs_fallback = not bool(html)  # Fallback if HTML is None or empty

                except asyncio.TimeoutError:
                    console.print(f"[red]⌛[/red] CDP timed out for {short_title}")
                    # html remains None, url might be updated, needs_fallback remains True
                except Exception as e:  # Catch other potential errors during CDP
                    console.print(f"[red]✗[/red] CDP error for {short_title}: {e}")
                    # html remains None, url might be updated, needs_fallback remains True

                if needs_fallback:
                    console.print(
                        f"[yellow]CDP failed for {short_title} - queuing fallback[/yellow]"
                    )
                else:
                    char_count = len(html) if html else 0
                    line_count = html.count("\n") + 1 if html else 0
                    console.print(
                        f"[green]✓[/green] CDP success: {short_title} ({char_count:,} chars, {line_count:,} lines) from {url}"
                    )
                # Store the URL found by CDP, even if it failed, for potential use in fallback phase logging
                if tab_id and url:
                    cdp_fetched_urls[tab_id] = url

                return tab, html, url, needs_fallback

        # Process all tabs in parallel
        cdp_results = await asyncio.gather(*[process_tab_with_cdp_async(tab) for tab in tabs])

        # Process results
        for tab, html, url, needs_fallback in cdp_results:
            if needs_fallback:
                tabs_needing_fallback.append(tab)
                # Add result with None HTML for now, URL might be from CDP attempt
                results.append((tab, None, url))
            else:
                results.append((tab, html, url))

        # Phase 2: Process fallbacks concurrently using Playwright
        if tabs_needing_fallback:
            console.print(
                f"\n[bold cyan]Phase 2: Concurrent Playwright fallbacks for {len(tabs_needing_fallback)} tabs...[/bold cyan]"
            )

            try:
                # Import here to avoid circular imports
                from brocc_li.playwright_fallback import playwright_fallback
            except ImportError as e:
                logger.error(f"Failed to import Playwright fallback: {e}")
                # Return results obtained so far from CDP
                return results

            # Create tasks for each fallback
            fallback_tasks = []
            tab_map = {}  # Map task to original tab data
            for tab in tabs_needing_fallback:
                tab_id = tab.get("id")
                if tab_id:
                    title = tab.get("title", "Untitled")
                    short_title = (title[:30] + "...") if len(title) > 30 else title
                    console.print(f"[dim]Playwright: Queuing {short_title}...[/dim]")
                    # Create the async task which returns (html, url)
                    task = asyncio.create_task(playwright_fallback.get_html_from_tab(tab_id))
                    fallback_tasks.append(task)
                    tab_map[task] = tab  # Store original tab info associated with this task

            # Run all fallback tasks concurrently and gather results
            fallback_results = await asyncio.gather(*fallback_tasks, return_exceptions=True)

            # Process the results
            # We need to match results back to the `results` list entries added earlier
            for i, fallback_result in enumerate(fallback_results):
                task = fallback_tasks[i]
                tab = tab_map[task]  # Get original tab info
                tab_id = tab.get("id")
                title = tab.get("title", "Untitled")
                short_title = (title[:30] + "...") if len(title) > 30 else title

                # Find the corresponding entry in the main results list
                # Find the index in the *original* results list where the tab_id matches
                # And where HTML is currently None (indicating it needed fallback)
                target_idx = -1
                for idx, (res_tab, res_html, _) in enumerate(results):
                    if res_tab.get("id") == tab_id and res_html is None:
                        target_idx = idx
                        break

                if target_idx == -1:
                    logger.error(f"Could not find matching result entry for fallback tab {tab_id}")
                    continue  # Skip this result if we can't place it

                html: Optional[str] = None
                url: Optional[str] = results[target_idx][2]  # Start with URL from CDP phase if any

                if isinstance(fallback_result, Exception):
                    console.print(
                        f"[red]✗[/red] Playwright error for {short_title}: {fallback_result}"
                    )
                    # Keep html as None, url might be from CDP
                elif isinstance(fallback_result, tuple) and len(fallback_result) == 2:
                    fb_html, fb_url = fallback_result
                    if fb_url:
                        url = fb_url  # Update URL if Playwright found one

                    if fb_html:  # Successfully got non-empty HTML
                        html = fb_html  # Assign the fetched HTML
                        # Safely calculate length and lines using fb_html directly
                        char_count = len(fb_html)  # Use fb_html which is known str here
                        line_count = fb_html.count("\n") + 1  # Use fb_html here too
                        console.print(
                            f"[green]✓[/green] Playwright success: {short_title} ({char_count:,} chars, {line_count:,} lines) from {url}"
                        )
                    else:  # Playwright returned empty or None string
                        console.print(
                            f"[red]✗[/red] Playwright failed for {short_title} (returned empty/None) from {url}"
                        )
                        # Keep html as None
                else:  # Should not happen, but handle unexpected result types
                    console.print(
                        f"[red]✗[/red] Playwright returned unexpected result type for {short_title}: {type(fallback_result)}"
                    )
                    # Keep html as None

                # Update the specific entry in the results list
                results[target_idx] = (tab, html, url)

        # Report final stats
        success_count = sum(1 for _, html, _ in results if html)
        failure_count = len(tabs) - success_count

        # Get the current average processing time if available
        try:
            from brocc_li.playwright_fallback import get_current_time_estimate

            avg_time = get_current_time_estimate()
            time_info = f" (avg {avg_time:.2f}s/tab)"
        except ImportError:
            time_info = ""

        if success_count == len(tabs):
            console.print(
                f"[bold green]Successfully extracted HTML from all {len(tabs)} tabs!{time_info}[/bold green]"
            )
        else:
            console.print(
                f"[bold yellow]Extracted HTML from {success_count}/{len(tabs)} tabs ({failure_count} failed){time_info}[/bold yellow]"
            )

        return results
