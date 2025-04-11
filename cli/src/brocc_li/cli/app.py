import asyncio
import os
import threading
import time
from typing import Optional

from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.css.query import NoMatches
from textual.widgets import Button, Footer, Header, Label, Static, TabbedContent

from brocc_li.chrome_manager import ChromeManager
from brocc_li.chrome_tabs import ChromeTabs, TabChangeEvent, TabReference
from brocc_li.cli import auth
from brocc_li.cli.config_dir import get_config_dir
from brocc_li.cli.info_panel import InfoPanel
from brocc_li.cli.logs_panel import LogsPanel
from brocc_li.cli.service_status import check_and_update_api_status, check_and_update_webview_status
from brocc_li.cli.systray_launcher import launch_systray, terminate_systray
from brocc_li.cli.webview_launcher import (
    get_service_url,
    handle_webview_after_logout,
    open_or_focus_webview,
)
from brocc_li.cli.webview_manager import is_webview_open, open_webview
from brocc_li.doc_db import DocDB
from brocc_li.fastapi_server import FASTAPI_HOST, FASTAPI_PORT, run_server_in_thread
from brocc_li.frontend_server import WEBAPP_HOST, WEBAPP_PORT
from brocc_li.frontend_server import run_server_in_thread as run_webapp_in_thread
from brocc_li.types.doc import Doc
from brocc_li.utils.api_url import get_api_url
from brocc_li.utils.auth_data import is_logged_in, load_auth_data
from brocc_li.utils.html_metadata import extract_metadata
from brocc_li.utils.logger import logger
from brocc_li.utils.version import get_version
from brocc_li.utils.version_check import check_for_updates

load_dotenv()


class MainContent(Static):
    def __init__(self, app_instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app_instance = app_instance

    def compose(self) -> ComposeResult:
        # Add update container first, initially hidden
        yield Container(
            Label(id="update-message-label", markup=True),
            id="update-container",
            classes="hidden",
        )
        yield Container(
            Horizontal(
                Button(
                    label="✷  Opening Brocc window...  ✷",
                    id="open-webapp-btn",
                    variant="primary",
                    disabled=True,
                    name="open_webapp",
                ),
                id="webapp-buttons",
            ),
            id="webapp-container",
        )

    def show_update_message(self, message: str) -> None:
        """Makes the update container visible and sets its message."""
        try:
            container = self.query_one("#update-container", Container)
            label = self.query_one("#update-message-label", Label)
            label.update(message)
            container.remove_class("hidden")
            logger.debug("Displayed update message in MainContent UI")
        except NoMatches:
            logger.error("Could not find update UI components in MainContent to show message.")


class BroccApp(App):
    TITLE = f"🥦 brocc v{get_version()}"
    BINDINGS = [
        ("ctrl+c", "request_quit", "Quit"),
        ("f8", "logout", "Logout"),
    ]
    API_URL = get_api_url()
    LOCAL_API_PORT = FASTAPI_PORT
    CONFIG_DIR = get_config_dir()
    AUTH_FILE = CONFIG_DIR / "auth.json"
    CSS_PATH = ["app.tcss"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_data = load_auth_data()
        self.server_thread = None
        self.webapp_thread = None
        self.webview_thread = None  # Add reference to webview thread
        self.site_api_healthy = False
        self.local_api_healthy = False
        self._previous_webview_status = False
        self.tray_icon = None
        self.exit_file = None

        # Initialize DocDB
        self.doc_db = None
        self.doc_db_thread = None

        # Reference to info panel
        self.info_panel: Optional[InfoPanel] = None
        self.main_content: Optional[MainContent] = None  # Add reference to MainContent

        # Chrome Monitoring
        self.chrome_manager: Optional[ChromeManager] = None
        self.tabs_monitor: Optional[ChromeTabs] = None
        self.is_monitoring_tabs: bool = False

    # Helper method to safely update UI status
    def _safe_update_ui_status(self, message: str, element_id: str) -> None:
        """Safe wrapper to update UI status that returns None as required by callbacks"""
        if self.info_panel is not None:
            self.info_panel.update_ui_status(message, element_id)

    def compose(self) -> ComposeResult:
        yield Header()

        with TabbedContent("★ Main", "✦ Info", "✧ Logs", id="main-content"):
            yield MainContent(self, id="main-tab")
            yield InfoPanel(self, id="info-tab")
            yield LogsPanel(id="logs-tab")

        yield Footer()

    def on_mount(self) -> None:
        self.title = f"🥦 Brocc v{get_version()}"

        # Get reference to InfoPanel
        try:
            self.info_panel = self.query_one(InfoPanel)
            # Update auth status
            self.info_panel.update_auth_status()
            # Get reference to MainContent
            self.main_content = self.query_one(MainContent)
        except NoMatches:
            logger.error("Could not find InfoPanel component")

        # Set up system tray icon in its own process
        self._setup_systray()

        # Start the FastAPI server in a background thread
        try:
            logger.debug("Starting FastAPI server...")
            self.server_thread = run_server_in_thread()

            # Wait a moment to give the server time to start
            time.sleep(0.5)

            # Chrome connection is handled automatically by the server on import
        except Exception as e:
            logger.error(f"Failed to start FastAPI server: {e}")

        # Start the Frontend server in a separate thread
        try:
            logger.debug("Starting Frontend server...")
            self.webapp_thread = run_webapp_in_thread()

            # Wait a moment to give the server time to start
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"Failed to start Frontend server: {e}")

        # Initialize DocDB in a background thread
        self.doc_db_thread = threading.Thread(target=self._initialize_doc_db, daemon=True)
        self.doc_db_thread.start()

        # Initialize Chrome Manager and Tabs Monitor
        self.chrome_manager = ChromeManager()
        self.tabs_monitor = ChromeTabs(self.chrome_manager)

        # Check health status initially
        self.run_worker(self._check_health_worker, thread=True)

        # Set up periodic health check to detect webview closure
        self.set_interval(2.0, self._check_webview_status)

        # Set up periodic check for DocDB status
        self.set_interval(60.0, self._update_doc_db_status)

        # Set up periodic check to manage tab monitoring state
        self.set_interval(5.0, self._manage_tab_monitoring_state)

        # Launch the webview via a worker that waits for the server
        self.run_worker(self._launch_webview_worker, thread=True)

        # Check for updates in background
        self.run_worker(self._check_for_updates_worker, thread=True)

    def _setup_systray(self):
        """Start the system tray icon in a separate process"""
        success = launch_systray(
            webapp_host=WEBAPP_HOST,
            webapp_port=WEBAPP_PORT,
            api_host=str(FASTAPI_HOST),
            api_port=FASTAPI_PORT,
            version=get_version(),
        )

        return success

    def _close_systray(self):
        """Close the systray process if it's running"""
        return terminate_systray()

    def _notify_webview_shutdown(self):
        """Directly terminate the webview process"""
        try:
            # Get reference to webview process from FastAPI server
            from brocc_li.fastapi_webview import _WEBVIEW_PROCESS

            if _WEBVIEW_PROCESS and _WEBVIEW_PROCESS.poll() is None:
                logger.debug("Terminating webview process directly")
                _WEBVIEW_PROCESS.terminate()
                return True
            return False
        except Exception as e:
            logger.error(f"Error terminating webview process: {e}")
            return False

    async def action_request_quit(self) -> None:
        """Cleanly exit the application, closing all resources"""
        # Mark logger as shutting down to suppress further output
        logger.mark_shutting_down()

        # Log shutdown message *after* marking as shutting down (won't go to TUI)
        logger.debug("Shutdown initiated, closing resources")

        # Set up a timed force exit in case shutdown hangs
        def force_exit():
            time.sleep(3)  # Wait 3 seconds then force exit
            # Don't log this since we're suppressing output

            os._exit(0)  # Force immediate exit

        # Start force exit timer
        threading.Thread(target=force_exit, daemon=True).start()

        # Stop tab monitoring first
        await self._stop_tab_monitoring_if_running()

        # First try to quickly terminate any active processes
        try:
            # Try direct termination of the webview process
            from brocc_li.fastapi_webview import _WEBVIEW_PROCESS

            if _WEBVIEW_PROCESS and _WEBVIEW_PROCESS.poll() is None:
                try:
                    # Don't log anything here - suppressed
                    _WEBVIEW_PROCESS.terminate()
                except Exception:  # Specify exception type
                    pass
        except Exception:  # Specify exception type
            pass

        # Then try to do a clean shutdown via API
        self._notify_webview_shutdown()

        # Close the systray
        self._close_systray()

        # No logging here
        logger.info("Initiating clean application exit.")
        self.exit()

    def action_check_health(self) -> None:
        self.run_worker(self._check_health_worker, thread=True)

    def action_logout(self) -> None:
        self.run_worker(self._logout_worker, thread=True)

    def action_open_webapp(self) -> None:
        """Action to open the App in a standalone window"""
        self.run_worker(self._open_webapp_worker, thread=True)

    def action_launch_duckdb_ui(self) -> None:
        """Launch the DuckDB UI browser interface"""
        if self.doc_db is None:
            logger.error("Cannot launch DuckDB UI: DocDB not initialized")
            return

        def run_ui():
            try:
                # Check again inside the thread in case it became None
                if self.doc_db is not None:
                    self.doc_db.launch_duckdb_ui()
                else:
                    logger.error("DocDB became None after thread started")
            except Exception as e:
                logger.error(f"Error launching DuckDB UI: {e}")

        # Launch in a separate thread to avoid blocking the UI
        threading.Thread(target=run_ui, daemon=True).start()
        logger.debug("Launched DuckDB UI browser interface")

    @property
    def is_logged_in(self) -> bool:
        return is_logged_in(self.auth_data)

    def _restart_local_server(self) -> bool:
        """Restart the local API server if it died"""
        try:
            if self.server_thread is not None and not self.server_thread.is_alive():
                logger.debug("Previous server thread died, starting a new one")
                self.server_thread = run_server_in_thread()
                # Give it a moment to start
                time.sleep(1)
                return True
            return False
        except Exception as restart_err:
            logger.error(f"Failed to restart local API: {restart_err}")
            return False

    def _restart_webapp_server(self) -> bool:
        """Restart the Frontend server if it died"""
        try:
            if self.webapp_thread is not None and not self.webapp_thread.is_alive():
                logger.debug("Previous Frontend thread died, starting a new one")
                self.webapp_thread = run_webapp_in_thread()
                # Give it a moment to start
                time.sleep(1)
                return True
            return False
        except Exception as restart_err:
            logger.error(f"Failed to restart Frontend server: {restart_err}")
            return False

    def _check_health_worker(self):
        """Worker to check health of both APIs"""
        try:
            # Check site API health
            local_url = get_service_url(FASTAPI_HOST, FASTAPI_PORT)
            webapp_url = get_service_url(WEBAPP_HOST, WEBAPP_PORT)

            # Update site API health status
            self.site_api_healthy = check_and_update_api_status(
                api_name="Site API",
                api_url=self.API_URL,
                update_ui_fn=lambda msg: self._safe_update_ui_status(msg, "siteapi-health"),
            )

            # Update local API health status
            self.local_api_healthy = check_and_update_api_status(
                api_name="Local API",
                api_url=local_url,
                is_local=True,
                update_ui_fn=lambda msg: self._safe_update_ui_status(msg, "localapi-health"),
                restart_server_fn=self._restart_local_server,
            )

            # Check App health status
            webapp_healthy = check_and_update_api_status(
                api_name="Frontend",
                api_url=webapp_url,
                is_local=True,
                update_ui_fn=lambda msg: self._safe_update_ui_status(msg, "webapp-health"),
                restart_server_fn=self._restart_webapp_server,
            )

            # Update App status including whether the webview is open
            if webapp_healthy and self.info_panel is not None:
                self.info_panel.update_webapp_status()

            # Update login button state based on API health
            if self.info_panel is not None:
                self.info_panel.update_auth_status()

            # Update login button specifically based on site API health
            try:
                login_btn = self.query_one("#login-btn", Button)
                open_webapp_btn = self.query_one("#open-webapp-btn", Button)

                if not self.site_api_healthy:
                    login_btn.disabled = True
                    logger.warning("Login disabled because Site API is not available")
                elif not self.is_logged_in:
                    login_btn.disabled = False

                # Enable/disable Open window button based on App health
                open_webapp_btn.disabled = not webapp_healthy
            except NoMatches:
                pass

        except Exception as e:
            logger.error(f"Error checking health: {e}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Call the appropriate action based on button name"""
        button_name = event.button.name
        if button_name:
            action_name = f"action_{button_name}"
            action = getattr(self, action_name, None)
            if action and callable(action):
                logger.debug(f"Button pressed: {button_name}")
                action()

    def _launch_webview_worker(self):
        """Worker to wait for local API and then launch the webview."""
        import time

        import requests

        local_api_health_url = f"http://{FASTAPI_HOST}:{FASTAPI_PORT}/health"
        max_wait_seconds = 15
        start_time = time.time()
        server_ready = False

        logger.debug(
            f"Waiting up to {max_wait_seconds}s for local API at {local_api_health_url}..."
        )

        while time.time() - start_time < max_wait_seconds:
            try:
                response = requests.get(local_api_health_url, timeout=1)  # Short timeout for check
                if response.status_code == 200:
                    logger.success(f"Local API is healthy after {time.time() - start_time:.1f}s.")
                    server_ready = True
                    break
                else:
                    logger.debug(f"Local API check failed with status {response.status_code}")
            except requests.exceptions.ConnectionError:
                logger.debug("Local API connection refused, retrying...")
            except requests.exceptions.Timeout:
                logger.debug("Local API health check timed out, retrying...")
            except Exception as e:
                logger.error(f"Unexpected error during local API health check: {e}")

            time.sleep(0.5)  # Wait before retrying

        if server_ready:
            logger.debug("Server ready, proceeding with webview launch.")
            success = open_webview()
            logger.debug(f"Webview launch attempt result: {success}")
            # Trigger status check to update UI based on actual launch state
            self.run_worker(self._check_webview_status, thread=True)
        else:
            logger.error(
                f"Local API server did not become healthy within {max_wait_seconds} seconds. Cannot launch webview."
            )
            # Update UI to show failure (safely)
            self.call_from_thread(
                self._safe_update_ui_status,
                "Window: [red]Launch Failed (API timeout)[/red]",
                "webapp-health",
            )

    def _logout_worker(self):
        try:
            status_label = self.query_one("#auth-status", Label)
            status_label.update("Logging out...")
            if auth.logout():
                self.auth_data = None
                status_label.update("Successfully logged out")
                if self.info_panel is not None:
                    self.info_panel.update_auth_status()

                # Stop tab monitoring after logout
                # Need to run the async stop function from this sync worker
                self.call_from_thread(asyncio.run, self._stop_tab_monitoring_if_running())

                # Handle webview after logout
                def update_ui_status(status):
                    if status == "LOGGED_OUT":
                        self._safe_update_ui_status(
                            "Window: [yellow]Running but logged out, closing automatically...[/yellow]",
                            "webapp-health",
                        )
                    elif status == "CLOSED":
                        self._safe_update_ui_status(
                            "Window: [blue]Closed after logout[/blue]",
                            "webapp-health",
                        )

                def update_button_state():
                    try:
                        open_webapp_btn = self.query_one("#open-webapp-btn", Button)
                        open_webapp_btn.label = "✷  Open Brocc window  ✷"
                    except NoMatches:
                        pass

                handle_webview_after_logout(
                    update_ui_fn=update_ui_status, update_button_fn=update_button_state
                )
            else:
                status_label.update("Error during logout")
                logger.error("Error during logout")
        except NoMatches:
            logger.error("Logout failed: UI components not found")

    def _open_webapp_worker(self):
        """Worker to open the App in a separate window or focus existing one"""
        logger.debug("Opening webapp worker started")

        def update_ui_status(message):
            logger.debug(f"Updating UI status: {message}")
            self._safe_update_ui_status(message, "webapp-health")

            # Update button state - keep enabled but change label if needed
            try:
                # If window is now open, update button label and hide loading indicator
                if is_webview_open():
                    logger.debug("Webview is now open, updating UI")
                    # Update UI elements that can be done directly
                    try:
                        open_webapp_btn = self.query_one("#open-webapp-btn", Button)
                        open_webapp_btn.disabled = False  # Keep enabled for focus functionality
                        open_webapp_btn.label = "✷  Show Brocc window  ✷"
                    except NoMatches:
                        logger.error("Could not find button to update")
                else:
                    logger.warning("Webview still not open after launch attempt")
            except NoMatches:
                logger.error("Could not find UI elements to update after webview launch")
                pass
            except Exception as e:
                logger.error(f"Error updating UI after webview launch: {e}")

        # Double-check webview status before trying to open it
        logger.debug(f"Webview state before launch: open={is_webview_open()}")

        logger.debug("Calling open_or_focus_webview")
        from brocc_li.cli.info_panel import UI_STATUS

        success = open_or_focus_webview(
            ui_status_mapping=UI_STATUS,
            update_ui_fn=update_ui_status,
            previous_status=getattr(self, "_previous_webview_status", None),
        )

        logger.debug(f"open_or_focus_webview result: {success}")

        # Check again after attempt
        logger.debug(f"Webview state after launch attempt: open={is_webview_open()}")

        # If we still don't have a webview, try one more direct launch
        if not is_webview_open():
            logger.debug("Webview still not open after first attempt, trying direct launch")
            direct_success = open_webview()
            logger.debug(f"Direct webview launch (fallback) result: {direct_success}")

            # Final check
            logger.debug(f"Final webview state: open={is_webview_open()}")

    def _check_webview_status(self) -> None:
        """Periodic check of webview status"""
        # Get local api URL
        local_url = get_service_url(FASTAPI_HOST, FASTAPI_PORT)

        # Use the utility function to check webview status and update UI
        from brocc_li.cli.info_panel import UI_STATUS

        status_mapping = {
            "OPEN": UI_STATUS["WINDOW_OPEN"],
            "READY": UI_STATUS["WINDOW_READY"],
            "CLOSED": UI_STATUS["WINDOW_READY"],  # Use READY status for closed windows
        }

        def update_button(is_open: bool, status_changed: bool) -> None:
            try:
                open_webapp_btn = self.query_one("#open-webapp-btn", Button)
                if is_open:
                    open_webapp_btn.disabled = False  # Keep enabled for focus functionality
                    open_webapp_btn.label = "✷  Show Brocc window  ✷"
                elif status_changed:  # Was open before but now closed
                    open_webapp_btn.disabled = False
                    open_webapp_btn.label = "✷  Open Brocc window  ✷"
            except NoMatches:
                logger.debug("Could not update button: UI component not found")
            except Exception as e:
                logger.error(f"Error updating button state: {e}")

        result = check_and_update_webview_status(
            api_url=local_url,
            ui_status_mapping=status_mapping,
            update_ui_fn=lambda msg: self._safe_update_ui_status(msg, "webapp-health"),
            update_button_fn=update_button,
            previous_status=getattr(self, "_previous_webview_status", None),
        )

        # Store current status for next check
        self._previous_webview_status = result["is_open"]

    def _initialize_doc_db(self):
        """Initialize document database in a background thread"""
        logger.debug("Initializing document database...")
        try:
            self.doc_db = DocDB()
            logger.debug("Document database initialized successfully")
            # Trigger UI update with initial status
            self._update_doc_db_status()
        except Exception as e:
            logger.error(f"Failed to initialize document database: {e}")

    def _update_doc_db_status(self):
        """Update the document database status in the UI"""
        if self.info_panel is not None:
            self.info_panel.update_doc_db_status()

    def _check_for_updates_worker(self):
        """Worker to check for updates and update UI if needed."""
        update_message = check_for_updates()
        if update_message and self.main_content:  # Check main_content reference
            # Use call_from_thread to safely update the UI from the worker
            self.call_from_thread(self.main_content.show_update_message, update_message)

    async def _manage_tab_monitoring_state(self):
        """Periodically checks conditions and starts/stops tab monitoring.

        Conditions:
        - Logged in
        - DocDB initialized and healthy
        - Chrome Manager instantiated and connected
        """
        if self.chrome_manager is None or self.tabs_monitor is None or self.doc_db is None:
            logger.debug("Tab monitoring dependencies not yet initialized.")
            return  # Dependencies not ready

        # Get DocDB status
        doc_db_healthy = False
        try:
            db_status = self.doc_db.get_duckdb_status()
            lance_status = self.doc_db.get_lancedb_status()
            # Consider it healthy if DuckDB is initialized and LanceDB initialization didn't fail critically
            doc_db_healthy = (
                db_status.get("initialized", False) and lance_status.get("error") is None
            )
        except Exception as e:
            logger.warning(f"Error checking DocDB status for monitoring: {e}")

        # Check Chrome connection
        try:
            # Use ensure_connection to try connecting if not already connected
            # Pass quiet=True to avoid excessive logging from ensure_connection itself
            chrome_connected = await self.chrome_manager.ensure_connection(quiet=True)

            # Update Chrome connection status in the UI
            if self.info_panel:
                self.info_panel.update_chrome_status(is_connected=chrome_connected)
        except Exception as e:
            logger.warning(f"Error checking Chrome connection for monitoring: {e}")
            chrome_connected = False
            # Update Chrome connection status to show error
            if self.info_panel:
                self.info_panel.update_chrome_status(is_connected=False)

        # Determine desired state
        should_be_monitoring = self.is_logged_in and doc_db_healthy and chrome_connected

        if should_be_monitoring and not self.is_monitoring_tabs:
            logger.info("Conditions met, starting Chrome tab monitoring...")
            try:
                # Update UI to show connecting state
                if self.info_panel:
                    self.info_panel.update_tab_monitoring_status(is_monitoring=False)

                monitor_started = await self.tabs_monitor.start_monitoring(
                    on_polling_change_callback=self._handle_tab_polling_update,
                    on_interaction_update_callback=self._handle_tab_interaction_update,
                )
                if monitor_started:
                    self.is_monitoring_tabs = True
                    logger.success("Chrome tab monitoring started.")

                    # Update UI to show active monitoring
                    if self.info_panel:
                        self.info_panel.update_tab_monitoring_status(is_monitoring=True)
                else:
                    logger.error("Failed to start tab monitoring.")

                    # Update UI to show error
                    if self.info_panel:
                        self.info_panel.update_tab_monitoring_status(error=True)
            except Exception as e:
                logger.error(f"Error starting tab monitoring: {e}", exc_info=True)
                # Update UI to show error
                if self.info_panel:
                    self.info_panel.update_tab_monitoring_status(error=True)

        elif not should_be_monitoring and self.is_monitoring_tabs:
            logger.info("Conditions no longer met, stopping Chrome tab monitoring...")
            try:
                await self.tabs_monitor.stop_monitoring()
                self.is_monitoring_tabs = False
                logger.success("Chrome tab monitoring stopped.")

                # Update UI to show inactive monitoring
                if self.info_panel:
                    # If not logged in, show that as the reason
                    self.info_panel.update_tab_monitoring_status(
                        is_monitoring=False, needs_login=not self.is_logged_in
                    )
            except Exception as e:
                logger.error(f"Error stopping tab monitoring: {e}", exc_info=True)
                # Update UI to show error
                if self.info_panel:
                    self.info_panel.update_tab_monitoring_status(error=True)
        # Ensure the UI always shows the current monitoring state, even if no change was needed
        elif self.info_panel:
            self.info_panel.update_tab_monitoring_status(
                is_monitoring=self.is_monitoring_tabs,
                needs_login=not self.is_logged_in and not self.is_monitoring_tabs,
            )

    async def _handle_tab_polling_update(self, event: TabChangeEvent):
        """Callback for polling-based tab changes."""
        logger.debug(
            f"Received polling update: {len(event.new_tabs)} new, {len(event.closed_tabs)} closed, {len(event.navigated_tabs)} navigated"
        )
        tabs_to_save = []
        # Collect refs for new and navigated tabs
        for tab_info in event.new_tabs + event.navigated_tabs:
            tab_id = tab_info.get("id")
            if tab_id and self.tabs_monitor:
                # Find the TabReference matching this ID in the monitor's current state
                ref = next((r for r in self.tabs_monitor.previous_tab_refs if r.id == tab_id), None)
                if ref:
                    tabs_to_save.append(ref)
                else:
                    logger.warning(f"Polling update: Could not find TabReference for ID {tab_id}")

        # Queue each ref for saving via the worker
        for tab_ref in tabs_to_save:
            logger.debug(f"Polling: Queueing save for tab {tab_ref.id[:8]} ({tab_ref.url}) ")
            # Wrap worker call in lambda to pass arguments correctly
            self.run_worker(lambda ref=tab_ref: self._save_tab_ref_worker(ref), thread=True)

    async def _handle_tab_interaction_update(self, tab_ref: TabReference):
        """Callback for interaction-based tab updates."""
        display_url = tab_ref.url[:80] + "..." if len(tab_ref.url) > 80 else tab_ref.url
        logger.debug(f"Received interaction update for tab {tab_ref.id[:8]}: {display_url}")
        # Queue the ref for saving via the worker
        # Wrap worker call in lambda to pass arguments correctly
        self.run_worker(lambda ref=tab_ref: self._save_tab_ref_worker(ref), thread=True)

    def _save_tab_ref_worker(self, tab_ref: TabReference):
        """Synchronous worker to save a TabReference to DocDB."""
        if self.doc_db is None:
            logger.error("Cannot save tab reference: DocDB not initialized.")
            return

        if not tab_ref.markdown:
            logger.debug(f"Skipping save for tab {tab_ref.id[:8]}: No markdown content.")
            return

        logger.info(f"Saving tab content to DB: {tab_ref.url}")

        try:
            if not tab_ref.html:
                # If HTML is missing, it likely means the content fetch failed or the
                # page wasn't HTML. We can't extract meaningful metadata or reliably
                # store the content without it.
                logger.warning(
                    f"Skipping save for tab {tab_ref.id[:8]} ({tab_ref.url}): Missing HTML content in TabReference."
                )
                return

            doc_title = tab_ref.title  # Start with title from tab reference
            doc_description = None
            doc_author = None
            doc_created_at = None
            doc_keywords = []
            additional_metadata = {}

            # If we have HTML, try to extract richer metadata
            if tab_ref.html:
                try:
                    extracted_meta = extract_metadata(tab_ref.html, tab_ref.url)
                    # Prioritize extracted title, fallback to tab title
                    if extracted_meta.title:
                        doc_title = extracted_meta.title
                    doc_description = extracted_meta.description
                    doc_author = extracted_meta.author

                    # Handle published_at (save as created_at in Doc)
                    if extracted_meta.published_at:
                        doc_created_at = Doc.format_date(extracted_meta.published_at)

                    # Handle keywords
                    if extracted_meta.keywords:
                        doc_keywords = extracted_meta.keywords

                    if extracted_meta.og_image:
                        additional_metadata["og_image"] = str(extracted_meta.og_image)
                    if extracted_meta.favicon:
                        additional_metadata["favicon"] = str(extracted_meta.favicon)
                except Exception as meta_ex:
                    logger.warning(f"Failed to extract HTML metadata for {tab_ref.url}: {meta_ex}")

            # Construct the Doc object for storage
            doc = Doc(
                id=Doc.generate_id(),  # Generate ID for the pydantic model
                url=tab_ref.url,
                title=doc_title,  # Use potentially updated title
                description=doc_description,  # Add extracted description
                text_content=tab_ref.markdown,  # Use markdown as the text content
                source="chrome",
                contact_name=doc_author,  # Use author as contact_name
                created_at=doc_created_at,  # Use publication date as created_at
                keywords=doc_keywords,  # Add keywords from metadata
                metadata=additional_metadata,  # Include extracted fields
            )

            # Store the document (handles new/update/merge logic)
            success = self.doc_db.store_document(doc)

            if success:
                logger.success(f"Successfully saved/updated tab in DB: {tab_ref.url}")
            else:
                # store_document logs its own errors, but we can add context
                logger.warning(f"Problem saving tab to DB (check previous logs): {tab_ref.url}")

        except Exception as e:
            logger.error(f"Error in _save_tab_ref_worker for {tab_ref.url}: {e}", exc_info=True)

    async def _stop_tab_monitoring_if_running(self):
        """Checks if tab monitoring is running and stops it if so."""
        if self.is_monitoring_tabs and self.tabs_monitor:
            logger.info("Stopping tab monitoring...")
            try:
                await self.tabs_monitor.stop_monitoring()
                self.is_monitoring_tabs = False
                logger.success("Tab monitoring stopped.")

                # Update UI to reflect stopped monitoring
                if self.info_panel:
                    self.info_panel.update_tab_monitoring_status(
                        is_monitoring=False, needs_login=not self.is_logged_in
                    )
            except Exception as e:
                logger.error(f"Error stopping tab monitoring during shutdown/logout: {e}")

                # Update UI to show error
                if self.info_panel:
                    self.info_panel.update_tab_monitoring_status(error=True)
        else:
            logger.debug("Tab monitoring was not running.")


if __name__ == "__main__":
    app = BroccApp()
    try:
        app.run()
    except Exception as e:
        logger.error(f"CRITICAL ERROR in main app loop: {e}", exc_info=True)
        # Attempt to cleanup systray even on crash
        try:
            terminate_systray()
        except Exception as term_e:
            logger.error(f"Error terminating systray during crash handling: {term_e}")
    finally:
        logger.info("Application has finished running.")
