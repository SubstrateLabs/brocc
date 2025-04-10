import threading
import time

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from brocc_li.fastapi_auth import router as auth_router
from brocc_li.fastapi_chrome import router as chrome_router
from brocc_li.fastapi_webview import router as webview_router
from brocc_li.utils.logger import logger
from brocc_li.utils.version import get_version

# --- Constants ---
FASTAPI_HOST = "127.0.0.1"
FASTAPI_PORT = 8022
WEBAPP_HOST = "127.0.0.1"
WEBAPP_PORT = 8023

# --- Server ---
app = FastAPI(
    title="Brocc Internal API",
    description="These APIs are subject to change without notice. Use at your own risk.",
    version=get_version(),
)

# --- Add CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://{WEBAPP_HOST}:{WEBAPP_PORT}",  # FastHTML UI server
        "http://127.0.0.1:8023",
        "http://localhost:8023",
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers
app.include_router(chrome_router)
app.include_router(webview_router)
app.include_router(auth_router)


# --- Routes ---
@app.get("/")
async def root():
    return {"message": "Welcome to Brocc API"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "brocc-api", "version": get_version()}


@app.get("/ping")
async def ping():
    """Simple endpoint to check if the API is responding"""
    return {"ping": "pong", "time": time.time()}


@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup"""
    # Initialize Chrome connection using the async function
    from brocc_li.fastapi_chrome import try_initial_connect

    await try_initial_connect(quiet=False)


# --- Server functions ---
def start_server(host=FASTAPI_HOST, port=FASTAPI_PORT):
    """Start the FastAPI server"""
    try:
        logger.debug(f"Starting FastAPI server, docs: http://{host}:{port}/docs")
        uvicorn.run(app, host=host, port=port, log_level="error")  # Reduce uvicorn logs
    except OSError as e:
        if "address already in use" in str(e).lower():
            logger.error(f"Port {port} is already in use! Cannot start server.")
        else:
            logger.error(f"Network error starting FastAPI server: {e}")
    except Exception as e:
        logger.error(f"Error starting FastAPI server: {e}")


def run_server_in_thread(host=FASTAPI_HOST, port=FASTAPI_PORT):
    """Run the server in a separate thread"""
    logger.debug(f"Creating server thread for {host}:{port}")
    server_thread = threading.Thread(
        target=start_server,
        args=(host, port),
        daemon=True,  # Make sure thread closes when main app closes
        name="brocc-api-server",
    )
    server_thread.start()
    logger.debug(f"Server thread started with ID: {server_thread.ident}")
    return server_thread
