import threading
import time
from datetime import datetime

import uvicorn
from fasthtml.common import (
    H2,
    Div,
    P,
    Table,
    Td,
    Th,
    Titled,
    Tr,
    fast_app,
)

from brocc_li.utils.logger import logger
from brocc_li.utils.version import get_version

# --- Constants ---
WEBAPP_HOST = "127.0.0.1"
WEBAPP_PORT = 8023  # Using a different port than the FastAPI server


def create_app():
    """Create a FastHTML app for the App"""
    app, rt = fast_app(pico=True)  # Enable Pico CSS for nice styling

    @rt("/")
    def get():
        # Create a proper page with FastHTML components
        return Titled(
            f"🥦 Brocc v{get_version()}",
            Div(
                P("Welcome to the Brocc CLI Web Interface"),
                P(
                    "This lightweight companion to the CLI provides web access to Brocc functionality."
                ),
                Div(
                    H2("System Info"),
                    Table(
                        Tr(Th("Component"), Th("Value")),
                        Tr(Td("Version"), Td(get_version())),
                        Tr(Td("Server Time"), Td(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))),
                    ),
                    cls="mt-4",
                ),
                cls="container",
            ),
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
        # No need to convert it

        logger.info(f"Starting App server at http://{host}:{port}")

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

    logger.info(f"Creating App server thread for {host}:{port}")
    server_thread.start()
    logger.info(f"App server thread started with ID: {server_thread.ident}")

    # Give the server a moment to start
    time.sleep(0.5)

    return server_thread
