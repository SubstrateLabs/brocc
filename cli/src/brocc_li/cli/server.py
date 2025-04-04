import subprocess
import sys
import threading
from pathlib import Path
import psutil
import platform

import uvicorn
from fastapi import BackgroundTasks, FastAPI

from brocc_li.utils.logger import logger
from brocc_li.utils.version import get_version

# --- Constants ---
API_HOST = "127.0.0.1"
API_PORT = 8022

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


# --- Webview Management ---
_WEBVIEW_ACTIVE = False
_WEBVIEW_PROCESS = None


@app.post("/webview/launch")
async def launch_webview(
    background_tasks: BackgroundTasks, webui_url: str = "http://127.0.0.1:8023", title: str = ""
):
    """Launch a webview window pointing to the WebUI"""
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
        _launch_webview_process, webui_url, title if title else f"🥦 Brocc v{get_version()}"
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
            logger.info(f"Focused macOS webview window for PID {_WEBVIEW_PROCESS.pid}")
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
                logger.info(f"Focused Windows webview window for PID {_WEBVIEW_PROCESS.pid}")
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
                logger.info(f"Focused Linux webview window for PID {_WEBVIEW_PROCESS.pid}")
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


def _launch_webview_process(webui_url, title):
    """Launch the webview process and monitor it"""
    global _WEBVIEW_ACTIVE, _WEBVIEW_PROCESS

    try:
        # Get the launcher script path
        script_dir = Path(__file__).parent
        launcher_path = script_dir / "webview_launcher.py"

        if not launcher_path.exists():
            logger.error(f"Webview launcher script not found at: {launcher_path}")
            return

        # Get the current Python executable
        python_exe = sys.executable

        # Create the command
        cmd = [python_exe, str(launcher_path), webui_url, title]

        logger.info(f"Launching webview process with command: {' '.join(cmd)}")

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

            logger.info(f"Monitoring webview process PID: {proc.pid}")

            # Read output
            while proc and proc.poll() is None:
                try:
                    if proc.stdout:
                        line = proc.stdout.readline().strip()
                        if line:
                            logger.info(f"Webview process: {line}")
                except (IOError, BrokenPipeError) as e:
                    logger.debug(f"Error reading from webview stdout: {e}")
                    break

            # Process has exited
            exit_code = proc.returncode if proc and proc.returncode is not None else "unknown"
            logger.info(f"Webview process exited with code: {exit_code}")

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
def start_server(host=API_HOST, port=API_PORT):
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


def run_server_in_thread(host=API_HOST, port=API_PORT):
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
