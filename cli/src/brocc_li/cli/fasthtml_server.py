import threading
import time
from datetime import datetime

import requests
import uvicorn
from fasthtml.common import H1, H2, A, Button, Form, Input, P, Span, Titled, fast_app

from brocc_li.utils.logger import logger
from brocc_li.utils.version import get_version

# --- Constants ---
WEBAPP_HOST = "127.0.0.1"
WEBAPP_PORT = 8023  # Using a different port than the FastAPI server
API_HOST = "127.0.0.1"
API_PORT = 8022  # FastAPI server port

# API endpoint URLs
API_URL = f"http://{API_HOST}:{API_PORT}"
CHROME_STATUS_URL = f"{API_URL}/chrome/status"
CHROME_CONNECT_URL = f"{API_URL}/chrome/connect"
CHROME_DISCONNECT_URL = f"{API_URL}/chrome/disconnect"


def create_app():
    """Create a FastHTML app for the App"""
    # Enable Pico CSS for styling
    app, rt = fast_app(pico=True)

    @rt("/")
    def get():
        """Main page with Chrome Manager UI - no JavaScript"""
        # Get the current Chrome status directly
        try:
            response = requests.get(CHROME_STATUS_URL, timeout=2)
            chrome_data = response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error fetching Chrome status: {e}")
            chrome_data = None

        # Determine status message and styling
        if chrome_data:
            status_text = chrome_data.get("status", "Unknown")
            is_connected = chrome_data.get("is_connected", False)
            requires_relaunch = chrome_data.get("requires_relaunch", False)
            connection_status = "Connected" if is_connected else "Not Connected"
        else:
            status_text = "Error fetching status"
            is_connected = False
            requires_relaunch = False
            connection_status = "Unknown"

        # Title and header
        title = "Chrome Manager"

        # Status section
        status_content = [
            H1(title),
            H2("Chrome Status"),
            P(f"Status: {status_text}"),
            P(f"Connection: {connection_status}"),
            P(f"Last Updated: {datetime.now().strftime('%H:%M:%S')}"),
        ]

        # Action buttons based on connection state
        if is_connected:
            # Already connected - show disconnect option
            status_content.extend(
                [
                    Form(
                        Button("Disconnect from Chrome", type="submit"),
                        action="/disconnect",
                        method="post",
                    )
                ]
            )
        else:
            # Not connected - show connect form
            connect_form = Form(
                H2("Connect to Chrome"),
                P("Connect to an existing Chrome instance with remote debugging enabled"),
                Button("Connect to Chrome", type="submit"),
                action="/connect",
                method="post",
            )

            # If relaunch required, show the auto-confirm option
            if requires_relaunch:
                connect_form = Form(
                    H2("Connect to Chrome (Relaunch Required)"),
                    P("Chrome needs to be relaunched with remote debugging enabled"),
                    Input(type="checkbox", id="auto-confirm", name="auto_confirm", value="true"),
                    Span("Auto-confirm when restarting Chrome"),
                    Button("Connect to Chrome", type="submit"),
                    action="/connect",
                    method="post",
                )

            status_content.append(connect_form)

        # Refresh button
        status_content.append(A("Refresh Status", href="/"))

        # Build the page
        return Titled(title, *status_content)

    @rt("/connect", "POST")
    def connect(auto_confirm: bool = False):
        """Connect to Chrome with auto_confirm option"""
        try:
            logger.debug(f"Connecting to Chrome with auto_confirm={auto_confirm}")
            response = requests.post(
                CHROME_CONNECT_URL,
                params={"auto_confirm": "true" if auto_confirm else "false"},
                timeout=10,  # Longer timeout as connection can take time
            )

            logger.debug(f"Chrome connect response: {response.status_code}")
            message = "Connected to Chrome"

            content = [H1("Chrome Connection"), P(message), A("Return to Chrome Manager", href="/")]

            # Return with meta refresh to redirect back home after 2 seconds
            return Titled("Chrome Connection", *content, meta_refresh=2)
        except Exception as e:
            logger.error(f"Error connecting to Chrome: {e}")
            return Titled(
                "Connection Error",
                H1("Connection Error"),
                P(f"Error: {str(e)}"),
                A("Try Again", href="/"),
                meta_refresh=5,
            )

    @rt("/disconnect", "POST")
    def disconnect():
        """Disconnect from Chrome"""
        try:
            logger.debug("Disconnecting from Chrome")
            response = requests.post(CHROME_DISCONNECT_URL, timeout=5)

            logger.debug(f"Chrome disconnect response: {response.status_code}")
            message = "Disconnected from Chrome"

            content = [
                H1("Chrome Disconnected"),
                P(message),
                A("Return to Chrome Manager", href="/"),
            ]

            # Return with meta refresh to redirect back home after 2 seconds
            return Titled("Disconnected", *content, meta_refresh=2)
        except Exception as e:
            logger.error(f"Error disconnecting from Chrome: {e}")
            return Titled(
                "Disconnection Error",
                H1("Disconnection Error"),
                P(f"Error: {str(e)}"),
                A("Try Again", href="/"),
                meta_refresh=5,
            )

    @rt("/health")
    def health():
        """Health check endpoint that returns JSON"""
        return {
            "status": "healthy",
            "service": "brocc-webapp",
            "version": get_version(),
            "timestamp": datetime.now().isoformat(),
        }

    return app


class NoSignalUvicornServer(uvicorn.Server):
    """Custom Uvicorn server that doesn't install signal handlers"""

    def install_signal_handlers(self):
        # Do nothing, avoiding the signal handling that causes issues in threads
        pass


def start_server(host=WEBAPP_HOST, port=WEBAPP_PORT):
    """Start the FastHTML server using a custom uvicorn configuration"""
    try:
        # Create and configure the app
        app = create_app()

        # FastHTML app is already ASGI-compatible
        logger.debug(f"Starting App server at http://{host}:{port}")

        # Configure Uvicorn with our custom server class
        config = uvicorn.Config(
            app=app,  # FastHTML app is ASGI-compatible
            host=host,
            port=port,
            log_level="error",  # Reduce noise
            access_log=False,
        )

        # Create and run the server with our custom class
        server = NoSignalUvicornServer(config=config)
        server.run()

    except Exception as e:
        logger.error(f"Error starting App server: {e}")


def run_server_in_thread(host=WEBAPP_HOST, port=WEBAPP_PORT):
    """Run the App server in a separate thread"""
    # Use threading instead of multiprocessing to avoid file descriptor issues
    server_thread = threading.Thread(
        target=start_server,
        args=(host, port),
        daemon=True,  # Make sure thread closes when main app closes
        name="brocc-webapp-server",
    )

    logger.debug(f"Creating App server thread for {host}:{port}")
    server_thread.start()
    logger.debug(f"App server thread started with ID: {server_thread.ident}")

    # Give the server a moment to start
    time.sleep(0.5)

    return server_thread
