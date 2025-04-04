import threading

import uvicorn
from fastapi import FastAPI

from brocc_li.utils.logger import logger
from brocc_li.utils.version import get_version

# --- Constants ---
HOST = "127.0.0.1"
PORT = 8022

# --- Server ---
app = FastAPI(
    title="Brocc Internal API",
    description="These APIs are subject to change without notice. Use at your own risk.",
    version=get_version(),
)


# --- Routes ---
@app.get("/")
async def root():
    return {"message": "Welcome to Brocc API"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "brocc-api", "version": get_version()}


# --- Server functions ---
def start_server(host=HOST, port=PORT):
    """Start the FastAPI server"""
    try:
        logger.info(f"Starting FastAPI server, docs: http://{host}:{port}/docs")
        uvicorn.run(app, host=host, port=port, log_level="error")  # Reduce uvicorn logs
    except OSError as e:
        if "address already in use" in str(e).lower():
            logger.error(f"Port {port} is already in use! Cannot start server.")
        else:
            logger.error(f"Network error starting FastAPI server: {e}")
    except Exception as e:
        logger.error(f"Error starting FastAPI server: {e}")


def run_server_in_thread(host=HOST, port=PORT):
    """Run the server in a separate thread"""
    logger.info(f"Creating server thread for {host}:{port}")
    server_thread = threading.Thread(
        target=start_server,
        args=(host, port),
        daemon=True,  # Make sure thread closes when main app closes
        name="brocc-api-server",
    )
    server_thread.start()
    logger.info(f"Server thread started with ID: {server_thread.ident}")
    return server_thread
