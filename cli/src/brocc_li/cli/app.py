import os
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
from platformdirs import user_config_dir
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.css.query import NoMatches
from textual.widgets import Button, Footer, Header, Label, Static, TabbedContent

from brocc_li.cli import auth
from brocc_li.cli.fastapi_server import FASTAPI_HOST, FASTAPI_PORT, run_server_in_thread
from brocc_li.cli.service_status import check_and_update_api_status, check_and_update_webview_status
from brocc_li.cli.systray_launcher import launch_systray, terminate_systray
from brocc_li.cli.textual_ui.info_panel import InfoPanel
from brocc_li.cli.textual_ui.logs_panel import LogsPanel
from brocc_li.cli.webapp_server import WEBAPP_HOST, WEBAPP_PORT
from brocc_li.cli.webapp_server import run_server_in_thread as run_webapp_in_thread
from brocc_li.cli.webview_launcher import (
    get_service_url,
    handle_webview_after_logout,
    maybe_launch_webview_if_logged_in,
    notify_webview_shutdown,
    open_or_focus_webview,
)
from brocc_li.cli.webview_manager import is_webview_open
from brocc_li.utils.api_url import get_api_url
from brocc_li.utils.auth_data import is_logged_in, load_auth_data
from brocc_li.utils.logger import logger
from brocc_li.utils.version import get_version

load_dotenv()

# Constants for UI messages and labels
UI_STATUS = {
    "WINDOW_OPEN": "Window: [green]Open[/green]",
    "WINDOW_READY": "Window: [blue]Ready to launch[/blue]",
    "WINDOW_CLOSED": "Window: [blue]Closed after logout[/blue]",
    "WINDOW_LAUNCHED": "Window: [green]Launched successfully[/green]",
    "WINDOW_FOCUSED": "Window: [green]Brought to foreground[/green]",
    "WINDOW_LAUNCH_FAILED": "Window: [red]Failed to launch[/red]",
    "WINDOW_STATUS_UNCLEAR": "Window: [yellow]Status unclear[/yellow]",
    "WINDOW_LOGGED_OUT": "Window: [yellow]Running but logged out, closing automatically...[/yellow]",
    "WEBAPP_OPEN": "WebApp: [green]Open[/green]",
    "WEBAPP_READY": "WebApp: [blue]Ready to launch[/blue]",
}

BUTTON_LABELS = {
    "OPEN_WINDOW": "Open Brocc window",
    "SHOW_WINDOW": "Show Brocc window",
    "LOGIN_TO_OPEN": "Login to open app window",
}

# Global vars for systray
_SYSTRAY_PROCESS = None


def update_ui_element(app, element_id, message):
    """Update UI element with message, handling NoMatches exception"""
    try:
        element = app.query_one(f"#{element_id}", Static)
        element.update(message)
        return True
    except NoMatches:
        logger.debug(f"Could not update UI status: element #{element_id} not found")
        return False


class AppContent(Static):
    def __init__(self, app_instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app_instance = app_instance

    def compose(self) -> ComposeResult:
        yield Container(
            Horizontal(
                Button(
                    label=BUTTON_LABELS["OPEN_WINDOW"],
                    id="open-webapp-btn",
                    variant="primary",
                    disabled=True,
                    name="open_webapp",
                ),
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

    def compose(self) -> ComposeResult:
        yield Header()

        with TabbedContent("App", "Info", "Logs", id="main-content"):
            yield AppContent(self, id="app-tab")
            yield InfoPanel(self, id="info-tab")
            yield LogsPanel(id="logs-tab")

        yield Footer()

    def _setup_systray(self):
        """Start the system tray icon in a separate process"""
        success, exit_file = launch_systray(
            webapp_host=WEBAPP_HOST,
            webapp_port=WEBAPP_PORT,
            api_host=FASTAPI_HOST,
            api_port=FASTAPI_PORT,
            version=get_version(),
        )

        if success:
            self.exit_file = exit_file
            return True
        return False

    def _close_systray(self):
        """Close the systray process if it's running"""
        return terminate_systray()

    def _notify_webview_shutdown(self):
        """Send shutdown message to webview via API"""
        notify_webview_shutdown()

    def action_request_quit(self) -> None:
        """Cleanly exit the application, closing all resources"""
        logger.info("Shutdown initiated, closing resources")

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
            from brocc_li.cli.fastapi_server import _WEBVIEW_PROCESS

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
        """Action to open the WebApp in a standalone window"""
        self.run_worker(self._open_webapp_worker, thread=True)

    @property
    def is_logged_in(self) -> bool:
        return is_logged_in(self.auth_data)

    def _update_auth_status(self):
        try:
            status_label = self.query_one("#auth-status", Label)
            login_btn = self.query_one("#login-btn", Button)
            open_webapp_btn = self.query_one("#open-webapp-btn", Button)

            if self.auth_data is None:
                status_label.update("Not logged in")
                login_btn.disabled = False or not self.site_api_healthy
                open_webapp_btn.disabled = True
                return

            if is_logged_in(self.auth_data):
                email = self.auth_data.get("email", "Unknown user")
                api_key = self.auth_data.get("apiKey", "")
                masked_key = f"{api_key[:8]}...{api_key[-5:]}" if api_key else "None"

                status_label.update(f"Logged in as: {email} (API Key: {masked_key})")
                login_btn.disabled = True
                open_webapp_btn.disabled = False
            else:
                status_label.update("Not logged in")
                login_btn.disabled = False or not self.site_api_healthy
                open_webapp_btn.disabled = True
        except NoMatches:
            logger.debug("Could not update auth status: UI not ready")

    def _update_ui_status(self, message: str, element_id: str) -> None:
        """Update UI status element with a message"""
        update_ui_element(self, element_id, message)

    def _restart_local_server(self) -> bool:
        """Restart the local API server if it died"""
        try:
            if self.server_thread is not None and not self.server_thread.is_alive():
                logger.info("Previous server thread died, starting a new one")
                self.server_thread = run_server_in_thread()
                # Give it a moment to start
                time.sleep(1)
                return True
            return False
        except Exception as restart_err:
            logger.error(f"Failed to restart local API: {restart_err}")
            return False

    def _restart_webapp_server(self) -> bool:
        """Restart the WebApp server if it died"""
        try:
            if self.webapp_thread is not None and not self.webapp_thread.is_alive():
                logger.info("Previous WebApp thread died, starting a new one")
                self.webapp_thread = run_webapp_in_thread()
                # Give it a moment to start
                time.sleep(1)
                return True
            return False
        except Exception as restart_err:
            logger.error(f"Failed to restart WebApp server: {restart_err}")
            return False

    def _update_webapp_status(self):
        """Update the WebApp status in the UI based on current state"""
        try:
            webapp_status = self.query_one("#webapp-health", Static)
            open_webapp_btn = self.query_one("#open-webapp-btn", Button)

            # Check if webview is already open
            if is_webview_open():
                webapp_status.update(UI_STATUS["WEBAPP_OPEN"])
                open_webapp_btn.disabled = False  # Keep enabled for focus functionality
                open_webapp_btn.label = BUTTON_LABELS["SHOW_WINDOW"]
            else:
                webapp_status.update(UI_STATUS["WEBAPP_READY"])
                open_webapp_btn.disabled = False
                open_webapp_btn.label = BUTTON_LABELS["OPEN_WINDOW"]
        except NoMatches:
            logger.debug("Could not update WebApp status: UI component not found")

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
                update_ui_fn=lambda msg: self._update_ui_status(msg, "site-health"),
            )

            # Update local API health status
            self.local_api_healthy = check_and_update_api_status(
                api_name="Local API",
                api_url=local_url,
                is_local=True,
                update_ui_fn=lambda msg: self._update_ui_status(msg, "local-health"),
                restart_server_fn=self._restart_local_server,
            )

            # Check WebApp health status
            webapp_healthy = check_and_update_api_status(
                api_name="WebApp",
                api_url=webapp_url,
                is_local=True,
                update_ui_fn=lambda msg: self._update_ui_status(msg, "webapp-health"),
                restart_server_fn=self._restart_webapp_server,
            )

            # Update WebApp status including whether the webview is open
            if webapp_healthy:
                self._update_webapp_status()

            # Update login button state based on API health
            self._update_auth_status()

            # Update login button specifically based on site API health
            try:
                login_btn = self.query_one("#login-btn", Button)
                open_webapp_btn = self.query_one("#open-webapp-btn", Button)

                if not self.site_api_healthy:
                    login_btn.disabled = True
                    logger.warning("Login disabled because Site API is not available")
                elif not self.is_logged_in:
                    login_btn.disabled = False

                # Enable/disable Open window button based on WebApp health
                open_webapp_btn.disabled = not webapp_healthy
            except NoMatches:
                pass

        except Exception as e:
            logger.error(f"Error checking health: {e}")

    def on_mount(self) -> None:
        self.title = f"🥦 Brocc v{get_version()}"
        self._update_auth_status()

        # Set up system tray icon in its own process
        self._setup_systray()

        # Start the FastAPI server in a background thread
        try:
            logger.info("Starting FastAPI server...")
            self.server_thread = run_server_in_thread()

            # Wait a moment to give the server time to start
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"Failed to start FastAPI server: {e}")

        # Start the FastHTML WebApp server in a separate thread
        try:
            logger.info("Starting FastHTML WebApp server...")
            self.webapp_thread = run_webapp_in_thread()

            # Wait a moment to give the server time to start
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"Failed to start FastHTML WebApp server: {e}")

        # Check health status initially
        self.run_worker(self._check_health_worker, thread=True)

        # Set up periodic health check to detect webview closure
        self.set_interval(2.0, self._check_webview_status)

        # Launch webview if already logged in
        if self.is_logged_in:
            # Launch with a small delay to allow servers to start
            self.set_timer(1, self._maybe_launch_webview)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Call the appropriate action based on button name"""
        button_name = event.button.name
        if button_name:
            action_name = f"action_{button_name}"
            action = getattr(self, action_name, None)
            if action and callable(action):
                logger.debug(f"Button pressed: {button_name}")
                action()

    def _display_auth_url(self, url: str) -> None:
        try:
            auth_url_display = self.query_one("#auth-url-display", Static)
            auth_url_display.update(
                f"🔐 Authentication URL:\n[link={url}]{url}[/link]\n\nClick to open in browser"
            )
        except NoMatches:
            logger.error("Could not display auth URL: UI component not found")

    def _maybe_launch_webview(self):
        """Launch webview if user is logged in and webview not already running"""

        def update_ui():
            self._update_ui_status(
                UI_STATUS["WINDOW_READY"],
                "webapp-health",
            )

        def update_button():
            try:
                open_webapp_btn = self.query_one("#open-webapp-btn", Button)
                open_webapp_btn.disabled = False
                open_webapp_btn.label = BUTTON_LABELS["OPEN_WINDOW"]
            except NoMatches:
                pass

        maybe_launch_webview_if_logged_in(
            is_logged_in=self.is_logged_in, update_ui_fn=update_ui, update_button_fn=update_button
        )

    def _login_worker(self):
        try:
            status_label = self.query_one("#auth-status", Label)
            auth_url_display = self.query_one("#auth-url-display", Static)

            # Check if Site API is healthy before proceeding
            if not self.site_api_healthy:
                status_label.update("[red]Cannot login: Site API is not available[/red]")
                logger.error("Login aborted: Site API is not available")
                return

            # Clear previous URL display
            auth_url_display.update("")

            # Define status update callback
            def update_status(message):
                status_label.update(message)

            # Start login process with callbacks
            auth_data = auth.initiate_login(
                self.API_URL,
                update_status_fn=update_status,
                display_auth_url_fn=self._display_auth_url,
            )

            if auth_data:
                self.auth_data = auth_data
                auth_url_display.update("")
                self._update_auth_status()

                # Launch webview after successful login
                self._maybe_launch_webview()
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
                self._update_auth_status()

                # Handle webview after logout
                def update_ui_status(status):
                    if status == "LOGGED_OUT":
                        self._update_ui_status(
                            UI_STATUS["WINDOW_LOGGED_OUT"],
                            "webapp-health",
                        )
                    elif status == "CLOSED":
                        self._update_ui_status(
                            UI_STATUS["WINDOW_CLOSED"],
                            "webapp-health",
                        )

                def update_button_state():
                    try:
                        open_webapp_btn = self.query_one("#open-webapp-btn", Button)
                        open_webapp_btn.disabled = True
                        open_webapp_btn.label = BUTTON_LABELS["LOGIN_TO_OPEN"]
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
        """Worker to open the WebApp in a separate window or focus existing one"""

        def update_ui_status(message):
            self._update_ui_status(message, "webapp-health")

            # Update button state - keep enabled but change label if needed
            try:
                open_webapp_btn = self.query_one("#open-webapp-btn", Button)

                # If window is now open, update button label
                if is_webview_open():
                    open_webapp_btn.disabled = False  # Keep enabled for focus functionality
                    open_webapp_btn.label = BUTTON_LABELS["SHOW_WINDOW"]
            except NoMatches:
                pass

        open_or_focus_webview(
            ui_status_mapping=UI_STATUS,
            update_ui_fn=update_ui_status,
            previous_status=getattr(self, "_previous_webview_status", None),
        )

    def _check_webview_status(self) -> None:
        """Periodic check of webview status"""
        # Get local api URL
        local_url = get_service_url(FASTAPI_HOST, FASTAPI_PORT)

        # Use the utility function to check webview status and update UI
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
                    open_webapp_btn.label = BUTTON_LABELS["SHOW_WINDOW"]
                elif status_changed:  # Was open before but now closed
                    open_webapp_btn.disabled = False
                    open_webapp_btn.label = BUTTON_LABELS["OPEN_WINDOW"]
            except NoMatches:
                logger.debug("Could not update button: UI component not found")

        result = check_and_update_webview_status(
            api_url=local_url,
            ui_status_mapping=status_mapping,
            update_ui_fn=lambda msg: self._update_ui_status(msg, "webapp-health"),
            update_button_fn=update_button,
            previous_status=getattr(self, "_previous_webview_status", None),
        )

        # Store current status for next check
        self._previous_webview_status = result["is_open"]


if __name__ == "__main__":
    app = BroccApp()
    app.run()
