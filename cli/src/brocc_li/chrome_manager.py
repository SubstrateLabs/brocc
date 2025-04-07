import json
import time
from collections.abc import Callable
from typing import List, NamedTuple

import requests
from rich import box
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

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


# Default confirmation function that uses Rich
def default_confirm(message: str, default: bool = True) -> bool:
    """Default confirmation function using Rich."""
    return Confirm.ask(message, default=default)


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
            if self._check_chrome_connection():
                self._connected = True
                if not quiet:
                    chrome_version = self._get_chrome_version()
                    logger.debug(f"Auto-connected to Chrome {chrome_version}")
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
        try:
            response = requests.get("http://localhost:9222/json/version", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def _get_chrome_version(self) -> str:
        """Get Chrome version from CDP."""
        try:
            response = requests.get("http://localhost:9222/json/version", timeout=2)
            if response.status_code == 200:
                data = response.json()
                return data.get("Browser", "Unknown")
            return "Unknown"
        except Exception:
            return "Unknown"

    @property
    def status_description(self) -> str:
        """Returns a human-readable description of the Chrome state."""
        self._state = self._get_chrome_state()
        if self._state.has_debug_port:
            return "Chrome is running and connected via debug port."
        elif self._state.is_running:
            return "Chrome is running, but the debug port is not active. Relaunch required."
        else:
            return "Chrome is not running. Launch required."

    @property
    def connected(self) -> bool:
        """Return whether we're connected to Chrome."""
        return self._connected and self._state.has_debug_port

    @property
    def connected_browser(self) -> bool:
        """
        Return whether we're connected to Chrome.

        Note: This is kept for backward compatibility.
        """
        return self.connected

    def refresh_state(self) -> ChromeState:
        """Refresh and return the current Chrome state."""
        self._state = self._get_chrome_state()
        # Try to auto-connect if configured and debug port is active
        if self._auto_connect and self._state.has_debug_port and not self._connected:
            self._try_auto_connect()
        return self._state

    def connect(
        self,
        confirm_fn: Callable[[str, bool], bool] | None = None,
        auto_confirm: bool = False,
        quiet: bool = False,
    ) -> bool:
        """
        Ensures Chrome is running with the debug port and connects to it.

        Handles launching or relaunching Chrome as needed, using the provided
        confirmation function or auto-confirming if specified.

        Args:
            confirm_fn: Custom confirmation function that takes a message and default value
                       and returns a boolean. If None, uses the default Rich confirm.
            auto_confirm: If True, bypass all confirmation prompts and proceed automatically.
            quiet: If True, suppress most logging output.

        Returns:
            A boolean indicating whether connection was successful.
        """

        # Use the provided confirm function or the default
        def make_confirm_function():
            def confirm_wrapper(msg, default=True):
                if auto_confirm:
                    return True
                else:
                    return confirm_fn(msg, default) if confirm_fn else default_confirm(msg, default)

            return confirm_wrapper

        confirm = make_confirm_function()

        self._state = self._get_chrome_state()

        # Check if we already have a connected browser
        if self._connected and self._state.has_debug_port:
            if not quiet:
                logger.debug("Already connected to Chrome browser")
            return True

        if self._state.has_debug_port:
            if not quiet:
                logger.debug("Chrome already running with debug port. Attempting to connect...")
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
                    logger.warning(
                        "Connection failed despite active debug port. Attempting relaunch."
                    )
                if not confirm("Connection failed. Quit existing Chrome and relaunch?", True):
                    if not quiet:
                        logger.error("Connection aborted by user.")
                    return False
                if not quit_chrome():
                    if not quiet:
                        logger.error("Failed to quit existing Chrome instance(s). Cannot proceed.")
                    return False
                # Fall through to launch logic

        elif self._state.is_running:
            if not quiet:
                logger.warning("Chrome is running without the debug port.")
            if not confirm("Quit existing Chrome and relaunch with debug port?", True):
                if not quiet:
                    logger.error("Relaunch aborted by user.")
                return False
            if not quit_chrome():
                if not quiet:
                    logger.error("Failed to quit existing Chrome instance(s). Cannot proceed.")
                return False
            # Fall through to launch logic

        else:
            if not quiet:
                logger.debug("Chrome is not running.")
            if not confirm("Launch Chrome with debug port?", True):
                if not quiet:
                    logger.error("Launch aborted by user.")
                return False
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

        try:
            # Use CDP HTTP API to create a new tab
            response = requests.get(
                "http://localhost:9222/json/new", params={"url": url}, timeout=5
            )
            if response.status_code == 200:
                logger.success(f"Successfully opened new tab with URL: {url}")
                return True
            else:
                logger.error(f"Failed to open URL {url}: HTTP {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to open URL {url}: {str(e)}")
            return False

    def disconnect(self) -> bool:
        """
        Disconnect from Chrome browser if connected.

        Returns:
            bool: True if disconnected or already not connected, False if error occurs.
        """
        if not self._connected:
            logger.debug("No active browser connection to disconnect")
            return True

        try:
            self._connected = False
            logger.debug("Successfully disconnected from Chrome")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from Chrome: {str(e)}")
            return False

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
        # Use direct HTTP request to Chrome DevTools API
        try:
            # Get list of tabs via Chrome DevTools HTTP API
            response = requests.get("http://localhost:9222/json/list", timeout=2)
            if response.status_code != 200:
                logger.error(f"Failed to get tabs: HTTP {response.status_code}")
                return []

            cdp_tabs_json = response.json()

            # Process each tab
            tabs = []
            for tab_info in cdp_tabs_json:
                # Only include actual tabs (type: page), not devtools, etc.
                if tab_info.get("type") == "page":
                    tab = {
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
                            import re

                            window_id_match = re.search(r"windowId=(\d+)", devtools_url)
                            if window_id_match:
                                tab["window_id"] = int(window_id_match.group(1))
                        except Exception as e:
                            logger.debug(f"Could not extract window ID: {e}")

                    tabs.append(tab)

            # Return tabs in the order we received them
            return tabs

        except requests.RequestException as e:
            logger.error(f"Failed to connect to Chrome DevTools API: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Chrome DevTools API response: {e}")
        except Exception as e:
            logger.error(f"Error getting tabs via Chrome DevTools API: {e}")

        # Return empty list if we couldn't get tabs
        return []


def main() -> None:
    import signal

    # Set up signal handlers for cleaner exit
    def signal_handler(sig, frame):
        logger.info("Chrome Manager stopped by user.")
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    manager = ChromeManager()
    logger.debug(f"Initial status: {manager.status_description}")

    last_tabs_check = 0
    tabs_check_interval = 2  # Check tabs every 2 seconds
    previous_tab_ids = set()  # Store IDs of previously seen tabs

    # Define the display_tabs function inline for debugging
    def display_tab_changes(current_tabs, prev_tab_ids):
        """Display only the changes in tabs since last check."""
        # Filter for only HTTP/HTTPS URLs
        filtered_tabs = [
            tab for tab in current_tabs if tab.get("url", "").startswith(("http://", "https://"))
        ]

        # Get current tab IDs
        current_tab_ids = {tab["id"] for tab in filtered_tabs if "id" in tab}

        # Calculate added and removed tabs
        added_tab_ids = current_tab_ids - prev_tab_ids
        removed_tab_ids = prev_tab_ids - current_tab_ids

        # If nothing changed, don't display anything
        if not added_tab_ids and not removed_tab_ids:
            return current_tab_ids

        console = Console()

        # Display added tabs if any
        if added_tab_ids:
            added_tabs = [tab for tab in filtered_tabs if tab.get("id") in added_tab_ids]

            table = Table(show_header=True, header_style="bold green", box=box.ROUNDED)

            # Add columns
            table.add_column("#", style="dim", width=4)
            table.add_column("Title", style="green")
            table.add_column("URL", style="blue")
            table.add_column("Tab ID", style="dim", width=10)

            # Display each added tab
            for i, tab in enumerate(added_tabs):
                # Format title and URL with truncation
                title = tab.get("title", "Untitled")
                title_display = (title[:60] + "...") if len(title) > 60 else title

                url = tab.get("url", "")
                url_display = (url[:60] + "...") if len(url) > 60 else url

                # Show a shortened tab ID
                tab_id = tab.get("id", "")
                if tab_id:
                    short_id = tab_id[:8] + "..." if len(tab_id) > 8 else tab_id
                else:
                    short_id = "-"

                # Add the row
                table.add_row(f"{i + 1}", title_display, url_display, short_id)

            console.print("\n[bold green]+++ New Tabs:[/bold green]")
            console.print(table)
            console.print(f"[dim]Added {len(added_tabs)} tab(s)[/dim]")

        # Display removed tabs if any
        if removed_tab_ids:
            console.print(f"\n[bold red]--- Removed {len(removed_tab_ids)} tab(s)[/bold red]")

        # Print summary
        console.print(f"[dim]Current HTTP/HTTPS tabs: {len(current_tab_ids)}[/dim]\n")

        # Return the current set of tab IDs for the next comparison
        return current_tab_ids

    try:
        # Connect to Chrome
        connected = manager.connect(auto_confirm=True)

        if connected:
            chrome_version = manager._get_chrome_version()
            logger.success(f"Successfully connected to Chrome {chrome_version}")

            # Get initial tabs
            initial_tabs = manager.get_all_tabs()
            filtered_initial_tabs = [
                tab
                for tab in initial_tabs
                if tab.get("url", "").startswith(("http://", "https://"))
            ]
            previous_tab_ids = {tab["id"] for tab in filtered_initial_tabs if "id" in tab}

            logger.info(
                f"Monitoring {len(previous_tab_ids)} HTTP/HTTPS tabs. Press Ctrl+C to exit..."
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
                connected = manager.connect(auto_confirm=True)
                if connected:
                    logger.success("Reconnected to Chrome")
                    # Reset tab tracking after reconnect
                    previous_tab_ids = set()
                else:
                    logger.error("Failed to reconnect to Chrome")
                    break

            # Periodically check and display open tabs
            if current_time - last_tabs_check >= tabs_check_interval:
                try:
                    tabs = manager.get_all_tabs()
                    previous_tab_ids = display_tab_changes(tabs, previous_tab_ids)
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
        # Clean up and log final status
        if manager.connected:
            try:
                logger.debug("Disconnecting from Chrome...")
                # Just disconnect from Chrome, don't quit the Chrome process
                manager.disconnect()
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")

        manager.refresh_state()
        logger.debug(f"Final status: {manager.status_description}")
        logger.debug("Chrome Manager has exited.")


if __name__ == "__main__":
    main()
