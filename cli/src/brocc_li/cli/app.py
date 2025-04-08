import os
import threading
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from platformdirs import user_config_dir
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.css.query import NoMatches
from textual.widgets import Button, Footer, Header, Label, LoadingIndicator, Static, TabbedContent

from brocc_li.cli import auth
from brocc_li.cli.service_status import check_and_update_api_status, check_and_update_webview_status
from brocc_li.cli.systray_launcher import launch_systray, terminate_systray
from brocc_li.cli.textual_ui.info_panel import InfoPanel
from brocc_li.cli.textual_ui.logs_panel import LogsPanel
from brocc_li.cli.webview_launcher import (
    get_service_url,
    handle_webview_after_logout,
    maybe_launch_webview_if_logged_in,
    open_or_focus_webview,
)
from brocc_li.cli.webview_manager import is_webview_open, open_webview
from brocc_li.doc_db import DocDB
from brocc_li.fastapi_server import FASTAPI_HOST, FASTAPI_PORT, run_server_in_thread
from brocc_li.frontend_server import WEBAPP_HOST, WEBAPP_PORT
from brocc_li.frontend_server import run_server_in_thread as run_webapp_in_thread
from brocc_li.utils.api_url import get_api_url
from brocc_li.utils.auth_data import is_logged_in, load_auth_data
from brocc_li.utils.logger import logger
from brocc_li.utils.version import get_version

load_dotenv()


class MainContent(Static):
    def __init__(self, app_instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app_instance = app_instance

    def compose(self) -> ComposeResult:
        yield Container(
            Horizontal(
                Button(
                    label="✷  Opening Brocc window...  ✷",
                    id="open-webapp-btn",
                    variant="primary",
                    disabled=True,
                    name="open_webapp",
                    classes="hidden",  # Hide button by default
                ),
                LoadingIndicator(id="webapp-loading"),  # Show loading indicator by default
                id="webapp-buttons",
            ),
            id="webapp-container",
        )


class BroccApp(App):
    TITLE = f"🥦 brocc v{get_version()}"
    BINDINGS = [
        ("ctrl+c", "request_quit", "Quit"),
        ("f8", "logout", "Logout"),
    ]
    API_URL = get_api_url()
    LOCAL_API_PORT = FASTAPI_PORT  # Port for the local FastAPI server
    CONFIG_DIR = Path(user_config_dir("brocc"))
    AUTH_FILE = CONFIG_DIR / "auth.json"
    CSS_PATH = ["app.tcss", "textual_ui/info_panel.tcss", "textual_ui/logs_panel.tcss"]

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
        self.is_opening_webapp = False  # Track if webapp is currently being opened

        # Initialize DocDB
        self.doc_db = None
        self.doc_db_thread = None

        # Reference to info panel
        self.info_panel: Optional[InfoPanel] = None

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

        # Check health status initially
        self.run_worker(self._check_health_worker, thread=True)

        # Set up periodic health check to detect webview closure
        self.set_interval(2.0, self._check_webview_status)

        # Set up periodic check for DocDB status
        self.set_interval(60.0, self._update_doc_db_status)

        # Launch webview if already logged in
        if self.is_logged_in:
            # Launch with a small delay to allow servers to start
            logger.debug("Setting timer to auto-launch webview in 2 seconds")
            self.set_timer(2, self._force_launch_webview)
        else:
            logger.debug("User not logged in, skipping auto-launch timer")

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

    def action_request_quit(self) -> None:
        """Cleanly exit the application, closing all resources"""
        logger.debug("Shutdown initiated, closing resources")

        # Mark logger as shutting down to suppress further output
        logger.mark_shutting_down()

        # Set up a timed force exit in case shutdown hangs
        def force_exit():
            time.sleep(3)  # Wait 3 seconds then force exit
            # Don't log this since we're suppressing output

            os._exit(0)  # Force immediate exit

        # Start force exit timer
        threading.Thread(target=force_exit, daemon=True).start()

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

        # Exit immediately without waiting for anything
        # No logging here
        self.exit()

    def action_check_health(self) -> None:
        self.run_worker(self._check_health_worker, thread=True)

    def action_login(self) -> None:
        self.run_worker(self._login_worker, thread=True)

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

    def _maybe_launch_webview(self):
        """Configure UI to show webview is ready to launch"""
        logger.debug("Setting up UI for webview launch")

        def update_ui():
            logger.debug("Updating UI to show webview is ready")
            self._safe_update_ui_status(
                "Window: [blue]Ready to launch[/blue]",
                "webapp-health",
            )

        def update_button():
            try:
                logger.debug("Updating button state for webview launch")
                open_webapp_btn = self.query_one("#open-webapp-btn", Button)
                open_webapp_btn.disabled = False
                open_webapp_btn.label = "✷  Open Brocc window  ✷"
            except NoMatches:
                logger.error("Could not find open-webapp-btn to update")
                pass

        logger.debug(
            f"Calling maybe_launch_webview_if_logged_in with is_logged_in={self.is_logged_in}"
        )
        maybe_launch_webview_if_logged_in(
            is_logged_in=self.is_logged_in, update_ui_fn=update_ui, update_button_fn=update_button
        )

    def _show_loading_indicator(self):
        """Show loading indicator and hide button while webapp opens"""
        try:
            button = self.query_one("#open-webapp-btn", Button)
            loading = self.query_one("#webapp-loading", LoadingIndicator)
            button.add_class("hidden")
            loading.remove_class("hidden")
            self.is_opening_webapp = True
        except NoMatches:
            logger.debug("Could not show loading indicator: UI components not found")

    def _hide_loading_indicator(self):
        """Hide loading indicator and show button once webapp is open"""
        try:
            button = self.query_one("#open-webapp-btn", Button)
            loading = self.query_one("#webapp-loading", LoadingIndicator)
            loading.add_class("hidden")
            button.remove_class("hidden")
            self.is_opening_webapp = False
        except NoMatches:
            logger.debug("Could not hide loading indicator: UI components not found")

    def _delayed_hide_loading_indicator(self):
        """Schedule hiding of the loading indicator from the main thread"""
        logger.debug("Scheduling delayed hiding of loading indicator")
        # Post a message to hide loading indicator after a delay
        # This is safe to call from worker threads
        self.call_after_refresh(self._schedule_hide_safely)

    def _schedule_hide_safely(self):
        """Schedule hiding from the main UI thread"""
        # This method runs in the main thread, so it's safe to use timers
        logger.debug("Setting timer to hide loading indicator")
        try:
            self.set_timer(1.0, self._hide_loading_indicator)
        except RuntimeError as e:
            logger.error(f"Error setting timer: {e}, hiding immediately instead")
            self._hide_loading_indicator()

    def _force_launch_webview(self):
        """Force the webview to launch regardless of state"""
        logger.debug("Force-launching webview")
        # Reset the flag first to ensure we can launch
        self.is_opening_webapp = False
        # Then launch
        self._auto_launch_webview()

    def _auto_launch_webview(self):
        """Automatically launch the webview if user is logged in"""
        if self.is_logged_in and not self.is_opening_webapp:
            logger.debug("Auto-launching webview since user is logged in")
            self._show_loading_indicator()
            self.is_opening_webapp = True  # Set flag AFTER the check but before launching

            # Try direct launch instead of going through the worker
            success = open_webview()
            logger.debug(f"Direct webview launch result: {success}")

            # Still run the worker for UI updates
            self.run_worker(self._open_webapp_worker, thread=True)
        elif not self.is_logged_in:
            logger.debug("Not auto-launching webview because user is not logged in")
        elif self.is_opening_webapp:
            logger.debug("Webview launch already in progress, not launching again")
            # If it's been more than 10 seconds since we started opening, reset
            if not hasattr(self, "_opening_start_time"):
                self._opening_start_time = time.time()
            elif time.time() - self._opening_start_time > 10:
                logger.debug("Launch has been pending for over 10 seconds, resetting state")
                self.is_opening_webapp = False
                self._opening_start_time = time.time()
                # Try launching again
                self._auto_launch_webview()
        else:
            logger.debug("Unknown state - not auto-launching webview")

    def _login_worker(self):
        try:
            status_label = self.query_one("#auth-status", Label)

            # Check if Site API is healthy before proceeding
            if not self.site_api_healthy:
                status_label.update("[red]Cannot login: Site API is not available[/red]")
                logger.error("Login aborted: Site API is not available")
                return

            # Clear previous URL display
            if self.info_panel is not None:
                self.info_panel.display_auth_url("")

            # Define status update callback
            def update_status(message):
                status_label.update(message)

            # Start login process with callbacks
            auth_data = auth.initiate_login(
                self.API_URL,
                update_status_fn=update_status,
                display_auth_url_fn=self.info_panel.display_auth_url
                if self.info_panel
                else lambda _: None,
            )

            if auth_data:
                self.auth_data = auth_data
                if self.info_panel is not None:
                    self.info_panel.update_auth_status()

                # Launch webview after successful login
                self._maybe_launch_webview()
                # Auto-launch the webview after successful login
                self.set_timer(1, self._auto_launch_webview)
            else:
                logger.error("Login failed")
        except NoMatches:
            logger.error("Login failed: UI components not found")

    def _logout_worker(self):
        try:
            status_label = self.query_one("#auth-status", Label)
            status_label.update("Logging out...")
            if auth.logout():
                self.auth_data = None
                status_label.update("Successfully logged out")
                if self.info_panel is not None:
                    self.info_panel.update_auth_status()

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
                        open_webapp_btn.disabled = True
                        open_webapp_btn.label = "✷  Login to start Brocc  ✷"
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
        self._show_loading_indicator()

        def update_ui_status(message):
            logger.debug(f"Updating UI status: {message}")
            self._safe_update_ui_status(message, "webapp-health")

            # Update button state - keep enabled but change label if needed
            try:
                # If window is now open, update button label and hide loading indicator
                if is_webview_open():
                    logger.debug("Webview is now open, updating UI")
                    # Request hiding to be scheduled from the main thread
                    self._delayed_hide_loading_indicator()
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
        from brocc_li.cli.textual_ui.info_panel import UI_STATUS

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
        from brocc_li.cli.textual_ui.info_panel import UI_STATUS

        status_mapping = {
            "OPEN": UI_STATUS["WINDOW_OPEN"],
            "READY": UI_STATUS["WINDOW_READY"],
            "CLOSED": UI_STATUS["WINDOW_READY"],  # Use READY status for closed windows
        }

        def update_button(is_open: bool, status_changed: bool) -> None:
            try:
                # If we were opening the webapp and it's now open, hide loading indicator with delay
                if self.is_opening_webapp and is_open:
                    # Request hiding from main thread
                    self._delayed_hide_loading_indicator()

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


if __name__ == "__main__":
    app = BroccApp()
    app.run()
