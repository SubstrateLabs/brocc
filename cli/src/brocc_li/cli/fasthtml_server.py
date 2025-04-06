import threading
import time
from datetime import datetime

import requests
import uvicorn
from fasthtml.common import A, Button, P, Titled, fast_app

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


def create_app():
    """Create a FastHTML app for the App"""
    # Enable Pico CSS for styling
    app, rt = fast_app(pico=True)

    @rt("/")
    def get(action: str = ""):
        """Single page that handles all actions inline without navigation"""
        # Process actions first, if any
        message = None

        if action == "connect":
            # Connect to Chrome
            try:
                requests.post(
                    CHROME_CONNECT_URL,
                    params={"auto_confirm": "true"},
                    timeout=10,
                )
                message = "Connecting to Chrome..."
            except Exception as e:
                logger.error(f"Error connecting to Chrome: {e}")
                message = f"Error connecting to Chrome: {str(e)}"

        # Get the current Chrome status
        try:
            response = requests.get(CHROME_STATUS_URL, timeout=2)
            chrome_data = response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error fetching Chrome status: {e}")
            chrome_data = None
            message = f"Error fetching Chrome status: {str(e)}"

        # Determine status message and button text
        if chrome_data:
            is_running = "not running" not in chrome_data.get("status", "")
            requires_relaunch = chrome_data.get("requires_relaunch", False)

            if not is_running:
                status_text = "Chrome is not running"
                button_text = "Launch Chrome"
            elif requires_relaunch:
                status_text = "Chrome is running without debug port"
                button_text = "Relaunch Chrome"
            else:
                status_text = "Chrome is running with debug port"
                button_text = None  # No button needed
        else:
            status_text = "Error fetching Chrome status"
            button_text = "Retry"
            is_running = False
            requires_relaunch = False

        # Build minimal content
        content = []

        # Message display if we have one
        if message:
            content.append(P(message, style="margin: 0.5rem 0; color: #666;"))

        # Status in top left (with minimal styling)
        content.append(P(f"Status: {status_text}", style="margin: 0.5rem 0;"))

        # Launch/Relaunch button only if needed - using query parameter instead of form submission
        if button_text:
            content.append(
                A(
                    Button(button_text, style="display: inline;"),
                    href="/?action=connect",
                    style="text-decoration: none; margin: 0.5rem 0; display: inline-block;",
                )
            )

        # Build the page without titles - no navigation, only query params
        return Titled("Chrome Manager", *content)

    # This ensures both GET with query params and POST form submissions work
    @rt("/", "POST")
    def post(request, query_params=None):
        """Handle POST submissions and redirect to GET with query params"""
        # Extract form data from the POST request
        body = getattr(request, "body", b"").decode("utf-8", errors="replace")

        # Simple form parsing to extract action
        if body:
            # Parse form data
            action = None
            # Very basic parsing - in a real app you'd use a proper form parser
            if "connect" in body:
                action = "connect"

            # Redirect to the same page with query params
            if action:
                return Titled("", meta_refresh=0, url=f"/?action={action}")

        # Default fallback
        return Titled("", meta_refresh=0, url="/")

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
