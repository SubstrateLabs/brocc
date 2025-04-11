import asyncio
import shutil
import signal
import time
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, NamedTuple, Optional, Set, Union

from rich.console import Console
from rich.markup import escape

from brocc_li.chrome_cdp import ChromeTab, get_chrome_info, get_tabs, monitor_user_interactions
from brocc_li.chrome_manager import ChromeManager
from brocc_li.html_to_md import html_to_md
from brocc_li.merge_md import MergeResultType, merge_md
from brocc_li.utils.logger import logger
from brocc_li.utils.slugify import slugify


class TabReference(NamedTuple):
    id: str
    url: str
    markdown: str
    html: Optional[str] = None
    title: Optional[str] = None


class TabChangeEvent(NamedTuple):
    new_tabs: List[dict]
    closed_tabs: List[dict]
    navigated_tabs: List[dict]
    current_tabs: List[dict]


TabChangeCallback = Union[
    Callable[[TabChangeEvent], None],  # Sync callback
    Callable[[TabChangeEvent], Awaitable[None]],  # Async callback
]

PollingTabChangeCallback = Union[
    Callable[[TabChangeEvent], None],
    Callable[[TabChangeEvent], Awaitable[None]],
]

InteractionTabUpdateCallback = Union[
    Callable[[TabReference], None],
    Callable[[TabReference], Awaitable[None]],
]

DEBOUNCE_DELAY_SECONDS = 0.75  # Time to wait after last interaction before fetching


class ChromeTabs:
    """Handles monitoring Chrome tabs and detecting changes."""

    def __init__(self, chrome_manager: ChromeManager, check_interval: float = 2.0):
        """
        Args:
            chrome_manager: ChromeManager instance to use for Chrome interactions
            check_interval: How often to check for tab changes, in seconds
        """
        self.chrome_manager = chrome_manager
        self.check_interval = check_interval
        self.previous_tab_refs: Set[TabReference] = set()
        self.last_tabs_check = 0
        self._monitoring = False
        self._on_polling_change_callback: Optional[PollingTabChangeCallback] = None
        self._on_interaction_update_callback: Optional[InteractionTabUpdateCallback] = None
        self._monitor_task = None  # Task for the main polling loop

        # State for interaction monitoring and debouncing
        self._interaction_monitors: Dict[str, asyncio.Task] = {}  # tab_id -> Task
        self._debounce_timers: Dict[str, asyncio.TimerHandle] = {}  # tab_id -> TimerHandle
        self._interaction_fetch_tasks: Dict[str, asyncio.Task] = {}  # tab_id -> Task fetching HTML

    async def start_monitoring(
        self,
        on_polling_change_callback: PollingTabChangeCallback,
        on_interaction_update_callback: InteractionTabUpdateCallback,
    ) -> bool:
        """
        Start monitoring tabs for changes asynchronously, including interaction events.

        Args:
            on_polling_change_callback: Callback for new/closed/navigated tabs detected by polling.
            on_interaction_update_callback: Callback for single tab content updates triggered by interaction.

        Returns:
            bool: True if monitoring started successfully
        """
        if self._monitoring:
            logger.warning("Tab monitoring already running")
            return False

        # Store the callbacks
        self._on_polling_change_callback = on_polling_change_callback
        self._on_interaction_update_callback = on_interaction_update_callback

        # Connect to Chrome if not already connected
        if not self.chrome_manager.connected:
            logger.info("Connecting to Chrome...")
            # Use test_connection which handles launching/relaunching
            connected = await self.chrome_manager.ensure_connection()
            if not connected:
                logger.error("Failed to connect to Chrome. Cannot monitor tabs.")
                return False

        # Get initial tabs and their HTML
        logger.debug("Getting initial tabs...")
        initial_cdp_tabs: List[ChromeTab] = await get_tabs()  # Get full ChromeTab objects

        # Filter for HTTP/HTTPS and valid websocket URLs
        filtered_initial_tabs_with_ws = [
            tab
            for tab in initial_cdp_tabs
            if tab.url.startswith(("http://", "https://")) and tab.webSocketDebuggerUrl
        ]
        logger.debug(
            f"Found {len(filtered_initial_tabs_with_ws)} initial HTTP/HTTPS tabs with WebSocket URLs."
        )

        # Get initial HTML content in parallel
        if filtered_initial_tabs_with_ws:
            # Convert ChromeTab models to simple dicts for get_parallel_tab_html if needed
            # (Assuming get_parallel_tab_html expects dicts for now)
            initial_tabs_dict = [tab.model_dump() for tab in filtered_initial_tabs_with_ws]

            initial_tabs_with_html = await self.chrome_manager.get_html_for_tabs(initial_tabs_dict)

            # Convert HTML to MD and create references
            logger.debug(
                f"Converting initial HTML to Markdown for {len(initial_tabs_with_html)} tabs..."
            )
            self.previous_tab_refs = set()
            for tab_dict, html, fetched_url in initial_tabs_with_html:
                tab_id = tab_dict.get("id")
                # Use the URL returned by the fetch, fallback to dict URL if needed
                tab_url = fetched_url or tab_dict.get("url")
                if tab_id and tab_url:
                    original_html = html  # Store original HTML
                    if html:
                        # Pass the fetched URL to html_to_md
                        markdown = html_to_md(html, tab_url)
                        if markdown is None:  # Handle conversion failure
                            logger.warning(
                                f"Initial Markdown conversion failed for {tab_url}, storing empty."
                            )
                            markdown = ""
                    else:
                        markdown = ""  # No HTML, empty MD
                    self.previous_tab_refs.add(
                        TabReference(
                            id=tab_id,
                            url=tab_url,
                            markdown=markdown,
                            html=original_html,
                            title=tab_dict.get("title"),
                        )
                    )

            logger.info(f"Processed initial Markdown for {len(self.previous_tab_refs)} tabs.")

            # Start interaction monitors for these initial tabs
            initial_ws_urls = {
                tab.id: tab.webSocketDebuggerUrl
                for tab in filtered_initial_tabs_with_ws
                if tab.webSocketDebuggerUrl
            }
            for tab_ref in self.previous_tab_refs:
                ws_url = initial_ws_urls.get(tab_ref.id)
                if ws_url:
                    self._start_interaction_monitor(tab_ref.id, ws_url)
                else:
                    logger.warning(
                        f"Missing WebSocket URL for initial tab {tab_ref.id}, cannot monitor interactions."
                    )

        # Start the main polling monitoring task
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(
            f"Started async monitoring. Polling interval: {self.check_interval}s. Interaction monitoring active for {len(self._interaction_monitors)} tabs."
        )
        return True

    async def stop_monitoring(self) -> None:
        """Stop monitoring tabs for changes (async version), including interaction monitors."""
        if not self._monitoring:
            logger.debug("Monitoring already stopped.")
            return

        self._monitoring = False  # Signal loops to stop

        # Stop interaction monitors first
        logger.debug(f"Stopping {len(self._interaction_monitors)} interaction monitors...")
        await self._stop_all_interaction_monitors()

        # Stop the main polling loop task
        if self._monitor_task and not self._monitor_task.done():
            logger.debug("Stopping main polling task...")
            self._monitor_task.cancel()
            try:
                await asyncio.wait_for(self._monitor_task, timeout=2.0)
                logger.debug("Main polling task cancelled successfully.")
            except asyncio.TimeoutError:
                logger.warning("Main polling task did not stop within timeout.")
            except asyncio.CancelledError:
                logger.debug("Main polling task cancelled as expected.")
            except Exception as e:
                logger.error(f"Error stopping main polling task: {e}")

        # Clear state
        self.previous_tab_refs = set()
        self._on_polling_change_callback = None
        self._on_interaction_update_callback = None
        self._monitor_task = None

        logger.debug("Async tab monitoring stopped completely.")

    # --- Interaction Monitoring Logic ---

    def _start_interaction_monitor(self, tab_id: str, ws_url: str):
        """Starts the background task to monitor interactions for a single tab."""
        if tab_id in self._interaction_monitors:
            logger.warning(f"Interaction monitor already running for tab {tab_id}")
            return

        logger.debug(f"Starting interaction monitor for tab {tab_id}")
        task = asyncio.create_task(self._run_interaction_monitor_for_tab(tab_id, ws_url))
        self._interaction_monitors[tab_id] = task
        # Add a callback to remove the task from the dict when it's done
        task.add_done_callback(lambda _task: self._interaction_monitors.pop(tab_id, None))

    async def _run_interaction_monitor_for_tab(self, tab_id: str, ws_url: str):
        """The actual monitoring loop for a single tab's interactions."""
        try:
            async for event in monitor_user_interactions(ws_url):
                # Check if monitoring is still active overall and specifically for this tab
                if not self._monitoring or tab_id not in self._interaction_monitors:
                    logger.debug(f"Interaction monitoring stopped for tab {tab_id}, exiting loop.")
                    break
                # Process the received click/scroll event
                await self._handle_interaction_event(tab_id, event.get("type"))
        except Exception as e:
            logger.error(
                f"Error in interaction monitor for tab {tab_id} ({ws_url}): {e}", exc_info=True
            )
        finally:
            logger.debug(f"Interaction monitor task finished for tab {tab_id}")
            # Ensure cleanup happens even if the loop exits unexpectedly
            self._stop_interaction_monitor(tab_id)  # Call stop to clean up timers/fetch tasks

    async def _handle_interaction_event(self, tab_id: str, event_type: Optional[str]):
        """Handles a detected interaction event (click/scroll) by resetting the debounce timer."""
        if not event_type:
            return

        logger.debug(
            f"Detected interaction '{event_type}' in tab {tab_id}. Resetting debounce timer."
        )

        # Cancel existing timer for this tab, if any
        if tab_id in self._debounce_timers:
            self._debounce_timers[tab_id].cancel()

        # Schedule the debounced fetch function to run after the delay
        loop = asyncio.get_running_loop()
        self._debounce_timers[tab_id] = loop.call_later(
            DEBOUNCE_DELAY_SECONDS,
            # Use lambda to create a coroutine task when the timer fires
            lambda: asyncio.create_task(self._trigger_debounced_fetch(tab_id)),
        )

    async def _trigger_debounced_fetch(self, tab_id: str):
        """Callback function executed after the debounce delay. Starts the HTML fetch task."""
        # Timer has fired, remove it from tracking
        self._debounce_timers.pop(tab_id, None)

        # Prevent concurrent fetches for the same tab initiated by interactions
        if tab_id in self._interaction_fetch_tasks:
            logger.debug(f"Fetch already in progress for tab {tab_id}, skipping debounced trigger.")
            return

        logger.info(f"Debounce finished for tab {tab_id}. Triggering HTML content fetch.")

        # Run the fetch in the background
        fetch_task = asyncio.create_task(self._fetch_and_update_tab_content(tab_id))
        self._interaction_fetch_tasks[tab_id] = fetch_task

        # Ensure the task is removed from the tracking dict once it completes
        fetch_task.add_done_callback(lambda _task: self._interaction_fetch_tasks.pop(tab_id, None))

    async def _fetch_and_update_tab_content(self, tab_id: str):
        """Fetches HTML for a specific tab, converts to MD, updates internal state, and logs."""
        try:
            logger.debug(f"Fetching latest HTML and URL for tab {tab_id} due to interaction...")
            # Fetch HTML and the *current* URL for the specific tab
            html_content, current_url = await self.chrome_manager.get_tab_html(tab_id)

            if not current_url:
                logger.warning(
                    f"Could not determine URL for tab {tab_id} during fetch. Aborting update."
                )
                return

            new_markdown = None
            original_html = html_content
            if not html_content:
                logger.warning(
                    f"Failed to fetch HTML for tab {tab_id} ({current_url}) after interaction."
                )
                # If HTML fetch failed, but we got a URL, maybe still proceed with merge logic?
                # Let's assume failure means we treat new_markdown as None
            else:
                # Convert fetched HTML to Markdown using the FETCHED URL
                logger.debug(
                    f"Converting HTML to Markdown for interacted tab {tab_id} ({current_url})..."
                )
                new_markdown = html_to_md(html_content, current_url)  # Use FETCHED URL
                # html_to_md returns None on error or empty content

            # Find the existing reference for this tab (still needed for old_markdown)
            current_ref = next((ref for ref in self.previous_tab_refs if ref.id == tab_id), None)
            old_markdown = current_ref.markdown if current_ref else None
            old_title = current_ref.title if current_ref else None

            # Use merge_md to combine old and new markdown
            merge_result = merge_md(old_markdown, new_markdown)
            merged_content = merge_result.content

            # Check if the merged content is different from the previously stored markdown
            content_changed = merged_content != old_markdown

            # Determine the URL to use for the *new* reference. Always use the freshly fetched URL.
            url_for_new_ref = current_url
            display_url = (
                url_for_new_ref[:80] + "..." if len(url_for_new_ref) > 80 else url_for_new_ref
            )

            if current_ref and content_changed:
                # Log based on merge type, using the NEW url
                if merge_result.type == MergeResultType.MERGED:
                    logger.success(
                        f"Interaction MERGED content update for tab {tab_id} ({display_url}). Updating stored Markdown."
                    )
                elif merge_result.type == MergeResultType.KEPT_NEW:
                    logger.success(
                        f"Interaction detected significant change (KEPT_NEW) for tab {tab_id} ({display_url}). Updating stored Markdown."
                    )
                else:  # KEPT_EMPTY
                    logger.success(
                        f"Interaction resulted in empty content (KEPT_EMPTY) for tab {tab_id} ({display_url}). Updating stored Markdown."
                    )

                # Create the new reference using the FETCHED URL
                new_ref = TabReference(
                    id=tab_id,
                    url=url_for_new_ref,
                    markdown=merged_content or "",
                    html=original_html,
                    title=old_title,
                )
                # Update the set: remove old, add new
                # Use discard() for safety, in case the ref was already removed by polling
                self.previous_tab_refs.discard(current_ref)
                self.previous_tab_refs.add(new_ref)

                # Trigger the interaction update callback if provided
                if self._on_interaction_update_callback:
                    logger.debug(
                        f"Calling interaction update callback for tab {tab_id} with URL {display_url}"
                    )
                    try:
                        if asyncio.iscoroutinefunction(self._on_interaction_update_callback):
                            await self._on_interaction_update_callback(new_ref)
                        else:
                            self._on_interaction_update_callback(new_ref)
                    except Exception as cb_err:
                        logger.error(
                            f"Error in interaction update callback for tab {tab_id}: {cb_err}",
                            exc_info=True,
                        )
            elif not current_ref:
                # Should not happen ideally if interaction is monitored, but handle it.
                logger.warning(
                    f"Tab {tab_id} not found in previous_tab_refs during interaction update. Storing fetched content for URL {display_url}."
                )
                # Store the newly fetched content (or merged) using the FETCHED URL
                new_ref = TabReference(
                    id=tab_id,
                    url=url_for_new_ref,
                    markdown=merged_content or "",
                    html=original_html,
                    title=None,
                )
                self.previous_tab_refs.add(new_ref)
                # Optionally trigger callback here too?
                # Let's trigger it if we just added it and there's a callback.
                if self._on_interaction_update_callback:
                    logger.debug(
                        f"Calling interaction update callback for newly tracked tab {tab_id} with URL {display_url}"
                    )
                    try:
                        if asyncio.iscoroutinefunction(self._on_interaction_update_callback):
                            await self._on_interaction_update_callback(new_ref)
                        else:
                            self._on_interaction_update_callback(new_ref)
                    except Exception as cb_err:
                        logger.error(
                            f"Error in interaction update callback for tab {tab_id}: {cb_err}",
                            exc_info=True,
                        )
            else:  # current_ref exists but content_changed is False
                # In that case, the url_for_new_ref might differ from current_ref.url.
                # Always use url_for_new_ref for logging and saving.
                logger.debug(
                    f"Interaction detected in tab {tab_id} ({display_url}), but merged Markdown content hasn't changed from previous state."
                )

        except Exception as e:
            logger.error(
                f"Error fetching/updating tab {tab_id} after interaction: {e}", exc_info=True
            )

    def _stop_interaction_monitor(self, tab_id: str):
        """Stops monitoring interactions and cleans up resources for a single tab."""
        logger.debug(f"Stopping interaction monitor and cleaning up for tab {tab_id}...")

        # Cancel and remove the main interaction monitor task
        monitor_task = self._interaction_monitors.pop(tab_id, None)
        if monitor_task and not monitor_task.done():
            monitor_task.cancel()
            # logger.debug(f"Cancelled interaction monitor task for tab {tab_id}")

        # Cancel and remove the debounce timer
        timer = self._debounce_timers.pop(tab_id, None)
        if timer:
            timer.cancel()
            # logger.debug(f"Cancelled debounce timer for tab {tab_id}")

        # Cancel and remove any ongoing fetch task triggered by interaction
        fetch_task = self._interaction_fetch_tasks.pop(tab_id, None)
        if fetch_task and not fetch_task.done():
            fetch_task.cancel()
            # logger.debug(f"Cancelled interaction fetch task for tab {tab_id}")

    async def _stop_all_interaction_monitors(self):
        """Stops all interaction monitors and associated tasks/timers."""
        if (
            not self._interaction_monitors
            and not self._debounce_timers
            and not self._interaction_fetch_tasks
        ):
            logger.debug("No active interaction monitors/timers/tasks to stop.")
            return

        logger.info(
            f"Stopping all interaction monitors ({len(self._interaction_monitors)}), timers ({len(self._debounce_timers)}), and fetch tasks ({len(self._interaction_fetch_tasks)})..."
        )

        # Get all unique tab IDs currently being tracked
        all_tab_ids = (
            set(self._interaction_monitors.keys())
            | set(self._debounce_timers.keys())
            | set(self._interaction_fetch_tasks.keys())
        )

        # Stop everything for each tab ID
        for tab_id in list(all_tab_ids):  # Iterate over a copy
            self._stop_interaction_monitor(tab_id)

        # Wait briefly for tasks to potentially cancel (optional)
        # await asyncio.sleep(0.1)

        # Clear the dictionaries just in case
        self._interaction_monitors.clear()
        self._debounce_timers.clear()
        self._interaction_fetch_tasks.clear()
        logger.debug("All interaction monitoring resources cleared.")

    # --- Polling Logic Modifications ---

    async def _monitor_loop(self) -> None:
        """Async version of the monitoring loop (handles polling)."""
        while self._monitoring:
            current_time = time.time()

            # Check connection status periodically
            if not self.chrome_manager.connected:
                logger.warning("Chrome connection lost. Attempting to reconnect...")
                # Stop existing monitors before attempting reconnect
                await self._stop_all_interaction_monitors()
                connected = await self.chrome_manager.ensure_connection()
                if connected:
                    logger.success("Reconnected to Chrome. Will rescan tabs on next interval.")
                    # Reset tab tracking - will be repopulated by process_tab_changes
                    self.previous_tab_refs = set()
                    self.last_tabs_check = 0  # Force immediate check
                else:
                    logger.error("Failed to reconnect to Chrome. Stopping monitoring.")
                    self._monitoring = False  # Stop the loop
                    break  # Exit loop immediately

            # Periodically check for tab changes via polling
            if current_time - self.last_tabs_check >= self.check_interval:
                try:
                    # Use get_tabs to get full ChromeTab objects including ws urls
                    current_cdp_tabs: List[ChromeTab] = await get_tabs()
                    # Pass the full objects to process_tab_changes
                    changed_tabs_event = await self.process_tab_changes(current_cdp_tabs)

                    # Call the main callback if registered and changes were detected by polling
                    if self._on_polling_change_callback and changed_tabs_event:
                        logger.info(
                            "Polling detected tab changes (new/closed/navigated). Notifying callback."
                        )
                        if asyncio.iscoroutinefunction(self._on_polling_change_callback):
                            await self._on_polling_change_callback(changed_tabs_event)
                        else:
                            self._on_polling_change_callback(changed_tabs_event)

                    self.last_tabs_check = current_time
                except Exception as e:
                    logger.error(f"Error during polling loop: {e}", exc_info=True)

            # Sleep briefly before next check
            await asyncio.sleep(0.5)  # Maintain a base loop responsiveness

    async def process_tab_changes(
        self, current_cdp_tabs: List[ChromeTab]
    ) -> Optional[TabChangeEvent]:
        """
        Process changes based on polled tabs, manage interaction monitors, and fetch HTML for polling-detected changes.

        Args:
            current_cdp_tabs: List of current ChromeTab objects from get_tabs()

        Returns:
            TabChangeEvent if polling detected new/closed/navigated tabs, None otherwise.
        """
        # Filter for only HTTP/HTTPS URLs and tabs with WebSocket URLs needed for monitoring
        filtered_tabs = [
            tab
            for tab in current_cdp_tabs
            if tab.url.startswith(("http://", "https://")) and tab.webSocketDebuggerUrl
        ]

        # --- Identify Changes & Manage Interaction Monitors ---

        current_tab_refs_map: Dict[str, TabReference] = {
            ref.id: ref for ref in self.previous_tab_refs
        }
        current_polled_tabs_map: Dict[str, ChromeTab] = {tab.id: tab for tab in filtered_tabs}

        current_tab_ids = set(current_polled_tabs_map.keys())
        previous_tab_ids = set(current_tab_refs_map.keys())

        added_tab_ids = current_tab_ids - previous_tab_ids
        removed_tab_ids = previous_tab_ids - current_tab_ids

        new_tabs_detected_by_poll = []  # Tabs needing HTML fetch due to being new
        navigated_tabs_detected_by_poll = []  # Tabs needing HTML fetch due to URL change
        closed_tabs_detected_by_poll = []  # Info about closed tabs

        # Process Added Tabs
        for tab_id in added_tab_ids:
            tab = current_polled_tabs_map[tab_id]
            logger.info(f"Polling: Detected NEW tab {tab.id} ({tab.url})")
            new_tabs_detected_by_poll.append(tab.model_dump())  # Store dict for event
            # Start interaction monitor for the new tab
            if tab.webSocketDebuggerUrl:
                self._start_interaction_monitor(tab.id, tab.webSocketDebuggerUrl)
            else:
                logger.warning(
                    f"New tab {tab.id} missing WebSocket URL, cannot monitor interactions."
                )

        # Process Removed Tabs
        for tab_id in removed_tab_ids:
            ref = current_tab_refs_map[tab_id]
            logger.info(f"Polling: Detected CLOSED tab {ref.id} ({ref.url})")
            closed_tabs_detected_by_poll.append(
                {"id": ref.id, "url": ref.url}
            )  # Store dict for event
            # Stop interaction monitor for the closed tab
            self._stop_interaction_monitor(tab_id)

        # Process Existing Tabs (Check for Navigation)
        potentially_navigated_ids = previous_tab_ids.intersection(current_tab_ids)
        tabs_to_keep_refs = set()  # Track refs that don't need fetching by polling

        for tab_id in potentially_navigated_ids:
            current_tab = current_polled_tabs_map[tab_id]
            previous_ref = current_tab_refs_map[tab_id]

            if current_tab.url != previous_ref.url:
                logger.info(
                    f"Polling: Detected NAVIGATION in tab {tab_id}: '{previous_ref.url}' -> '{current_tab.url}'"
                )
                nav_tab_info = current_tab.model_dump()
                nav_tab_info["old_url"] = previous_ref.url  # Add old URL for event context
                navigated_tabs_detected_by_poll.append(nav_tab_info)

                # 1. Stop any ongoing interaction work for the old URL context IMMEDIATELY.
                # This cancels pending timers/fetches associated with the previous URL.
                self._stop_interaction_monitor(tab_id)

                # 2. Update the internal state *now* with the new URL but empty markdown.
                # This ensures any interaction update that might still slip through
                # before the polling HTML fetch completes uses the *correct* URL for saving.
                # The actual markdown will be filled in later by the polling fetch results.
                logger.debug(
                    f"Navigation detected for {tab_id}: updating internal ref URL immediately to {current_tab.url}"
                )
                self.previous_tab_refs.discard(previous_ref)  # Remove old ref
                # Add placeholder with new URL, empty markdown, and no HTML initially
                self.previous_tab_refs.add(
                    TabReference(
                        id=tab_id,
                        url=current_tab.url,
                        markdown="",
                        html=None,
                        title=current_tab.title,
                    )
                )

                # 3. Start the interaction monitor for the *new* URL context.
                # Add a small delay to allow the target page's WS endpoint to potentially stabilize
                await asyncio.sleep(1.0)  # Wait 1 second

                if current_tab.webSocketDebuggerUrl:
                    self._start_interaction_monitor(tab_id, current_tab.webSocketDebuggerUrl)
                else:
                    logger.warning(
                        f"Navigated tab {tab_id} missing WebSocket URL, cannot monitor interactions."
                    )

            else:
                # URL didn't change according to polling, keep existing reference for now
                # Interaction monitor should already be running if it was started previously
                tabs_to_keep_refs.add(previous_ref)

        # --- Fetch HTML for Polling-Detected Changes ---
        tabs_needing_html_fetch_by_poll = []
        # Add new tabs (we already have the dicts)
        tabs_needing_html_fetch_by_poll.extend(new_tabs_detected_by_poll)
        # Add navigated tabs (we already have the dicts)
        tabs_needing_html_fetch_by_poll.extend(navigated_tabs_detected_by_poll)

        newly_fetched_tabs_with_html = []
        if tabs_needing_html_fetch_by_poll:
            logger.debug(
                f"Polling needs to fetch HTML for {len(tabs_needing_html_fetch_by_poll)} new/navigated tabs..."
            )
            # Fetch HTML in parallel ONLY for tabs identified by the polling logic
            newly_fetched_tabs_with_html = await self.chrome_manager.get_html_for_tabs(
                tabs_needing_html_fetch_by_poll  # Pass the list of dicts
            )
            logger.debug(f"Polling fetched HTML for {len(newly_fetched_tabs_with_html)} tabs.")

        # --- Update Internal State (previous_tab_refs) ---
        # Start with the refs for tabs whose URL didn't change
        updated_tab_refs = set(tabs_to_keep_refs)

        # Add/update refs for tabs where polling fetched new HTML
        # The result now contains (tab_dict, html, url)
        for tab_dict, html, fetched_url in newly_fetched_tabs_with_html:
            tab_id = tab_dict.get("id")
            # Use the URL returned by the fetch operation, fallback to tab_dict URL if None
            tab_url = fetched_url or tab_dict.get("url")
            original_html = html

            if tab_id and tab_url:
                # Convert HTML to Markdown using the fetched/confirmed URL
                markdown = html_to_md(html, tab_url) if html else ""
                if markdown is None:
                    logger.warning(
                        f"Polling Markdown conversion failed for {tab_url}, storing empty."
                    )
                    markdown = ""
                # Remove any outdated ref for this ID if it exists (e.g., from navigation placeholder)
                updated_tab_refs = {ref for ref in updated_tab_refs if ref.id != tab_id}
                # Add the new reference with the fetched/confirmed URL and fresh markdown
                updated_tab_refs.add(
                    TabReference(
                        id=tab_id,
                        url=tab_url,
                        markdown=markdown,
                        html=original_html,
                        title=tab_dict.get("title"),
                    )
                )

        # Atomically update the main set of references
        self.previous_tab_refs = updated_tab_refs

        # --- Return Event for Polling Callback ---
        # Only return an event if polling detected direct changes (new, close, navigate)
        polling_detected_changes = bool(
            new_tabs_detected_by_poll
            or closed_tabs_detected_by_poll
            or navigated_tabs_detected_by_poll
        )

        if polling_detected_changes:
            # Prepare the current_tabs list for the event (use dicts from filtered_tabs)
            current_tabs_for_event = [tab.model_dump() for tab in filtered_tabs]
            return TabChangeEvent(
                new_tabs=new_tabs_detected_by_poll,
                closed_tabs=closed_tabs_detected_by_poll,
                navigated_tabs=navigated_tabs_detected_by_poll,
                current_tabs=current_tabs_for_event,  # Provide the full current state
            )
        else:
            # logger.debug("Polling detected no new/closed/navigated tabs.")
            return None  # No changes detected by this polling run


async def main() -> None:
    """Run the Chrome tab monitor as a standalone program."""
    console = Console()

    POLLING_INTERVAL = 5.0

    stop_event = asyncio.Event()

    def signal_handler(sig, frame):
        console.print(f":shield: Signal {sig} received. Stopping monitor...")
        stop_event.set()  # Signal the main loop to stop

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # --- File Saving Setup ---
    debug_dir = Path(__file__).parent / "debug"
    saved_slugs_in_run: Set[str] = set()
    processed_urls_for_md: Set[str] = set()

    def clear_and_create_dir(dir_path: Path, name: str):
        if dir_path.exists():
            logger.info(f"Clearing {name} directory: {dir_path}")
            shutil.rmtree(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created {name} directory: {dir_path}")

    clear_and_create_dir(debug_dir, "debug")

    async def save_tab_content(tab_ref: TabReference):
        # Check for URL
        if not tab_ref.url:
            logger.warning(f"Skipping content save for tab {tab_ref.id} - missing URL.")
            return

        # Find a unique slugified filename base
        original_slug = slugify(tab_ref.url)
        slug = original_slug
        counter = 1
        # Ensure we don't overwrite by checking existence of *either* file type
        while (debug_dir / f"{slug}.md").exists() or (debug_dir / f"{slug}.html").exists():
            if slug in saved_slugs_in_run:  # Check if we've used this base slug in this run
                counter += 1
                slug = f"{original_slug}_{counter}"
            else:
                # If the file exists but wasn't saved by *this* run, we can overwrite it
                # Mark it as used now.
                break  # Exit loop to use current slug

        saved_slugs_in_run.add(slug)  # Mark slug as used for this run

        # Save Markdown
        md_file = debug_dir / f"{slug}.md"
        markdown = tab_ref.markdown
        if markdown:  # Only save if markdown exists
            try:
                md_file.parent.mkdir(parents=True, exist_ok=True)
                with open(md_file, "w", encoding="utf-8") as f:
                    f.write(markdown)
                logger.info(
                    f"Saved markdown for {tab_ref.url} ({len(markdown):,} chars) to {md_file.name}"
                )
                processed_urls_for_md.add(tab_ref.url)  # Keep track for final count maybe?
            except Exception as e:
                logger.error(f"Error saving markdown for {tab_ref.url}: {e}")
        else:
            logger.debug(f"Skipping markdown save for {tab_ref.url} - content is empty.")

        # Save HTML
        html_file = debug_dir / f"{slug}.html"
        html = tab_ref.html
        if html:  # Only save if HTML exists
            try:
                html_file.parent.mkdir(parents=True, exist_ok=True)
                with open(html_file, "w", encoding="utf-8") as f:
                    f.write(html)
                logger.info(
                    f"Saved HTML for {tab_ref.url} ({len(html):,} chars) to {html_file.name}"
                )
            except Exception as e:
                logger.error(f"Error saving HTML for {tab_ref.url}: {e}")
        else:
            logger.debug(f"Skipping HTML save for {tab_ref.url} - content is missing.")

    # --- End File Saving Setup ---

    # --- Callbacks ---
    async def on_polling_update(event: TabChangeEvent):
        console.print("[bold yellow]:mag: Polling Update Detected:[/bold yellow]")
        if event.new_tabs:
            console.print(f"  :heavy_plus_sign: [green]Added {len(event.new_tabs)} tab(s):[/green]")
            for i, tab in enumerate(event.new_tabs):
                console.print(
                    f"    {i + 1}. [link={tab.get('url')}]{tab.get('url', 'N/A')}[/link] (ID: {tab.get('id', '?')[:8]}...)"
                )
                ref = next(
                    (r for r in tabs_monitor.previous_tab_refs if r.id == tab.get("id")), None
                )
                if ref:
                    await save_tab_content(ref)

        if event.navigated_tabs:
            console.print(
                f"  :left_right_arrow: [blue]Navigated {len(event.navigated_tabs)} tab(s):[/blue]"
            )
            for i, tab in enumerate(event.navigated_tabs):
                console.print(
                    f"    {i + 1}. '[dim]{tab.get('old_url', 'N/A')}[/dim]' -> [link={tab.get('url')}]{tab.get('url', 'N/A')}[/link] (ID: {tab.get('id', '?')[:8]}...)"
                )
                ref = next(
                    (r for r in tabs_monitor.previous_tab_refs if r.id == tab.get("id")), None
                )
                if ref:
                    await save_tab_content(ref)

        if event.closed_tabs:
            console.print(
                f"  :heavy_minus_sign: [red]Closed {len(event.closed_tabs)} tab(s):[/red]"
            )
            for i, tab in enumerate(event.closed_tabs):
                console.print(
                    f"    {i + 1}. [dim]{tab.get('url', 'N/A')}[/dim] (ID: {tab.get('id', '?')[:8]}...)"
                )
        console.print()  # Add a newline for spacing

    async def on_interaction_update(tab_ref: TabReference):
        console.print(
            f"[bold cyan]:point_up: Interaction Update:[/bold cyan] Tab [dim]{tab_ref.id[:8]}...[/dim] ([link={tab_ref.url}]{tab_ref.url}[/link]) changed."
        )
        console.print(f"  :page_facing_up: New Markdown Size: {len(tab_ref.markdown):,} chars")
        await save_tab_content(tab_ref)
        console.print()  # Add a newline for spacing

    # --- End Callbacks ---

    # --- Main Execution Logic ---
    manager = ChromeManager()
    tabs_monitor = ChromeTabs(manager, check_interval=POLLING_INTERVAL)

    try:
        logger.info("Attempting to start tab monitoring...")
        monitor_started = await tabs_monitor.start_monitoring(
            on_polling_change_callback=on_polling_update,
            on_interaction_update_callback=on_interaction_update,
        )

        if monitor_started:
            chrome_info = await get_chrome_info()
            logger.success(
                f"Successfully connected to Chrome {chrome_info['version']} and started monitoring."
            )
            initial_refs = sorted(tabs_monitor.previous_tab_refs, key=lambda r: r.url)
            if initial_refs:
                for _i, ref in enumerate(initial_refs):
                    await save_tab_content(ref)  # Save MD and HTML for initial tabs
            else:
                console.print("  (No initial HTTP/HTTPS tabs found)")
            console.print(
                f"[dim]Polling every {POLLING_INTERVAL}s. Waiting for interactions or polling changes...[/dim]"
            )

            logger.info("Monitoring active. Press Ctrl+C to exit...")
            await stop_event.wait()  # Keep running until signal

        else:
            logger.error("Failed to start tab monitoring. Check Chrome connection.")

    except Exception as e:
        escaped_error = escape(str(e))
        logger.error(f"Unexpected error in main execution: {escaped_error}", exc_info=True)
    finally:
        logger.info("Initiating monitor shutdown...")
        await tabs_monitor.stop_monitoring()
        final_md_count = len(list(debug_dir.glob("*.md"))) if debug_dir.exists() else 0
        logger.success(
            f"Shutdown complete. Saved/updated markdown for {final_md_count} files to {debug_dir}"
        )
        logger.debug("Tab monitor main program finished.")
    # --- End Main Execution Logic ---


if __name__ == "__main__":
    logger.info("Starting Chrome Tab Monitor Demo...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user (main asyncio run).")
