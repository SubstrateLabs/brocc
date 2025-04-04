import time
from pathlib import Path

from dotenv import load_dotenv
from platformdirs import user_config_dir
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.css.query import NoMatches
from textual.widgets import Button, Footer, Header, Label, Log, Static, TabbedContent

from brocc_li.cli import auth
from brocc_li.cli.api_health import check_and_update_api_status
from brocc_li.cli.server import API_HOST, API_PORT, run_server_in_thread
from brocc_li.cli.webui import WEBUI_HOST, WEBUI_PORT
from brocc_li.cli.webui import run_server_in_thread as run_webui_in_thread
from brocc_li.utils.api_url import get_api_url
from brocc_li.utils.auth_data import is_logged_in, load_auth_data
from brocc_li.utils.logger import logger
from brocc_li.utils.version import get_version

load_dotenv()


class AppContent(Static):
    def __init__(self, app_instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app_instance = app_instance

    def compose(self) -> ComposeResult:
        yield Container(
            Horizontal(
                Button(label="Login", id="login-btn", variant="default", name="login"),
                Button(
                    label="Logout",
                    id="logout-btn",
                    variant="default",
                    disabled=not self.app_instance.is_logged_in,
                    name="logout",
                ),
                id="auth-buttons",
            ),
            Static("", id="auth-url-display"),
            id="auth-container",
        )
        yield Container(
            Static("Site API: Checking...", id="site-health"),
            Static("Local API: Checking...", id="local-health"),
            Static("WebUI: Checking...", id="webui-health"),
            Label("Not logged in", id="auth-status"),
            id="health-container",
        )


class LogsPanel(Static):
    def compose(self) -> ComposeResult:
        yield Log(highlight=True, auto_scroll=True, id="app-logs")

    def on_mount(self) -> None:
        log_widget = self.query_one("#app-logs", Log)
        logger.set_log_widget(log_widget)


class BroccApp(App):
    TITLE = f"🥦 brocc v{get_version()}"
    BINDINGS = [
        ("ctrl+c", "request_quit", "Quit"),
    ]
    API_URL = get_api_url()
    LOCAL_API_PORT = API_PORT  # Port for the local FastAPI server
    CONFIG_DIR = Path(user_config_dir("brocc"))
    AUTH_FILE = CONFIG_DIR / "auth.json"
    CSS_PATH = "app.tcss"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_data = load_auth_data()
        self.server_thread = None
        self.webui_thread = None
        self.site_api_healthy = False
        self.local_api_healthy = False

    def compose(self) -> ComposeResult:
        yield Header()

        with TabbedContent("App", "Logs", id="main-content"):
            yield AppContent(self, id="app-tab")
            yield LogsPanel(id="logs-tab")

        yield Footer()

    def action_request_quit(self) -> None:
        self.exit()

    def action_check_health(self) -> None:
        self.run_worker(self._check_health_worker, thread=True)

    def action_login(self) -> None:
        self.run_worker(self._login_worker, thread=True)

    def action_logout(self) -> None:
        self.run_worker(self._logout_worker, thread=True)

    @property
    def is_logged_in(self) -> bool:
        return is_logged_in(self.auth_data)

    def _update_auth_status(self):
        try:
            status_label = self.query_one("#auth-status", Label)
            login_btn = self.query_one("#login-btn", Button)
            logout_btn = self.query_one("#logout-btn", Button)

            if self.auth_data is None:
                status_label.update("Not logged in")
                login_btn.disabled = False or not self.site_api_healthy
                logout_btn.disabled = True
                return

            if is_logged_in(self.auth_data):
                email = self.auth_data.get("email", "Unknown user")
                api_key = self.auth_data.get("apiKey", "")
                masked_key = f"{api_key[:8]}...{api_key[-5:]}" if api_key else "None"

                status_label.update(f"Logged in as: {email} (API Key: {masked_key})")
                login_btn.disabled = True
                logout_btn.disabled = False
            else:
                status_label.update("Not logged in")
                login_btn.disabled = False or not self.site_api_healthy
                logout_btn.disabled = True
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
            check_and_update_api_status(
                api_name="WebUI",
                api_url=webui_url,
                is_local=True,
                update_ui_fn=lambda msg: self._update_ui_status(msg, "webui-health"),
                restart_server_fn=self._restart_webui_server,
            )

            # Update login button state based on API health
            self._update_auth_status()

            # Update login button specifically based on site API health
            try:
                login_btn = self.query_one("#login-btn", Button)
                if not self.site_api_healthy:
                    login_btn.disabled = True
                    logger.warning("Login disabled because Site API is not available")
                elif not self.is_logged_in:
                    login_btn.disabled = False
            except NoMatches:
                pass

        except Exception as e:
            logger.error(f"Error checking health: {e}")

    def on_mount(self) -> None:
        self.title = f"🥦 Brocc v{get_version()}"
        self._update_auth_status()

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

        # Check health status
        self.run_worker(self._check_health_worker, thread=True)

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
            else:
                status_label.update("Error during logout")
                logger.error("Error during logout")
        except NoMatches:
            logger.error("Logout failed: UI components not found")


if __name__ == "__main__":
    app = BroccApp()
    app.run()
