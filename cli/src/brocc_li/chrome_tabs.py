import signal
import threading
import time
from typing import Callable, List, NamedTuple, Optional, Set

from brocc_li.chrome_cdp import get_chrome_info
from brocc_li.chrome_manager import ChromeManager, TabReference
from brocc_li.utils.logger import logger


class TabChangeEvent(NamedTuple):
    """Container for tab change events."""

    new_tabs: List[dict]
    closed_tabs: List[dict]
    navigated_tabs: List[dict]
    current_tabs: List[dict]


class ChromeTabs:
    """Handles monitoring Chrome tabs and detecting changes."""

    def __init__(self, chrome_manager: ChromeManager, check_interval: float = 2.0):
        """
        Initialize the tab monitor.

        Args:
            chrome_manager: ChromeManager instance to use for Chrome interactions
            check_interval: How often to check for tab changes, in seconds
        """
        self.chrome_manager = chrome_manager
        self.check_interval = check_interval
        self.previous_tab_refs: Set[TabReference] = set()
        self.last_tabs_check = 0
        self._monitoring = False
        self._monitor_thread = None
        self._on_change_callback = None

    def start_monitoring(
        self, on_change_callback: Optional[Callable[[TabChangeEvent], None]] = None
    ) -> bool:
        """
        Start monitoring tabs for changes.

        Args:
            on_change_callback: Optional callback function that receives TabChangeEvent objects
                                when tabs change

        Returns:
            bool: True if monitoring started successfully
        """
        if self._monitoring:
            logger.warning("Tab monitoring already running")
            return False

        # Store the callback
        self._on_change_callback = on_change_callback

        # Connect to Chrome if not already connected
        if not self.chrome_manager.connected:
            logger.info("Connecting to Chrome...")
            connected = self.chrome_manager.test_connection()
            if not connected:
                logger.error("Failed to connect to Chrome. Cannot monitor tabs.")
                return False

        # Get initial tabs
        logger.debug("Getting initial tabs...")
        initial_tabs = self.chrome_manager.get_all_tabs()
        filtered_initial_tabs = [
            tab for tab in initial_tabs if tab.get("url", "").startswith(("http://", "https://"))
        ]

        # Process initial tabs to get HTML content
        if filtered_initial_tabs:
            initial_tabs_with_html = self.chrome_manager.get_parallel_tab_html(
                filtered_initial_tabs
            )

            # Create references from the collected data
            self.previous_tab_refs = {
                TabReference(tab["id"], tab["url"], html)
                for tab, html in initial_tabs_with_html
                if "id" in tab and "url" in tab
            }

        # Start monitoring thread
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, name="chrome-tabs-monitor", daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Started monitoring {len(self.previous_tab_refs)} HTTP/HTTPS tabs.")
        return True

    def stop_monitoring(self) -> None:
        """Stop monitoring tabs for changes."""
        self._monitoring = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)
        logger.debug("Tab monitoring stopped.")

    def _monitor_loop(self) -> None:
        """Main monitoring loop that runs in a separate thread."""
        while self._monitoring:
            current_time = time.time()

            # Check connection status periodically
            if not self.chrome_manager.connected:
                logger.warning("Chrome connection lost. Attempting to reconnect...")
                connected = self.chrome_manager.test_connection()
                if connected:
                    logger.success("Reconnected to Chrome")
                    # Reset tab tracking after reconnect
                    self.previous_tab_refs = set()
                else:
                    logger.error("Failed to reconnect to Chrome")
                    self._monitoring = False
                    break

            # Periodically check for tab changes
            if current_time - self.last_tabs_check >= self.check_interval:
                try:
                    tabs = self.chrome_manager.get_all_tabs()
                    changed_tabs = self.process_tab_changes(tabs)

                    # Call the callback if registered
                    if self._on_change_callback and changed_tabs:
                        self._on_change_callback(changed_tabs)

                    self.last_tabs_check = current_time
                except Exception as e:
                    logger.error(f"Error monitoring tabs: {e}")

            # Sleep to prevent high CPU usage
            time.sleep(0.5)

    def process_tab_changes(self, current_tabs) -> Optional[TabChangeEvent]:
        """
        Process changes in tabs, including URL changes within existing tabs.

        Args:
            current_tabs: The list of current tabs from chrome_manager.get_all_tabs()

        Returns:
            TabChangeEvent if changes detected, None otherwise
        """
        # Filter for only HTTP/HTTPS URLs
        filtered_tabs = [
            tab for tab in current_tabs if tab.get("url", "").startswith(("http://", "https://"))
        ]

        # Find brand new tabs and URL changes to collect HTML for
        tabs_needing_html = []

        # Track current tabs (will add HTML later)
        current_tab_refs_temp = set()
        for tab in filtered_tabs:
            if "id" in tab and "url" in tab:
                current_tab_refs_temp.add(TabReference(tab["id"], tab["url"]))

        # Get current tab IDs to identify completely new or removed tabs
        current_tab_ids = {ref.id for ref in current_tab_refs_temp}
        previous_tab_ids = {ref.id for ref in self.previous_tab_refs}

        # Completely new tabs (new browser tabs)
        added_tab_ids = current_tab_ids - previous_tab_ids
        # Tabs that were closed
        removed_tab_ids = previous_tab_ids - current_tab_ids

        # Extract data for detecting navigation changes
        new_tabs = []
        navigated_tabs = []
        tabs_with_html = []

        # Find tabs that are new or have navigated
        for tab in filtered_tabs:
            tab_id = tab.get("id")
            tab_url = tab.get("url", "")

            if tab_id in added_tab_ids:
                # This is a completely new tab
                new_tabs.append(tab)
                tabs_needing_html.append(tab)
            else:
                # Check if existing tab has a new URL
                old_urls = [ref.url for ref in self.previous_tab_refs if ref.id == tab_id]
                if old_urls and old_urls[0] != tab_url:
                    # This is a navigation in an existing tab
                    # Add the old URL for reference
                    navigated_tab = {**tab, "old_url": old_urls[0]}
                    navigated_tabs.append(navigated_tab)
                    tabs_needing_html.append(tab)
                else:
                    # Tab hasn't changed, reuse the previous HTML
                    old_html = next(
                        (
                            ref.html
                            for ref in self.previous_tab_refs
                            if ref.id == tab_id and ref.url == tab_url
                        ),
                        "",
                    )
                    tabs_with_html.append((tab, old_html))

        # Get HTML content for new tabs or navigations
        if tabs_needing_html:
            # Use our parallel method to get HTML for all tabs needing it
            new_tabs_with_html = self.chrome_manager.get_parallel_tab_html(tabs_needing_html)
            # Add the new results to our full list
            tabs_with_html.extend(new_tabs_with_html)

        # Create references with HTML for current tabs
        current_tab_refs = set()
        for tab, html in tabs_with_html:
            current_tab_refs.add(TabReference(tab["id"], tab["url"], html))

        # Update our stored references
        self.previous_tab_refs = current_tab_refs

        # Extract data for removed tabs
        closed_tabs = [
            {"id": ref.id, "url": ref.url}
            for ref in self.previous_tab_refs
            if ref.id in removed_tab_ids
        ]

        # If nothing changed, return None
        if not new_tabs and not closed_tabs and not navigated_tabs:
            return None

        # Create and return the change event
        return TabChangeEvent(
            new_tabs=new_tabs,
            closed_tabs=closed_tabs,
            navigated_tabs=navigated_tabs,
            current_tabs=filtered_tabs,
        )

    def get_all_tabs_with_html(self) -> List[dict]:
        """
        Get all current tabs with their HTML content.

        Returns:
            List of tab dictionaries with HTML content added
        """
        tabs = self.chrome_manager.get_all_tabs()
        filtered_tabs = [
            tab for tab in tabs if tab.get("url", "").startswith(("http://", "https://"))
        ]

        tabs_with_html = self.chrome_manager.get_parallel_tab_html(filtered_tabs)

        # Convert to a list of dicts with HTML included
        result = []
        for tab, html in tabs_with_html:
            tab_with_html = dict(tab)
            tab_with_html["html"] = html
            result.append(tab_with_html)

        return result


def main() -> None:
    """Run the Chrome tab monitor as a standalone program."""
    from rich import box
    from rich.console import Console
    from rich.table import Table

    # Set up signal handlers for cleaner exit
    def signal_handler(sig, frame):
        logger.info("Tab monitor stopped by user.")
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    console = Console()

    # Create Chrome manager and tabs monitor
    manager = ChromeManager()
    tabs_monitor = ChromeTabs(manager)

    # Helper function to display a list of tabs in a table
    def display_tab_list(tabs_with_html, header, show_old_url=False, show_html_stats=False):
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

    # On tab change callback
    def on_tab_change(event):
        # Display completely new tabs if any
        if event.new_tabs:
            new_tabs_with_html = []
            for tab in event.new_tabs:
                html = next(
                    (ref.html for ref in tabs_monitor.previous_tab_refs if ref.id == tab.get("id")),
                    "",
                )
                new_tabs_with_html.append((tab, html))

            display_tab_list(
                new_tabs_with_html,
                "\n[bold green]+++ New Tabs:[/bold green]",
                show_html_stats=True,
            )
            console.print(f"[dim]Added {len(new_tabs_with_html)} new tab(s)[/dim]")

        # Display URL changes in existing tabs
        if event.navigated_tabs:
            navigated_tabs_with_html = []
            for tab in event.navigated_tabs:
                html = next(
                    (ref.html for ref in tabs_monitor.previous_tab_refs if ref.id == tab.get("id")),
                    "",
                )
                navigated_tabs_with_html.append((tab, html))

            display_tab_list(
                navigated_tabs_with_html,
                "\n[bold blue]+++ Navigation in Existing Tabs:[/bold blue]",
                show_old_url=True,
                show_html_stats=True,
            )
            console.print(
                f"[dim]Detected {len(navigated_tabs_with_html)} navigation(s) in existing tab(s)[/dim]"
            )

        # Display removed tabs if any
        if event.closed_tabs:
            console.print(f"\n[bold red]--- Removed {len(event.closed_tabs)} tab(s)[/bold red]")

    try:
        # Connect to Chrome and start monitoring
        if tabs_monitor.start_monitoring(on_tab_change):
            chrome_info = get_chrome_info()
            logger.success(f"Successfully connected to Chrome {chrome_info['version']}")

            # Get initial tabs to display
            tabs = manager.get_all_tabs()
            filtered_tabs = [
                tab for tab in tabs if tab.get("url", "").startswith(("http://", "https://"))
            ]

            # Process initial tabs to get HTML content
            if filtered_tabs:
                initial_tabs_with_html = manager.get_parallel_tab_html(filtered_tabs)

                # Display initial tabs in a table
                display_tab_list(
                    initial_tabs_with_html,
                    "\n[bold cyan]=== Current Open Tabs:[/bold cyan]",
                    show_html_stats=True,
                )
                console.print(f"[dim]Found {len(initial_tabs_with_html)} HTTP/HTTPS tabs[/dim]\n")

            logger.info("Monitoring Chrome tabs. Press Ctrl+C to exit...")

            # Keep the main thread alive until Ctrl+C
            try:
                while True:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                logger.info("Tab monitor stopped by user.")
        else:
            logger.error("Failed to start tab monitoring.")

    except KeyboardInterrupt:
        logger.info("Tab monitor stopped by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        # Stop monitoring and clean up resources
        tabs_monitor.stop_monitoring()

        # Clean up Playwright resources if we used them
        try:
            # Import here to avoid circular imports
            from brocc_li.playwright_fallback import playwright_fallback

            playwright_fallback.cleanup()
        except Exception as e:
            logger.debug(f"Error cleaning up Playwright resources: {e}")

        logger.debug("Tab monitor has exited.")


if __name__ == "__main__":
    main()
