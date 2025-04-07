import time
from enum import Enum
from typing import List, NamedTuple, Set

from rich import box
from rich.console import Console
from rich.table import Table

from brocc_li.chrome_cdp import get_chrome_info, get_tab_html_content, get_tabs, open_new_tab
from brocc_li.utils.chrome import (
    is_chrome_debug_port_active,
    is_chrome_process_running,
    launch_chrome,
    quit_chrome,
)
from brocc_li.utils.logger import logger


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

    def get_tab_html(self, tab_id: str, timeout: int = 1) -> str:
        """
        Get the HTML content from a specific tab using its ID.

        Uses a multi-strategy approach:
        1. Quick check with Chrome DevTools Protocol (fast but fails on anti-bot sites)
        2. If CDP fails, fall back to Playwright (better for anti-bot sites)

        Args:
            tab_id: The ID of the tab to get HTML from
            timeout: Connection and command timeout in seconds

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
        html = get_tab_html_content(tab.webSocketDebuggerUrl, timeout=timeout)

        # Strategy 2: If CDP failed, try Playwright fallback
        if not html:
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


def main() -> None:
    import signal

    # Set up signal handlers for cleaner exit
    def signal_handler(sig, frame):
        logger.info("Chrome Manager stopped by user.")
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    manager = ChromeManager()
    status = manager.status_code
    logger.debug(f"Initial status: {status.name}")

    last_tabs_check = 0
    tabs_check_interval = 2  # Check tabs every 2 seconds

    # Track tabs by ID+URL+HTML instead of just ID+URL
    previous_tab_refs: Set[TabReference] = set()  # Store references of previously seen tabs

    # Define the display_tab_changes function inline for debugging
    def display_tab_changes(current_tabs, prev_tab_refs, chrome_manager):
        """Display changes in tabs, including URL changes within existing tabs."""
        # Filter for only HTTP/HTTPS URLs
        filtered_tabs = [
            tab for tab in current_tabs if tab.get("url", "").startswith(("http://", "https://"))
        ]

        # Prepare to collect HTML content for new tabs or navigation events
        tabs_with_html = []

        # Find brand new tabs and URL changes to collect HTML for
        tabs_needing_html = []

        # Track current tabs (will add HTML later)
        current_tab_refs_temp = set()
        for tab in filtered_tabs:
            if "id" in tab and "url" in tab:
                current_tab_refs_temp.add(TabReference(tab["id"], tab["url"]))

        # Get current tab IDs to identify completely new or removed tabs
        current_tab_ids = {ref.id for ref in current_tab_refs_temp}
        previous_tab_ids = {ref.id for ref in prev_tab_refs}

        # Completely new tabs (new browser tabs)
        added_tab_ids = current_tab_ids - previous_tab_ids
        # Tabs that were closed
        removed_tab_ids = previous_tab_ids - current_tab_ids

        # Find tabs that are new or have navigated
        for tab in filtered_tabs:
            tab_id = tab.get("id")
            tab_url = tab.get("url", "")

            if tab_id in added_tab_ids:
                # This is a completely new tab
                tabs_needing_html.append(tab)
            else:
                # Check if existing tab has a new URL
                old_urls = [ref.url for ref in prev_tab_refs if ref.id == tab_id]
                if old_urls and old_urls[0] != tab_url:
                    # This is a navigation in an existing tab
                    tabs_needing_html.append(tab)
                else:
                    # Tab hasn't changed, reuse the previous HTML
                    old_html = next(
                        (
                            ref.html
                            for ref in prev_tab_refs
                            if ref.id == tab_id and ref.url == tab_url
                        ),
                        "",
                    )
                    tabs_with_html.append((tab, old_html))

        # Get HTML content for new tabs or navigations
        console = Console()
        if tabs_needing_html:
            console.print("\n[bold cyan]Fetching HTML for new/changed tabs...[/bold cyan]")

        for i, tab in enumerate(tabs_needing_html):
            tab_id = tab.get("id")
            tab_title = tab.get("title", "Untitled")
            short_title = (tab_title[:30] + "...") if len(tab_title) > 30 else tab_title

            # Show progress
            console.print(
                f"[dim]Getting HTML for tab {i + 1}/{len(tabs_needing_html)}: {short_title}[/dim]"
            )

            # Get HTML content via ChromeManager with short timeout for faster loading
            html = chrome_manager.get_tab_html(tab_id, timeout=1)
            tabs_with_html.append((tab, html))

            # Show result
            if html:
                char_count = len(html)
                line_count = html.count("\n") + 1
                console.print(
                    f"[green]✓[/green] Got HTML ({char_count:,} chars, {line_count:,} lines)"
                )
            else:
                console.print("[red]✗[/red] Failed to get HTML")

        # Create references with HTML for current tabs
        current_tab_refs = set()
        for tab, html in tabs_with_html:
            current_tab_refs.add(TabReference(tab["id"], tab["url"], html))

        # If nothing changed, don't display anything
        if (
            not added_tab_ids
            and not removed_tab_ids
            and not [t for t, _ in tabs_with_html if t.get("id") not in added_tab_ids]
        ):
            return current_tab_refs

        # Display completely new tabs if any
        if added_tab_ids:
            new_tabs_with_html = [
                (tab, html) for tab, html in tabs_with_html if tab.get("id") in added_tab_ids
            ]
            display_tab_list(
                console,
                new_tabs_with_html,
                "\n[bold green]+++ New Tabs:[/bold green]",
                show_html_stats=True,
            )
            console.print(f"[dim]Added {len(new_tabs_with_html)} new tab(s)[/dim]")

        # Display URL changes in existing tabs
        url_changes_with_html = []
        for tab, html in tabs_with_html:
            tab_id = tab.get("id")
            if tab_id and tab_id not in added_tab_ids:  # Not a brand new tab
                current_url = tab.get("url", "")
                # Check if this tab had a different URL before
                old_urls = [ref.url for ref in prev_tab_refs if ref.id == tab_id]
                if old_urls and old_urls[0] != current_url:
                    # This tab has navigated to a new URL
                    url_changes_with_html.append(
                        (
                            {
                                "id": tab_id,
                                "title": tab.get("title", "Untitled"),
                                "url": current_url,
                                "old_url": old_urls[0],
                                **tab,
                            },
                            html,
                        )
                    )

        if url_changes_with_html:
            display_tab_list(
                console,
                url_changes_with_html,
                "\n[bold blue]+++ Navigation in Existing Tabs:[/bold blue]",
                show_old_url=True,
                show_html_stats=True,
            )
            console.print(
                f"[dim]Detected {len(url_changes_with_html)} navigation(s) in existing tab(s)[/dim]"
            )

        # Display removed tabs if any
        if removed_tab_ids:
            console.print(f"\n[bold red]--- Removed {len(removed_tab_ids)} tab(s)[/bold red]")

        # Return the current set of tab references for the next comparison
        return current_tab_refs

    # Helper function to display a list of tabs in a table
    def display_tab_list(
        console, tabs_with_html, header, show_old_url=False, show_html_stats=False
    ):
        """Display a list of tabs in a table."""
        if not tabs_with_html:
            return

        table = Table(show_header=True, header_style="bold green", box=box.ROUNDED)

        # Add columns
        table.add_column("#", style="dim", width=4)
        table.add_column("Title", style="green")
        table.add_column("URL", style="blue")
        if show_old_url:
            table.add_column("Previous URL", style="dim")
        if show_html_stats:
            table.add_column("HTML Size", style="cyan")
            table.add_column("Lines", style="cyan")
        table.add_column("Tab ID", style="dim", width=10)

        # Display each tab
        for i, (tab, html) in enumerate(tabs_with_html):
            # Format title and URL with truncation
            title = tab.get("title", "Untitled")
            title_display = (title[:60] + "...") if len(title) > 60 else title

            url = tab.get("url", "")
            url_display = (url[:60] + "...") if len(url) > 60 else url

            # Show the old URL if requested and available
            old_url_display = ""
            if show_old_url:
                old_url = tab.get("old_url", "")
                old_url_display = (old_url[:60] + "...") if len(old_url) > 60 else old_url

            # Calculate HTML stats if requested
            html_stats_display = []
            if show_html_stats:
                if html:
                    char_count = len(html)
                    line_count = html.count("\n") + 1 if html else 0
                    html_stats_display = [
                        f"{char_count:,} chars",  # Format with thousands separator
                        f"{line_count:,}",
                    ]
                else:
                    html_stats_display = [
                        "[dim]N/A[/dim]",  # Indicate HTML wasn't available
                        "[dim]N/A[/dim]",
                    ]

            # Show a shortened tab ID
            tab_id = tab.get("id", "")
            if tab_id:
                short_id = tab_id[:8] + "..." if len(tab_id) > 8 else tab_id
            else:
                short_id = "-"

            # Add the row with all the requested columns
            row = [f"{i + 1}", title_display, url_display]
            if show_old_url:
                row.append(old_url_display)
            if show_html_stats:
                row.extend(html_stats_display)
            row.append(short_id)

            table.add_row(*row)

        console.print(header)
        console.print(table)

    try:
        # Connect to Chrome
        connected = manager.test_connection()

        if connected:
            chrome_info = get_chrome_info()
            logger.success(f"Successfully connected to Chrome {chrome_info['version']}")

            # Ensure connection is fully established before fetching HTML
            time.sleep(2)  # Give Chrome a moment to fully initialize

            if not manager.connected:
                logger.warning("Connection to Chrome appears unstable. Retrying connection...")
                connected = manager.test_connection()
                if not connected:
                    logger.error("Could not establish a stable connection to Chrome.")
                    return

            # Get initial tabs
            initial_tabs = manager.get_all_tabs()
            filtered_initial_tabs = [
                tab
                for tab in initial_tabs
                if tab.get("url", "").startswith(("http://", "https://"))
            ]

            # Create initial tab references with HTML content
            initial_tabs_with_html = []

            # Add progress reporting
            console = Console()
            if filtered_initial_tabs:
                console.print("\n[bold cyan]Fetching HTML content from tabs...[/bold cyan]")

            for idx, tab in enumerate(filtered_initial_tabs):
                tab_id = tab.get("id")
                if tab_id:
                    title = tab.get("title", "Untitled")
                    short_title = (title[:30] + "...") if len(title) > 30 else title

                    # Show progress
                    console.print(
                        f"[dim]Getting HTML for tab {idx + 1}/{len(filtered_initial_tabs)}: {short_title}[/dim]"
                    )

                    # Get HTML with short timeout for faster loading
                    html = manager.get_tab_html(
                        tab_id, timeout=1
                    )  # Use shorter timeout to quickly fallback to Playwright
                    initial_tabs_with_html.append((tab, html))

                    # Show result (success/failure)
                    if html:
                        char_count = len(html)
                        line_count = html.count("\n") + 1
                        console.print(
                            f"[green]✓[/green] Got HTML ({char_count:,} chars, {line_count:,} lines)"
                        )
                    else:
                        console.print("[red]✗[/red] Failed to get HTML")

            # Create references from the collected data
            previous_tab_refs = {
                TabReference(tab["id"], tab["url"], html)
                for tab, html in initial_tabs_with_html
                if "id" in tab and "url" in tab
            }

            # Display initial tabs in a table
            console = Console()
            display_tab_list(
                console,
                initial_tabs_with_html,
                "\n[bold cyan]=== Current Open Tabs:[/bold cyan]",
                show_html_stats=True,
            )
            console.print(f"[dim]Found {len(previous_tab_refs)} HTTP/HTTPS tabs[/dim]\n")

            logger.info(
                f"Monitoring {len(previous_tab_refs)} HTTP/HTTPS tabs. Press Ctrl+C to exit..."
            )
        else:
            logger.error("Failed to connect to Chrome.")
            return

        # Keep the process running until Ctrl+C
        while True:
            current_time = time.time()

            # Check connection status periodically
            if not manager.connected:
                logger.warning("Chrome connection lost. Attempting to reconnect...")
                connected = manager.test_connection()
                if connected:
                    logger.success("Reconnected to Chrome")
                    # Reset tab tracking after reconnect
                    previous_tab_refs = set()
                else:
                    logger.error("Failed to reconnect to Chrome")
                    break

            # Periodically check and display open tabs
            if current_time - last_tabs_check >= tabs_check_interval:
                try:
                    tabs = manager.get_all_tabs()
                    previous_tab_refs = display_tab_changes(tabs, previous_tab_refs, manager)
                    last_tabs_check = current_time
                except Exception as e:
                    logger.error(f"Error getting or displaying tabs: {e}")

            # Sleep to prevent high CPU usage
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Chrome Manager stopped by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        # Clean up resources
        try:
            # Clean up Playwright resources if we used them
            from brocc_li.playwright_fallback import playwright_fallback

            playwright_fallback.cleanup()
        except Exception as e:
            logger.debug(f"Error cleaning up Playwright resources: {e}")

        # Log final status
        manager.refresh_state()
        status_code = manager.status_code
        logger.debug(f"Final status: {status_code.name}")
        logger.debug("Chrome Manager has exited.")


if __name__ == "__main__":
    main()
