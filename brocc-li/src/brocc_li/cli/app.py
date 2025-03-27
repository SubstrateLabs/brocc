from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static, Button, Label
from textual.containers import Container
from dotenv import load_dotenv
import os
import json
import requests
import webbrowser
from pathlib import Path
from brocc_li.utils.logger import logger
from platformdirs import user_config_dir
import time

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
        return (
            self.auth_data is not None
            and "apiKey" in self.auth_data
            and self.auth_data["apiKey"]
        )

    def _update_auth_status(self):
        status_label = self.query_one("#auth-status", Label)
        login_btn = self.query_one("#login-btn", Button)
        logout_btn = self.query_one("#logout-btn", Button)

        if (
            self.auth_data is not None
            and "apiKey" in self.auth_data
            and self.auth_data["apiKey"]
        ):
            email = self.auth_data.get("email", "Unknown user")
            api_key = self.auth_data["apiKey"]
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
        try:
            self.CONFIG_DIR.mkdir(exist_ok=True)
            if self.AUTH_FILE.exists():
                with open(self.AUTH_FILE, "r") as f:
                    self.auth_data = json.load(f)
                logger.info(
                    f"Loaded auth data for user: {self.auth_data.get('email', 'unknown')}"
                )
            else:
                logger.debug("No saved auth data found")
        except Exception as e:
            logger.error(f"Error loading auth data: {e}")
            self.auth_data = None

    def _save_auth_data(self, auth_data) -> None:
        """Save auth data to local file"""
        try:
            self.CONFIG_DIR.mkdir(exist_ok=True)
            with open(self.AUTH_FILE, "w") as f:
                json.dump(auth_data, f)
            self.auth_data = auth_data
            logger.info(
                f"Saved auth data for user: {auth_data.get('email', 'unknown')}"
            )
        except Exception as e:
            logger.error(f"Error saving auth data: {e}")

    def _clear_auth_data(self) -> None:
        """Clear auth data from local file"""
        try:
            if self.AUTH_FILE.exists():
                self.AUTH_FILE.unlink()
            self.auth_data = None
            logger.info("Cleared auth data")
        except Exception as e:
            logger.error(f"Error clearing auth data: {e}")

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

        # Update UI
        status_label.update("Initiating authentication...")
        auth_url_display.update("")

        try:
            # Initial auth request
            target_url = f"{self.API_URL}/auth/cli/start"
            logger.info(f"Connecting to: {target_url}")

            response = requests.get(target_url)

            if response.status_code == 404:
                raise Exception(
                    f"API route not found (404): {target_url}\nIs your Next.js server running?"
                )

            if not response.ok:
                error_text = response.text
                if len(error_text) > 500 and "<!DOCTYPE html>" in error_text:
                    error_text = f"{error_text[:150]}... [HTML content truncated]"
                raise Exception(f"Server returned {response.status_code}: {error_text}")

            data = response.json()
            auth_url = data.get("authUrl")
            session_id = data.get("sessionId")

            if not auth_url or not session_id:
                raise Exception("Invalid response from server")

            status_label.update("Opening browser for authentication...")
            # Display the auth URL in the UI
            self._display_auth_url(auth_url)

            logger.info("Authentication URL ready")
            logger.info("Please open this URL in your browser to authenticate")

            # Open browser
            try:
                webbrowser.open(auth_url)
            except Exception as e:
                logger.error(f"Error opening browser: {e}")
                logger.info(f"Please open this URL manually: {auth_url}")

            status_label.update("Waiting for authentication in browser...")

            # Poll for token
            token = self._poll_for_token(session_id)

            # Clear the auth URL display
            auth_url_display.update("")
            status_label.update("Authentication successful!")

            # Debug auth token info
            logger.debug(
                f"Auth info: {token['userId']} / API key length: {len(token.get('apiKey', ''))}"
            )

            # Check if we have an API key
            api_key = token.get("apiKey")
            if api_key:
                logger.debug(f"API key: {api_key[:8]}...{api_key[-5:]}")
            else:
                logger.warning("No API key received from authentication process")
                status_label.update("Warning: No API key received")

            # Save the token locally
            self._save_auth_data(
                {
                    "accessToken": token["accessToken"],
                    "userId": token["userId"],
                    "email": token.get("email"),
                    "apiKey": token.get("apiKey"),
                    "_source": "browser",
                }
            )

            self._update_auth_status()

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            status_label.update("Authentication failed")
            auth_url_display.update("")

    def _poll_for_token(self, session_id, max_attempts=120):
        """Poll the token endpoint until auth is complete"""
        attempts = 0
        consecutive_errors = 0

        token_url = f"{self.API_URL}/auth/cli/token?sessionId={session_id}"
        logger.info(f"Polling for token at: {token_url}")

        while attempts < max_attempts:
            try:
                logger.debug(f"Poll attempt #{attempts + 1}...")
                response = requests.get(token_url, timeout=10)

                logger.debug(f"Poll response status: {response.status_code}")

                # Handle 404 errors specially on first attempt
                if response.status_code == 404 and attempts == 0:
                    logger.error(f"Error: API route not found (404): {token_url}")
                    raise Exception(
                        f"API route not found: {token_url}\nIs your Next.js server running with the correct routes?"
                    )

                # Reset consecutive errors on successful request
                consecutive_errors = 0

                # Process response
                try:
                    data = response.json()
                    logger.debug(f"Poll response data: {json.dumps(data, indent=2)}")
                except Exception as e:
                    # Handle non-JSON responses
                    text = response.text
                    logger.error(f"Error parsing JSON: {e}")
                    logger.error(f"Response text: {text[:150]}...")
                    raise Exception(
                        f"Server returned non-JSON response: {text[:150]}..."
                    )

                if response.ok and data.get("status") == "complete":
                    logger.success(
                        f"Authentication complete. API key received: {bool(data.get('apiKey'))}"
                    )
                    return {
                        "accessToken": data["accessToken"],
                        "userId": data["userId"],
                        "email": data.get("email"),
                        "apiKey": data.get("apiKey"),
                    }

                # If the response indicates an error, throw it to be caught below
                if not response.ok:
                    raise Exception(
                        f"Server returned {response.status_code}: {json.dumps(data)}"
                    )

                # Wait before trying again
                time.sleep(1)
                attempts += 1

            except Exception as e:
                error_message = str(e)
                is_abort_error = "abort" in error_message or "timeout" in error_message

                if is_abort_error:
                    logger.warning(f"Poll attempt {attempts + 1} timed out")
                else:
                    logger.error(f"Poll attempt {attempts + 1} failed: {e}")

                # Count consecutive errors
                consecutive_errors += 1

                # After 3 consecutive errors, increase wait time
                if consecutive_errors >= 3:
                    # If we've had many consecutive errors, throw to exit the loop
                    if consecutive_errors >= 10:
                        raise Exception(
                            "Connection to authentication server failed repeatedly. Please check your network connection and try again."
                        )

                    # Exponential backoff
                    backoff_delay = min(5, 1 * pow(1.5, consecutive_errors - 3))
                    time.sleep(backoff_delay)
                else:
                    time.sleep(1)

                attempts += 1

        raise Exception("Authentication timed out. Please try again.")

    def _logout_worker(self):
        """Worker to handle logout flow"""
        status_label = self.query_one("#auth-status", Label)

        # Update UI
        status_label.update("Logging out...")

        try:
            # Clear auth data
            self._clear_auth_data()
            status_label.update("Successfully logged out")
            self._update_auth_status()
        except Exception as e:
            logger.error(f"Error during logout: {e}")
            status_label.update("Error during logout")


if __name__ == "__main__":
    app = BroccApp()
    app.run()
