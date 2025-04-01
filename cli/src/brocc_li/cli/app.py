from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static, Button, Label
from textual.containers import Container
from dotenv import load_dotenv
import os
from pathlib import Path
from platformdirs import user_config_dir
from brocc_li.cli import auth

load_dotenv()


class BroccApp(App):
    TITLE = "🥦 brocc"
    BINDINGS = [
        ("ctrl+c", "request_quit", "Quit"),
        ("l", "login", "Login"),
        ("o", "logout", "Logout"),
    ]
    API_URL = os.getenv("API_URL", "https://brocc.li/api")
    CONFIG_DIR = Path(user_config_dir("brocc"))
    AUTH_FILE = CONFIG_DIR / "auth.json"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_data = None
        self._load_auth_data()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"Site URL: {self.API_URL}", id="site-url")
        yield Container(
            Label("Not logged in", id="auth-status"),
            Button("Login", id="login-btn", variant="primary"),
            Button(
                "Logout",
                id="logout-btn",
                variant="error",
                disabled=not self.is_logged_in,
            ),
            Static("", id="auth-url-display"),
            id="auth-container",
        )
        yield Footer()

    def action_request_quit(self) -> None:
        self.exit()

    def action_login(self) -> None:
        # Create and run a synchronous worker directly
        self.run_worker(self._login_worker, thread=True)

    def action_logout(self) -> None:
        # Create and run a synchronous worker directly
        self.run_worker(self._logout_worker, thread=True)

    @property
    def is_logged_in(self) -> bool:
        return auth.is_logged_in(self.auth_data)

    def _update_auth_status(self):
        status_label = self.query_one("#auth-status", Label)
        login_btn = self.query_one("#login-btn", Button)
        logout_btn = self.query_one("#logout-btn", Button)

        if self.auth_data is None:
            status_label.update("Not logged in")
            login_btn.disabled = False
            logout_btn.disabled = True
            return

        if auth.is_logged_in(self.auth_data):
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

    def on_mount(self) -> None:
        self.title = f"🥦 brocc - {self.API_URL}"
        self._update_auth_status()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "login-btn":
            self.action_login()
        elif event.button.id == "logout-btn":
            self.action_logout()

    def _load_auth_data(self) -> None:
        """Load auth data from local file"""
        self.auth_data = auth.load_auth_data()

    def _display_auth_url(self, url: str) -> None:
        """Display auth URL prominently in the UI"""
        auth_url_display = self.query_one("#auth-url-display", Static)
        auth_url_display.update(
            f"🔐 Authentication URL:\n[link={url}]{url}[/link]\n\nClick to open in browser"
        )

    def _login_worker(self):
        """Worker to handle login flow"""
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

    def _logout_worker(self):
        """Worker to handle logout flow"""
        status_label = self.query_one("#auth-status", Label)

        # Update UI
        status_label.update("Logging out...")

        if auth.logout():
            self.auth_data = None
            status_label.update("Successfully logged out")
            self._update_auth_status()
        else:
            status_label.update("Error during logout")


if __name__ == "__main__":
    app = BroccApp()
    app.run()
