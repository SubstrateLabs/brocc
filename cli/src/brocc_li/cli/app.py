from pathlib import Path

from dotenv import load_dotenv
from platformdirs import user_config_dir
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.css.query import NoMatches
from textual.widgets import Button, Footer, Header, Label, Log, Static, TabbedContent

from brocc_li.cli import auth
from brocc_li.cli.server import HOST, PORT, run_server_in_thread
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
        yield Static(f"Site URL: {self.app_instance.API_URL}", id="site-url")
        yield Static(f"Local API: http://{HOST}:{PORT}", id="api-url")
        yield Container(
            Label("Not logged in", id="auth-status"),
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
    API_PORT = PORT  # Port for the local FastAPI server
    CONFIG_DIR = Path(user_config_dir("brocc"))
    AUTH_FILE = CONFIG_DIR / "auth.json"
    CSS_PATH = "app.tcss"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_data = load_auth_data()
        self.server_thread = None

    def compose(self) -> ComposeResult:
        yield Header()

        with TabbedContent("App", "Logs", id="main-content"):
            yield AppContent(self, id="app-tab")
            yield LogsPanel(id="logs-tab")

        yield Footer()

    def action_request_quit(self) -> None:
        self.exit()

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
                login_btn.disabled = False
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
                login_btn.disabled = False
                logout_btn.disabled = True
        except NoMatches:
            logger.debug("Could not update auth status: UI not ready")

    def on_mount(self) -> None:
        self.title = f"🥦 Brocc v{get_version()}"
        self._update_auth_status()

        # Start the FastAPI server in a background thread
        try:
            logger.info("Starting FastAPI server...")
            self.server_thread = run_server_in_thread()
        except Exception as e:
            logger.error(f"Failed to start FastAPI server: {e}")

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
