import os
import subprocess
import sys
import tempfile
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
from brocc_li.cli.api_health import check_and_update_api_status
from brocc_li.cli.open_webview import (
    close_webview,
    is_webview_open,
    open_webview,
)
from brocc_li.cli.server import API_HOST, API_PORT, run_server_in_thread
from brocc_li.cli.textual_ui.info_panel import InfoPanel
from brocc_li.cli.textual_ui.logs_panel import LogsPanel
from brocc_li.cli.webui import WEBUI_HOST, WEBUI_PORT
from brocc_li.cli.webui import run_server_in_thread as run_webui_in_thread
from brocc_li.utils.api_url import get_api_url
from brocc_li.utils.auth_data import is_logged_in, load_auth_data
from brocc_li.utils.logger import logger
from brocc_li.utils.version import get_version

load_dotenv()

# Global vars for systray
_SYSTRAY_PROCESS = None


class AppContent(Static):
    def __init__(self, app_instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app_instance = app_instance

    def compose(self) -> ComposeResult:
        yield Container(
            Horizontal(
                Button(
                    label="Open window",
                    id="open-webui-btn",
                    variant="primary",
                    disabled=True,
                    name="open_webui",
                ),
                id="webui-buttons",
            ),
            id="webui-container",
        )


class BroccApp(App):
    TITLE = f"🥦 brocc v{get_version()}"
    BINDINGS = [
        ("ctrl+c", "request_quit", "Quit"),
    ]
    API_URL = get_api_url()
    LOCAL_API_PORT = API_PORT  # Port for the local FastAPI server
    CONFIG_DIR = Path(user_config_dir("brocc"))
    AUTH_FILE = CONFIG_DIR / "auth.json"
    CSS_PATH = ["app.tcss", "textual_ui/info_panel.tcss", "textual_ui/logs_panel.tcss"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_data = load_auth_data()
        self.server_thread = None
        self.webui_thread = None
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
        global _SYSTRAY_PROCESS

        try:
            # Create a temp file to monitor for exit
            fd, self.exit_file = tempfile.mkstemp(prefix="brocc_exit_")
            os.close(fd)  # We just need the path

            # Get the path to the systray launcher
            script_dir = Path(__file__).parent
            launcher_path = script_dir / "systray.py"

            if not launcher_path.exists():
                logger.error(f"Systray launcher script not found at: {launcher_path}")
                return False

            # Get the current Python executable
            python_exe = sys.executable

            # Create the command
            cmd = [
                python_exe,
                str(launcher_path),
                "--host",
                WEBUI_HOST,
                "--port",
                str(WEBUI_PORT),
                "--api-host",
                API_HOST,
                "--api-port",
                str(API_PORT),
                "--version",
                get_version(),
                "--exit-file",
                self.exit_file,
            ]

            logger.info(f"Launching systray process: {' '.join(cmd)}")

            # Launch the process
            _SYSTRAY_PROCESS = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
            )

            # Start a thread to monitor systray process
            def monitor_systray():
                proc = _SYSTRAY_PROCESS  # Local reference
                if not proc:
                    return

                logger.info(f"Monitoring systray process PID: {proc.pid}")

                # Read output
                while proc and proc.poll() is None:
                    try:
                        if proc.stdout:
                            line = proc.stdout.readline().strip()
                            if line:
                                logger.info(f"Systray process: {line}")
                    except (IOError, BrokenPipeError) as e:
                        logger.debug(f"Error reading from systray stdout: {e}")
                        break

                # Process has exited
                exit_code = proc.returncode if proc and proc.returncode is not None else "unknown"
                logger.info(f"Systray process exited with code: {exit_code}")

                # Check for errors
                if proc and proc.stderr:
                    try:
                        error = proc.stderr.read()
                        if error:
                            logger.error(f"Systray process error: {error}")
                    except (IOError, BrokenPipeError) as e:
                        logger.debug(f"Error reading from systray stderr: {e}")

            # Start the monitor thread
            threading.Thread(target=monitor_systray, daemon=True, name="systray-monitor").start()

            # Wait a moment to verify process started
            time.sleep(0.5)

            if _SYSTRAY_PROCESS and _SYSTRAY_PROCESS.poll() is None:
                logger.info("Systray process started successfully")
                return True
            else:
                logger.error("Systray process failed to start")
                return False

        except Exception as e:
            logger.error(f"Failed to launch systray: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return False

    def _close_systray(self):
        """Close the systray process if it's running"""
        global _SYSTRAY_PROCESS

        if _SYSTRAY_PROCESS:
            try:
                logger.info("Terminating systray process")
                _SYSTRAY_PROCESS.terminate()
                # Give it a moment to terminate gracefully
                time.sleep(0.5)
                if _SYSTRAY_PROCESS.poll() is None:
                    logger.info("Systray process still running, killing it")
                    _SYSTRAY_PROCESS.kill()
                _SYSTRAY_PROCESS = None
                return True
            except Exception as e:
                logger.error(f"Error closing systray process: {e}")

        # Remove the exit file if it exists
        if self.exit_file and Path(self.exit_file).exists():
            try:
                Path(self.exit_file).unlink()
            except Exception as e:
                logger.debug(f"Error removing exit file: {e}")

        return False

    def _notify_webview_shutdown(self):
        """Send shutdown message to webview via WebSocket"""
        try:
            # Instead of trying to use the WebSocket connections directly,
            # we'll just make a fire-and-forget API call
            try:
                # Use a completely non-blocking approach with no wait
                import threading

                import requests

                def make_request():
                    try:
                        # Use a very short timeout to avoid hanging
                        requests.post(f"http://{API_HOST}:{API_PORT}/webview/shutdown", timeout=0.5)
                    except Exception:  # Specify exception type
                        # Ignore all errors during shutdown
                        pass

                # Start the thread and don't wait for it
                thread = threading.Thread(target=make_request, daemon=True)
                thread.start()
                # Don't log during shutdown
            except Exception:  # Specify exception type
                # Ignore any errors - we're shutting down anyway
                pass
        except Exception:  # Specify exception type
            # Ignore any errors during shutdown
            pass

    def action_request_quit(self) -> None:
        """Cleanly exit the application, closing all resources"""
        logger.info("Shutdown initiated, closing resources")

        # Mark logger as shutting down to suppress further output
        logger.mark_shutting_down()

        # Set up a timed force exit in case shutdown hangs
        def force_exit():
            time.sleep(3)  # Wait 3 seconds then force exit
            # Don't log this since we're suppressing output
            import os

            os._exit(0)  # Force immediate exit

        # Start force exit timer
        threading.Thread(target=force_exit, daemon=True).start()

        # First try to quickly terminate any active processes
        try:
            # Try direct termination of the webview process
            from brocc_li.cli.server import _WEBVIEW_PROCESS

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
        try:
            if _SYSTRAY_PROCESS and _SYSTRAY_PROCESS.poll() is None:
                # Don't log anything here - suppressed
                _SYSTRAY_PROCESS.terminate()
                # Remove the exit file if it exists
                if self.exit_file and Path(self.exit_file).exists():
                    try:
                        Path(self.exit_file).unlink()
                    except Exception:  # Specify exception type
                        pass
        except Exception:  # Specify exception type
            pass

        # Exit immediately without waiting for anything
        # No logging here
        self.exit()

    def action_check_health(self) -> None:
        self.run_worker(self._check_health_worker, thread=True)

    def action_login(self) -> None:
        self.run_worker(self._login_worker, thread=True)

    def action_logout(self) -> None:
        self.run_worker(self._logout_worker, thread=True)

    def action_open_webui(self) -> None:
        """Action to open the WebUI in a standalone window"""
        self.run_worker(self._open_webui_worker, thread=True)

    @property
    def is_logged_in(self) -> bool:
        return is_logged_in(self.auth_data)

    def _update_auth_status(self):
        try:
            status_label = self.query_one("#auth-status", Label)
            login_btn = self.query_one("#login-btn", Button)
            logout_btn = self.query_one("#logout-btn", Button)
            open_webui_btn = self.query_one("#open-webui-btn", Button)

            if self.auth_data is None:
                status_label.update("Not logged in")
                login_btn.disabled = False or not self.site_api_healthy
                logout_btn.disabled = True
                open_webui_btn.disabled = True
                return

            if is_logged_in(self.auth_data):
                email = self.auth_data.get("email", "Unknown user")
                api_key = self.auth_data.get("apiKey", "")
                masked_key = f"{api_key[:8]}...{api_key[-5:]}" if api_key else "None"

                status_label.update(f"Logged in as: {email} (API Key: {masked_key})")
                login_btn.disabled = True
                logout_btn.disabled = False
                open_webui_btn.disabled = False
            else:
                status_label.update("Not logged in")
                login_btn.disabled = False or not self.site_api_healthy
                logout_btn.disabled = True
                open_webui_btn.disabled = True
        except NoMatches:
            logger.debug("Could not update auth status: UI not ready")

    def _update_ui_status(self, message: str, element_id: str) -> None:
        """Update UI status element with a message"""
        try:
            element = self.query_one(f"#{element_id}", Static)
            element.update(message)
        except NoMatches:
            logger.debug(f"Could not update UI status: element #{element_id} not found")

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

    def _restart_webui_server(self) -> bool:
        """Restart the WebUI server if it died"""
        try:
            if self.webui_thread is not None and not self.webui_thread.is_alive():
                logger.info("Previous WebUI thread died, starting a new one")
                self.webui_thread = run_webui_in_thread()
                # Give it a moment to start
                time.sleep(1)
                return True
            return False
        except Exception as restart_err:
            logger.error(f"Failed to restart WebUI server: {restart_err}")
            return False

    def _update_webui_status(self):
        """Update the WebUI status in the UI based on current state"""
        try:
            webui_status = self.query_one("#webui-health", Static)
            open_webui_btn = self.query_one("#open-webui-btn", Button)

            # Check if webview is already open
            if is_webview_open():
                webui_status.update("WebUI: [green]Open[/green]")
                open_webui_btn.disabled = False  # Keep enabled for focus functionality
                open_webui_btn.label = "Show window"  # Change label to indicate focus behavior
            else:
                webui_status.update("WebUI: [blue]Ready to launch[/blue]")
                open_webui_btn.disabled = False
                open_webui_btn.label = "Open window"
        except NoMatches:
            logger.debug("Could not update WebUI status: UI component not found")

    def _check_health_worker(self):
        """Worker to check health of both APIs"""
        try:
            # Check site API health
            local_url = f"http://{API_HOST}:{API_PORT}"
            webui_url = f"http://{WEBUI_HOST}:{WEBUI_PORT}"  # FastHTML server port

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

            # Check WebUI health status
            webui_healthy = check_and_update_api_status(
                api_name="WebUI",
                api_url=webui_url,
                is_local=True,
                update_ui_fn=lambda msg: self._update_ui_status(msg, "webui-health"),
                restart_server_fn=self._restart_webui_server,
            )

            # Update WebUI status including whether the webview is open
            if webui_healthy:
                self._update_webui_status()

            # Update login button state based on API health
            self._update_auth_status()

            # Update login button specifically based on site API health
            try:
                login_btn = self.query_one("#login-btn", Button)
                open_webui_btn = self.query_one("#open-webui-btn", Button)

                if not self.site_api_healthy:
                    login_btn.disabled = True
                    logger.warning("Login disabled because Site API is not available")
                elif not self.is_logged_in:
                    login_btn.disabled = False

                # Enable/disable Open window button based on WebUI health
                open_webui_btn.disabled = not webui_healthy
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

        # Start the FastHTML WebUI server in a separate thread
        try:
            logger.info("Starting FastHTML WebUI server...")
            self.webui_thread = run_webui_in_thread()

            # Wait a moment to give the server time to start
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"Failed to start FastHTML WebUI server: {e}")

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
        if self.is_logged_in and not is_webview_open():
            logger.info("User is logged in - webview can be launched")
            # Automatic launch often doesn't work well due to threading issues
            # Instead, we'll just enable the button and let the user click it
            try:
                open_webui_btn = self.query_one("#open-webui-btn", Button)
                open_webui_btn.disabled = False
                open_webui_btn.label = "Open window"
                self._update_ui_status(
                    "Window: [blue]Ready to launch[/blue]",
                    "webui-health",
                )
            except NoMatches:
                pass

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

                # Update UI to note webview may still be running
                if is_webview_open():
                    # Prompt user to close the webview
                    self._update_ui_status(
                        "Window: [yellow]Running but logged out, closing automatically...[/yellow]",
                        "webui-health",
                    )
                    # Close the webview since user is no longer logged in
                    if close_webview():
                        self._update_ui_status(
                            "Window: [blue]Closed after logout[/blue]",
                            "webui-health",
                        )
                        # Update button state
                        try:
                            open_webui_btn = self.query_one("#open-webui-btn", Button)
                            open_webui_btn.disabled = True
                            open_webui_btn.label = "Login to open app window"
                        except NoMatches:
                            pass
            else:
                status_label.update("Error during logout")
                logger.error("Error during logout")
        except NoMatches:
            logger.error("Logout failed: UI components not found")

    def _open_webui_worker(self):
        """Worker to open the WebUI in a separate window or focus existing one"""
        logger.info("Opening WebUI in standalone window or focusing existing window")
        success = open_webview()

        if success:
            # Check if it was launched or just focused
            if is_webview_open():
                if (
                    not hasattr(self, "_previous_webview_status")
                    or not self._previous_webview_status
                ):
                    # It was just launched
                    self._update_ui_status(
                        "Window: [green]Launched successfully[/green]", "webui-health"
                    )
                else:
                    # It was already running and focused
                    self._update_ui_status(
                        "Window: [green]Brought to foreground[/green]", "webui-health"
                    )

                # Update button state - keep enabled but change label
                try:
                    open_webui_btn = self.query_one("#open-webui-btn", Button)
                    open_webui_btn.disabled = False  # Keep enabled for focus functionality
                    open_webui_btn.label = "Show window"
                except NoMatches:
                    pass
            else:
                # Launching failed despite success=True
                self._update_ui_status("Window: [yellow]Status unclear[/yellow]", "webui-health")
        else:
            self._update_ui_status("Window: [red]Failed to launch[/red]", "webui-health")

    def _check_webview_status(self) -> None:
        """Periodic check of webview status"""
        # Directly check if webview is still open using the API
        current_status = is_webview_open()

        # Store previous webview state to detect changes
        try:
            # Get the elements we'll need to update
            open_webui_btn = self.query_one("#open-webui-btn", Button)

            # If webview was previously open but now closed
            if (
                not current_status
                and hasattr(self, "_previous_webview_status")
                and self._previous_webview_status
            ):
                logger.info("Detected webview was manually closed by user")

                # Update UI to reflect closed state
                open_webui_btn.disabled = False
                open_webui_btn.label = "Open window"
                self._update_ui_status("Window: [blue]Ready to launch[/blue]", "webui-health")

            # If webview is open, keep button enabled but update label
            elif current_status:
                open_webui_btn.disabled = False  # Keep enabled for focus functionality
                open_webui_btn.label = "Show window"
                self._update_ui_status("Window: [green]Open[/green]", "webui-health")

            # Store current status for next check
            self._previous_webview_status = current_status

        except NoMatches:
            logger.debug("Could not update webview status: UI components not found")
            # Still store the status even if we couldn't update UI
            self._previous_webview_status = current_status


if __name__ == "__main__":
    app = BroccApp()
    app.run()
