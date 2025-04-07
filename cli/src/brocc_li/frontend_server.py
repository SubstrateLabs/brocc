import threading
import time
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from brocc_li.utils.logger import logger
from brocc_li.utils.version import get_version

# --- Constants ---
WEBAPP_HOST = "127.0.0.1"
WEBAPP_PORT = 8023  # Same port as the previous FastHTML server

# Define static directory (where Vite assets are)
STATIC_DIR = Path(__file__).parent / "static"

# Create FastAPI app
app = FastAPI(title="Brocc Frontend")

# --- Add CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://{WEBAPP_HOST}:{WEBAPP_PORT}",
        "http://127.0.0.1:8023",
        "http://localhost:8023",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static assets directory (where Vite puts assets, js, css files)
if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


# Health check endpoint (to match original functionality)
@app.get("/health")
async def health():
    """Health check endpoint that returns JSON"""
    return {
        "status": "healthy",
        "service": "brocc-webapp",
        "version": get_version(),
        "timestamp": datetime.now().isoformat(),
    }


# Serve index.html for all other paths (SPA routing pattern)
@app.get("/{full_path:path}")
async def serve_index(full_path: str):
    """Serve the index.html for any path to support SPA routing"""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        logger.error(f"index.html not found at {index_file}")
        return JSONResponse(
            {"error": "Frontend assets not found. Run 'make build' to build the frontend."},
            status_code=500,
        )
    return FileResponse(index_file)


# Custom Uvicorn server that doesn't install signal handlers
class NoSignalUvicornServer(uvicorn.Server):
    """Custom Uvicorn server that doesn't install signal handlers"""

    def install_signal_handlers(self):
        # Do nothing, avoiding the signal handling that causes issues in threads
        pass


def start_server(host=WEBAPP_HOST, port=WEBAPP_PORT):
    """Start the static asset server using uvicorn"""
    try:
        # Check if static directory exists
        if not STATIC_DIR.exists():
            logger.warning(
                f"Static directory not found at {STATIC_DIR}. Frontend may not work correctly."
            )

        logger.debug(f"Starting Frontend server at http://{host}:{port}")

        # Configure Uvicorn with our custom server class
        config = uvicorn.Config(
            app=app,
            host=host,
            port=port,
            log_level="error",  # Reduce noise
            access_log=False,
        )

        # Create and run the server with our custom class
        server = NoSignalUvicornServer(config=config)
        server.run()

    except Exception as e:
        logger.error(f"Error starting Frontend server: {e}")


def run_server_in_thread(host=WEBAPP_HOST, port=WEBAPP_PORT):
    """Run the Frontend server in a separate thread"""
    # Use threading instead of multiprocessing to avoid file descriptor issues
    server_thread = threading.Thread(
        target=start_server,
        args=(host, port),
        daemon=True,  # Make sure thread closes when main app closes
        name="brocc-frontend-server",
    )

    logger.debug(f"Creating Frontend server thread for {host}:{port}")
    server_thread.start()
    logger.debug(f"Frontend server thread started with ID: {server_thread.ident}")

    # Give the server a moment to start
    time.sleep(0.5)

    return server_thread
