import asyncio
import atexit
import concurrent.futures
import functools
import os
import platform
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import psutil
import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from starlette.middleware.cors import CORSMiddleware

from brocc_li.chrome_cdp import get_chrome_info
from brocc_li.chrome_manager import ChromeManager
from brocc_li.chrome_tabs import ChromeTabs
from brocc_li.utils.chrome import launch_chrome, quit_chrome
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

# --- ChromeManager singleton - enable auto-connect ---
chrome_manager = ChromeManager(auto_connect=True)

# Thread pool for running sync code
_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)

# Store active tab monitoring tasks
_tab_monitoring_tasks = {}


# Helper function to check if Chrome is connected
def is_chrome_connected():
    """Check if Chrome is connected and usable"""
    return chrome_manager.connected


# Try initial auto-connect on server start
def _try_initial_connect(quiet=True):
    """Try to auto-connect to Chrome on server start"""
    try:
        state = chrome_manager.refresh_state()
        if state.has_debug_port:
            # Connect with quiet parameter
            is_connected = chrome_manager.test_connection(quiet=quiet)
            if is_connected:
                if not quiet:
                    logger.debug("Successfully auto-connected to Chrome on server start")
                return True
    except Exception as e:
        if not quiet:
            logger.error(f"Error during initial auto-connect: {e}")

    return False


# Call auto-connect on module load with quiet=True to suppress logs during import
_try_initial_connect(quiet=True)


# Helper function to run sync code in a thread pool
def run_sync(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return _thread_pool.submit(func, *args, **kwargs).result()

    return wrapper


# Helper function to properly await ThreadPoolExecutor futures
async def run_in_executor(executor, func, *args, **kwargs):
    """Properly awaits for ThreadPoolExecutor futures."""
    return await asyncio.wrap_future(executor.submit(func, *args, **kwargs))


# Async-safe version of _launch_chrome_in_thread
async def _launch_chrome_async(force_relaunch: bool = False):
    """Launch Chrome in a thread pool to avoid sync/async issues"""
    # Run the sync code in a thread pool with proper awaiting
    await run_in_executor(app.state.thread_pool, _launch_chrome_in_thread, force_relaunch)


# --- Webview Management ---
_WEBVIEW_ACTIVE = False
_WEBVIEW_PROCESS = None


# Register cleanup function to ensure webview is terminated on server exit
def _cleanup_webview():
    global _WEBVIEW_ACTIVE, _WEBVIEW_PROCESS

    # Terminate the process
    if _WEBVIEW_PROCESS:
        try:
            if _WEBVIEW_PROCESS.poll() is None:
                logger.debug(f"Terminating webview process (PID: {_WEBVIEW_PROCESS.pid})")
                _WEBVIEW_PROCESS.terminate()
                # Don't wait longer than 1 second - we need to exit
                try:
                    _WEBVIEW_PROCESS.wait(1.0)
                except subprocess.TimeoutExpired:
                    logger.warning("Webview process did not terminate gracefully, forcing kill")
                    _WEBVIEW_PROCESS.kill()

            _WEBVIEW_ACTIVE = False
            _WEBVIEW_PROCESS = None
        except Exception as e:
            logger.error(f"Error terminating webview process: {e}")


atexit.register(_cleanup_webview)


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


# --- Routes ---
@app.post("/webview/launch")
async def launch_webview(
    background_tasks: BackgroundTasks, webapp_url: str = "http://127.0.0.1:8023", title: str = ""
):
    """Launch a webview window pointing to the App"""
    global _WEBVIEW_ACTIVE, _WEBVIEW_PROCESS

    # Check if already active
    if _WEBVIEW_ACTIVE and _WEBVIEW_PROCESS and _WEBVIEW_PROCESS.poll() is None:
        # Try to focus the existing window
        focused = _focus_webview_window()
        if focused:
            return {"status": "focused", "message": "Brought existing webview to the foreground"}
        else:
            return {
                "status": "already_running",
                "message": "Webview is already running but couldn't bring to foreground",
            }

    # Reset state if process has terminated
    if _WEBVIEW_PROCESS and _WEBVIEW_PROCESS.poll() is not None:
        _WEBVIEW_ACTIVE = False
        _WEBVIEW_PROCESS = None

    # Launch in a background task to not block the response
    background_tasks.add_task(
        _launch_webview_process, webapp_url, title if title else f"🥦 Brocc v{get_version()}"
    )

    return {"status": "launching", "message": "Launching webview process"}


@app.post("/webview/focus")
async def focus_webview():
    """Focus the webview window if it's running"""
    global _WEBVIEW_ACTIVE, _WEBVIEW_PROCESS

    if not _WEBVIEW_ACTIVE or not _WEBVIEW_PROCESS or _WEBVIEW_PROCESS.poll() is not None:
        return {"status": "not_running", "message": "No webview process is running"}

    if _focus_webview_window():
        return {"status": "focused", "message": "Brought webview to the foreground"}
    else:
        return {"status": "error", "message": "Couldn't focus webview window"}


@app.get("/webview/status")
async def webview_status():
    """Check if the webview is currently running"""
    global _WEBVIEW_ACTIVE, _WEBVIEW_PROCESS

    # Update status if needed
    if _WEBVIEW_ACTIVE and _WEBVIEW_PROCESS and _WEBVIEW_PROCESS.poll() is not None:
        _WEBVIEW_ACTIVE = False
        _WEBVIEW_PROCESS = None

    return {
        "active": _WEBVIEW_ACTIVE,
        "process_running": _WEBVIEW_PROCESS is not None and _WEBVIEW_PROCESS.poll() is None,
    }


@app.post("/webview/close")
async def close_webview():
    """Close the webview if it's running"""
    global _WEBVIEW_ACTIVE, _WEBVIEW_PROCESS

    if not _WEBVIEW_PROCESS:
        return {"status": "not_running", "message": "No webview process is running"}

    try:
        _WEBVIEW_PROCESS.terminate()
        _WEBVIEW_ACTIVE = False
        _WEBVIEW_PROCESS = None
        return {"status": "closed", "message": "Webview process terminated"}
    except Exception as e:
        logger.error(f"Error closing webview: {e}")
        return {"status": "error", "message": f"Error closing webview: {e}"}


# --- Helper Functions ---
def _focus_webview_window():
    """
    Platform-specific function to focus the webview window
    Returns True if successful, False otherwise
    """
    global _WEBVIEW_PROCESS

    if not _WEBVIEW_PROCESS:
        return False

    try:
        system = platform.system()

        if system == "Darwin":  # macOS
            # AppleScript to activate the app
            script = """
            tell application "System Events"
                set frontmost of every process whose unix id is {0} to true
            end tell
            """.format(_WEBVIEW_PROCESS.pid)

            subprocess.run(["osascript", "-e", script], check=False)
            logger.debug(f"Focused macOS webview window for PID {_WEBVIEW_PROCESS.pid}")
            return True

        elif system == "Windows":
            # On Windows, we can use pywin32, but we'll use a direct command approach here
            # using pythonw.exe's window title to find it
            try:
                # First try with psutil to get all window titles
                proc = psutil.Process(_WEBVIEW_PROCESS.pid)
                # Then use powershell to focus the window by process ID
                ps_cmd = f"(Get-Process -Id {proc.pid} | Where-Object {{$_.MainWindowTitle}} | ForEach-Object {{ (New-Object -ComObject WScript.Shell).AppActivate($_.MainWindowTitle) }})"
                subprocess.run(["powershell", "-command", ps_cmd], check=False)
                logger.debug(f"Focused Windows webview window for PID {_WEBVIEW_PROCESS.pid}")
                return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                logger.error("Could not focus webview window - process not found or access denied")
                return False

        elif system == "Linux":
            # For Linux, we'd use wmctrl but it's not always available
            # We could also try xdotool
            try:
                proc = psutil.Process(_WEBVIEW_PROCESS.pid)
                # Try using wmctrl (if installed)
                subprocess.run(["wmctrl", "-i", "-a", str(proc.pid)], check=False)
                logger.debug(f"Focused Linux webview window for PID {_WEBVIEW_PROCESS.pid}")
                return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError):
                logger.error(
                    "Could not focus webview window - wmctrl not available or process issue"
                )
                return False

        logger.warning(f"No focus implementation for platform: {system}")
        return False

    except Exception as e:
        logger.error(f"Error focusing webview window: {e}")
        return False


def _launch_webview_process(webapp_url, title):
    """Launch the webview process and monitor it"""
    global _WEBVIEW_ACTIVE, _WEBVIEW_PROCESS

    try:
        # Use the known location in cli directory
        launcher_path = Path(__file__).parent / "cli" / "webview_process.py"

        if not launcher_path.exists():
            logger.error(f"Webview process script not found at: {launcher_path}")
            return

        # Get the current Python executable
        python_exe = sys.executable

        # Get this process's PID to pass to the child process
        current_pid = os.getpid()

        # Create the command - include current PID for parent monitoring
        cmd = [
            python_exe,
            str(launcher_path),
            webapp_url,
            title,
            str(current_pid),  # Pass current PID as parent to monitor
        ]

        logger.debug(f"Launching webview process with command: {' '.join(cmd)}")

        # Launch the process
        _WEBVIEW_PROCESS = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
        )

        # Set active flag
        _WEBVIEW_ACTIVE = True

        # Monitor the process output and status
        def monitor_process():
            global _WEBVIEW_ACTIVE
            proc = _WEBVIEW_PROCESS  # Local reference

            if not proc:
                return

            logger.debug(f"Monitoring webview process PID: {proc.pid}")

            # Read output
            while proc and proc.poll() is None:
                try:
                    if proc.stdout:
                        line = proc.stdout.readline().strip()
                        if line:
                            logger.debug(f"Webview process: {line}")
                except (IOError, BrokenPipeError) as e:
                    logger.debug(f"Error reading from webview stdout: {e}")
                    break

            # Process has exited
            exit_code = proc.returncode if proc and proc.returncode is not None else "unknown"
            logger.debug(f"Webview process exited with code: {exit_code}")

            # Check for errors
            if proc and proc.stderr:
                try:
                    error = proc.stderr.read()
                    if error:
                        logger.error(f"Webview process error: {error}")
                except (IOError, BrokenPipeError) as e:
                    logger.debug(f"Error reading from webview stderr: {e}")

            # Update state
            _WEBVIEW_ACTIVE = False

        # Start monitor thread
        threading.Thread(target=monitor_process, daemon=True, name="webview-monitor").start()

    except Exception as e:
        logger.error(f"Failed to launch webview: {e}")
        _WEBVIEW_ACTIVE = False
        _WEBVIEW_PROCESS = None


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


# --- Chrome Manager API ---
@app.get("/chrome/status")
async def chrome_status():
    """Get the current status of Chrome connection"""
    # Refresh the state which might auto-connect if configured
    # Run the refresh in a thread pool to avoid sync/async issues
    try:
        await run_in_executor(app.state.thread_pool, chrome_manager.refresh_state)
    except Exception as e:
        logger.error(f"Error refreshing Chrome state: {e}")

    # Get status code
    status_code = chrome_manager.status_code

    return {
        "status_code": status_code.value,  # Return the string value of the enum
        "timestamp": time.time(),
    }


@app.post("/chrome/launch")
async def chrome_launch_endpoint(
    request: Request, background_tasks: BackgroundTasks, force_relaunch: bool = False
):
    """
    Launch Chrome with a debug port or connect to an existing instance.

    If force_relaunch is True, will quit existing Chrome instances and start fresh.
    Otherwise, it will try to connect to an existing Chrome if possible.
    """
    # Try to extract force_relaunch from JSON body if it wasn't in query params
    if not force_relaunch:
        try:
            body = await request.json()
            if isinstance(body, dict) and "force_relaunch" in body:
                force_relaunch = bool(body["force_relaunch"])
        except Exception:
            # No valid JSON body or other error, stick with default
            pass

    # For regular (non-forced) launch, check if already connected
    if not force_relaunch:
        # Check if already connected - run this in thread pool to avoid async issues
        try:
            chrome_connected = await run_in_executor(app.state.thread_pool, is_chrome_connected)
            if chrome_connected:
                return {"status": "already_connected", "message": "Already connected to Chrome"}
        except Exception as e:
            logger.debug(f"Error checking Chrome connection: {e}")

    # Use a helper function to run the sync operation safely from an async context
    async def run_in_thread():
        try:
            await run_in_executor(app.state.thread_pool, _launch_chrome_in_thread, force_relaunch)
        except Exception as e:
            logger.error(f"Error running Chrome launch in thread: {e}")

    # Run the launch operation in the background
    background_tasks.add_task(run_in_thread)

    return {
        "status": "launching",
        "message": f"{'Relaunching' if force_relaunch else 'Launching'} Chrome in background",
    }


def _launch_chrome_in_thread(force_relaunch: bool = False):
    """Launch or relaunch Chrome in a background thread"""
    try:
        logger.debug(f"Starting Chrome {'relaunch' if force_relaunch else 'launch'} process")

        # Get the current state
        state = chrome_manager.refresh_state()
        logger.debug(
            f"Chrome state: running={state.is_running}, has_debug_port={state.has_debug_port}"
        )

        # If we're forcing a relaunch or Chrome is running without debug port
        if force_relaunch or (state.is_running and not state.has_debug_port):
            logger.debug("Quitting existing Chrome instances")

            # Quit all Chrome instances directly
            if not quit_chrome():
                logger.error("Failed to quit existing Chrome instances")
                return

            logger.debug("Successfully quit existing Chrome instances")

            # Chrome needs to be launched with debug port
            needs_launch = True
        else:
            # If Chrome is not running, we need to launch it
            needs_launch = not state.is_running
            logger.debug(f"Chrome needs launch: {needs_launch}")

        # Launch Chrome if needed
        if needs_launch:
            logger.debug("Launching Chrome with debug port")
            if not launch_chrome():
                logger.error("Failed to launch Chrome")
                return

            # Give Chrome a moment to initialize - longer time for relaunch
            wait_time = 3 if force_relaunch else 2
            logger.debug(f"Waiting {wait_time}s for Chrome to initialize")
            time.sleep(wait_time)
        else:
            logger.debug("Chrome already running with debug port, skipping launch")

        # Now connect to Chrome
        logger.debug("Attempting to connect to Chrome")
        try:
            connected = chrome_manager.test_connection(quiet=True)
            if connected:
                chrome_info = get_chrome_info()
                logger.debug(f"Successfully connected to Chrome {chrome_info['version']}")
            else:
                logger.error("Failed to connect to Chrome")
        except Exception as e:
            logger.error(f"Error connecting to Chrome: {e}")
    except Exception as e:
        logger.error(f"Error in Chrome launch thread: {e}")
        # Add stack trace for better debugging
        import traceback

        logger.error(f"Stack trace: {traceback.format_exc()}")


@app.post("/chrome/startup-faq")
async def chrome_startup_faq():
    """Open the Chrome startup FAQ page in the default web browser"""
    try:
        webbrowser.open("https://brocc.li/faq#chrome-startup")
        return {"status": "success", "message": "Opened Chrome startup FAQ in browser"}
    except Exception as e:
        logger.error(f"Error opening Chrome startup FAQ: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error opening Chrome startup FAQ: {str(e)}"
        ) from e


@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup"""
    # Create a thread pool for running sync code in async context
    app.state.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    logger.debug("Thread pool initialized for sync operations")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    # Shutdown the thread pool
    if hasattr(app.state, "thread_pool"):
        app.state.thread_pool.shutdown(wait=False)
        logger.debug("Thread pool shutdown")

    # Close any active WebSocket connections
    for _client_id, client in list(_tab_monitoring_tasks.items()):
        try:
            client["stop_event"].set()
            await client["websocket"].close()
        except Exception as e:
            logger.debug(f"Error closing websocket: {e}")
    _tab_monitoring_tasks.clear()


@app.get("/chrome/tabs")
async def get_chrome_tabs(include_html: bool = False):
    """
    Get all open Chrome tabs with optional HTML content.

    Args:
        include_html: Whether to include HTML content for each tab
    """
    # Check if Chrome is connected
    if not chrome_manager.connected:
        try:
            # Try to connect
            connected = await run_in_executor(
                app.state.thread_pool, chrome_manager.test_connection, True
            )
            if not connected:
                raise HTTPException(
                    status_code=503, detail="Chrome is not connected. Try /chrome/launch first."
                )
        except Exception as e:
            logger.error(f"Error connecting to Chrome: {e}")
            raise HTTPException(status_code=500, detail="Error connecting to Chrome") from e

    # Using ChromeTabs to get tab information
    tabs_manager = ChromeTabs(chrome_manager)

    if include_html:
        try:
            # Get all tabs with HTML content
            tabs_with_html = await run_in_executor(
                app.state.thread_pool, tabs_manager.get_all_tabs_with_html
            )
            return tabs_with_html
        except Exception as e:
            logger.error(f"Error getting tabs with HTML: {e}")
            raise HTTPException(
                status_code=500, detail=f"Error getting tabs with HTML: {str(e)}"
            ) from e
    else:
        try:
            # Get tabs without HTML content (faster)
            tabs = await run_in_executor(app.state.thread_pool, chrome_manager.get_all_tabs)
            # Filter for HTTP/HTTPS tabs
            filtered_tabs = [
                tab for tab in tabs if tab.get("url", "").startswith(("http://", "https://"))
            ]
            return filtered_tabs
        except Exception as e:
            logger.error(f"Error getting tabs: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting tabs: {str(e)}") from e


@app.websocket("/ws/tabs")
async def websocket_tabs(websocket: WebSocket):
    """WebSocket endpoint for real-time tab monitoring"""
    await websocket.accept()
    client_id = id(websocket)  # Use websocket object ID as client ID

    # Create a shared event for signaling the monitoring task to stop
    stop_event = asyncio.Event()

    # Store in active tasks
    _tab_monitoring_tasks[client_id] = {"websocket": websocket, "stop_event": stop_event}

    logger.debug(f"Tab monitoring WebSocket client connected: {client_id}")

    try:
        # Check if Chrome is connected, connect if needed
        if not chrome_manager.connected:
            await websocket.send_json(
                {"type": "status", "status": "connecting", "message": "Connecting to Chrome..."}
            )

            connected = await run_in_executor(
                app.state.thread_pool, chrome_manager.test_connection, True
            )

            if not connected:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Failed to connect to Chrome. Please launch Chrome with debug port.",
                    }
                )
                return

        # Send connected status
        await websocket.send_json(
            {
                "type": "status",
                "status": "connected",
                "message": "Connected to Chrome. Starting tab monitoring...",
            }
        )

        # Create ChromeTabs instance
        tabs_manager = ChromeTabs(chrome_manager)

        # Start monitoring in a separate task
        monitor_task = asyncio.create_task(
            _tab_monitoring_loop(websocket, tabs_manager, stop_event)
        )

        # Keep the websocket open until client disconnects
        while not stop_event.is_set():
            # Process any incoming messages
            try:
                # Use a timeout so we can still check the stop_event periodically
                data = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                # Process commands from client
                if data.get("command") == "refresh":
                    # Force a refresh of tabs
                    await websocket.send_json(
                        {"type": "status", "status": "refreshing", "message": "Refreshing tabs..."}
                    )
            except asyncio.TimeoutError:
                # This is expected due to our timeout, just continue
                pass
            except WebSocketDisconnect:
                logger.debug(f"Tab monitoring WebSocket client disconnected: {client_id}")
                stop_event.set()
                break
            except Exception as e:
                logger.error(f"Error in WebSocket receive loop: {e}")
                # Try to send error to client
                try:
                    await websocket.send_json({"type": "error", "message": str(e)})
                except Exception as e:
                    # If we can't send, client is probably gone
                    logger.debug(f"Could not send error to WebSocket client: {e}")
                    stop_event.set()
                    break

        # Wait for monitoring task to end
        if not monitor_task.done():
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        logger.debug(f"Tab monitoring WebSocket client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"Error in tab monitoring WebSocket: {e}")
    finally:
        # Clean up
        stop_event.set()
        if client_id in _tab_monitoring_tasks:
            del _tab_monitoring_tasks[client_id]
        logger.debug(f"Tab monitoring WebSocket connection closed: {client_id}")


async def _tab_monitoring_loop(
    websocket: WebSocket, tabs_manager: ChromeTabs, stop_event: asyncio.Event
):
    """Loop to monitor tabs and send updates via WebSocket"""
    # First, get initial tabs and send them
    try:
        # Get initial tabs without HTML (faster)
        initial_tabs = await run_in_executor(
            app.state.thread_pool, lambda: tabs_manager.chrome_manager.get_all_tabs()
        )

        # Filter tabs
        filtered_tabs = [
            tab for tab in initial_tabs if tab.get("url", "").startswith(("http://", "https://"))
        ]

        # Send initial tabs
        await websocket.send_json({"type": "tabs", "tabs": filtered_tabs, "event": "initial"})

        # Set up callback for tab changes
        async def tab_change_callback(event):
            if stop_event.is_set():
                return

            # Send update based on event type
            if event.new_tabs:
                await websocket.send_json(
                    {"type": "tabs", "tabs": event.new_tabs, "event": "new_tabs"}
                )

            if event.navigated_tabs:
                await websocket.send_json(
                    {"type": "tabs", "tabs": event.navigated_tabs, "event": "navigation"}
                )

            if event.closed_tabs:
                await websocket.send_json(
                    {"type": "tabs", "tabs": event.closed_tabs, "event": "closed_tabs"}
                )

        # Create an async to sync bridge for callbacks
        def start_monitoring():
            # Use a queue to pass events from sync to async world
            event_queue = asyncio.Queue()

            # Sync callback puts events in queue
            def sync_callback(event):
                asyncio.run_coroutine_threadsafe(event_queue.put(event), asyncio.get_event_loop())

            # Start monitoring in sync world
            success = tabs_manager.start_monitoring(sync_callback)

            # Return the queue and success status
            return event_queue, success

        # Start the monitoring and get the event queue
        event_queue, success = await run_in_executor(app.state.thread_pool, start_monitoring)

        if not success:
            await websocket.send_json(
                {"type": "error", "message": "Failed to start tab monitoring"}
            )
            return

        # Process events from queue until stopped
        while not stop_event.is_set():
            try:
                # Wait for next event with timeout so we can check stop_event
                event = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                # Process the event
                await tab_change_callback(event)
            except asyncio.TimeoutError:
                # Expected due to timeout, just check stop_event
                pass
            except Exception as e:
                logger.error(f"Error processing tab event: {e}")
                # Try to report error to client
                try:
                    await websocket.send_json(
                        {"type": "error", "message": f"Error monitoring tabs: {str(e)}"}
                    )
                except Exception as e:
                    # Can't send, client probably disconnected
                    logger.debug(f"Could not send error to WebSocket client: {e}")
                    break

    except Exception as e:
        logger.error(f"Error in tab monitoring loop: {e}")
        # Try to send error to client
        try:
            await websocket.send_json(
                {"type": "error", "message": f"Error starting tab monitoring: {str(e)}"}
            )
        except Exception as e:
            # Can't send, client probably disconnected
            logger.debug(f"Could not send error to WebSocket client: {e}")
            pass
    finally:
        # Make sure to stop monitoring
        await run_in_executor(app.state.thread_pool, lambda: tabs_manager.stop_monitoring())
