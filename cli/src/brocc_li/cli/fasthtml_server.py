import threading
import time
from datetime import datetime

import requests
import uvicorn
from fasthtml.common import A, Button, Div, P, Script, Titled, fast_app

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
CHROME_LAUNCH_URL = f"{API_URL}/chrome/launch"
CHROME_STARTUP_FAQ_URL = f"{API_URL}/chrome/startup-faq"

# --- Style Constants ---
CONTAINER_STYLE = "max-width: 300px;"
SMALL_TEXT_STYLE = "font-size: 0.85em;"
PADDING_BOTTOM = "padding-bottom: 0.5rem;"


def create_app():
    """Create a FastHTML app for the App"""
    # Enable Pico CSS for styling
    app, rt = fast_app(pico=True)

    @rt("/")
    def get(action: str = ""):
        """Single page that handles all actions inline without navigation"""

        # Track if we're currently launching Chrome
        is_launching = False
        is_relaunching = False

        if action == "launch":
            # Launch Chrome
            try:
                logger.debug("User clicked Launch Chrome")
                requests.post(
                    CHROME_LAUNCH_URL,
                    json={"force_relaunch": False},
                    timeout=10,
                )
                is_launching = True
            except Exception as e:
                logger.error(f"Error launching Chrome: {e}")
        elif action == "relaunch":
            # Relaunch Chrome
            try:
                logger.debug("User clicked Relaunch Chrome")
                requests.post(
                    CHROME_LAUNCH_URL,
                    json={"force_relaunch": True},
                    timeout=10,
                )
                is_launching = True
                is_relaunching = True
            except Exception as e:
                logger.error(f"Error relaunching Chrome: {e}")
        elif action == "faq":
            # Open the Chrome startup FAQ
            try:
                requests.post(CHROME_STARTUP_FAQ_URL, timeout=5)
            except Exception as e:
                logger.error(f"Error opening Chrome startup FAQ: {e}")
        elif action == "refresh":
            # Just a manual refresh to pick up latest state
            logger.debug("Manual refresh requested")

        # Build the main page
        return build_page(is_launching, is_relaunching)

    @rt("/status")
    def status():
        """Endpoint for HTMX to poll for status updates"""
        return get_status_content()

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
            if "launch" in body:
                action = "launch"
            elif "relaunch" in body:
                action = "relaunch"
            elif "faq" in body:
                action = "faq"

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


def get_status_content():
    """Get the current Chrome status and generate content"""
    # Get the current Chrome status
    try:
        response = requests.get(CHROME_STATUS_URL, timeout=2)
        chrome_data = response.json() if response.status_code == 200 else None
        logger.debug(f"Chrome status response: {chrome_data}")
    except Exception as e:
        logger.error(f"Error fetching Chrome status: {e}")
        chrome_data = None

    # Determine status message and button text
    if chrome_data:
        is_running = "not running" not in chrome_data.get("status", "")
        requires_relaunch = chrome_data.get("requires_relaunch", False)
        is_connected = chrome_data.get("is_connected", False)

        logger.debug(
            f"Status parsed: is_running={is_running}, requires_relaunch={requires_relaunch}, is_connected={is_connected}"
        )

        if is_connected:
            status_text = "Connected to Chrome"
            button_text = None  # No button needed
        elif not is_running:
            status_text = (
                "Not connected. Brocc needs to launch Chrome to sync your browsing activity."
            )
            button_text = "Launch Chrome"
        elif requires_relaunch:
            status_text = (
                "Not connected. Brocc needs to relaunch Chrome to sync your browsing activity."
            )
            button_text = "Relaunch Chrome"
        else:  # default?
            status_text = "Connected to Chrome"
            button_text = None  # No button needed
    else:
        status_text = "Error checking Chrome status"
        button_text = "Retry"
        is_running = False
        requires_relaunch = False
        is_connected = False

    # Build minimal content
    content = []

    # Only show status text directly if we don't have a button
    # (otherwise it will be shown in the flex layout with the button)
    if not button_text:
        status_div = Div(
            P(status_text),
            style=CONTAINER_STYLE,
        )
        content.append(status_div)

    # Launch/Relaunch button only if needed - using query parameter instead of form submission
    if button_text:
        if is_running and requires_relaunch:
            content.append(
                Div(
                    Div(
                        P(status_text),
                        A(
                            Button(button_text),
                            href="/?action=relaunch",
                        ),
                        style=PADDING_BOTTOM,
                    ),
                    Div(
                        P(
                            "Note: you may lose your open tabs when Brocc relaunches Chrome. To prevent this, check your startup settings:",
                            style=SMALL_TEXT_STYLE,
                        ),
                        A(
                            Button(
                                "FAQ: Chrome startup",
                                style=SMALL_TEXT_STYLE,
                            ),
                            href="/?action=faq",
                        ),
                    ),
                    style=CONTAINER_STYLE,
                )
            )
        else:
            # If not showing settings, add status and button together
            content.append(
                Div(
                    P(status_text),
                    A(
                        Button(button_text),
                        href="/?action=launch",
                    ),
                    style=CONTAINER_STYLE,
                )
            )

    return Div(*content, id="status-container")


def build_page(is_launching=False, is_relaunching=False):
    """Build the complete page with HTMX polling if needed"""
    content = []

    # Create a container for the status that can be updated via HTMX
    status_container = get_status_content()
    content.append(status_container)

    # Add JavaScript polling for launch/relaunch only if needed
    if is_launching or is_relaunching:
        # Create proper JavaScript using the Script component
        timeout = 5000 if is_relaunching else 4000  # 5s for relaunch, 4s for launch
        js_code = f"""
            // Function to check status and reload if connected
            function checkStatusAndReload() {{
                fetch('{CHROME_STATUS_URL}')
                    .then(response => response.json())
                    .then(data => {{
                        if (data.is_connected) {{
                            console.log('Chrome connected! Redirecting to clean URL');
                            // Redirect to base URL instead of reloading
                            // This prevents the action=relaunch param from persisting
                            window.location.href = "/";
                            return;
                        }}
                    }})
                    .catch(err => console.error('Error checking status:', err));
            }}

            // Check immediately and then every 500ms
            checkStatusAndReload();
            const intervalId = setInterval(checkStatusAndReload, 500);
            
            // Stop checking after timeout
            setTimeout(() => {{
                clearInterval(intervalId);
                console.log('Status polling stopped after timeout');
                // Redirect to base URL to refresh state
                window.location.href = "/";
            }}, {timeout});
        """

        # Add the script to the page using FastHTML's Script component
        content.append(Script(js_code))

    # Build the page without title
    return Titled("", *content)


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
