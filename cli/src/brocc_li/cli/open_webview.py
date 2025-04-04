import atexit
import subprocess
import sys
import threading
import time
from pathlib import Path

from brocc_li.cli.webui import WEBUI_HOST, WEBUI_PORT
from brocc_li.utils.logger import logger
from brocc_li.utils.version import get_version

# URL for the WebUI
WEBUI_URL = f"http://{WEBUI_HOST}:{WEBUI_PORT}"

# Simple global flag to prevent multiple windows
_WEBVIEW_ACTIVE = False
_WEBVIEW_PROCESS = None


def is_webview_open():
    """Check if webview is marked as open"""
    global _WEBVIEW_ACTIVE, _WEBVIEW_PROCESS

    # First check our flag
    if _WEBVIEW_ACTIVE:
        # Verify process is still running
        if _WEBVIEW_PROCESS and _WEBVIEW_PROCESS.poll() is None:
            return True
        else:
            # Process has terminated or was closed by user
            logger.info("Webview process detected as terminated")
            _WEBVIEW_ACTIVE = False
            _WEBVIEW_PROCESS = None

    return False


def check_webview_health():
    """Simple health check"""
    return is_webview_open()


def close_webview():
    """Close any open webview processes"""
    global _WEBVIEW_ACTIVE, _WEBVIEW_PROCESS

    if _WEBVIEW_PROCESS:
        try:
            logger.info("Terminating webview process")
            _WEBVIEW_PROCESS.terminate()
            # Give it a moment to terminate gracefully
            time.sleep(0.5)
            if _WEBVIEW_PROCESS.poll() is None:
                logger.info("Webview process still running, killing it")
                _WEBVIEW_PROCESS.kill()
            _WEBVIEW_PROCESS = None
            _WEBVIEW_ACTIVE = False
            return True
        except Exception as e:
            logger.error(f"Error closing webview process: {e}")

    _WEBVIEW_ACTIVE = False
    return False


# Register cleanup function
atexit.register(close_webview)


def create_launcher_script():
    """Create a temporary script to launch webview in a separate process"""
    # Create a temp directory if it doesn't exist
    script_dir = Path(__file__).parent
    launcher_path = script_dir / "webview_launcher.py"

    # We'll rely on the actual webview_launcher.py file that we edited manually
    # Just verify it exists
    if not launcher_path.exists():
        logger.error(f"Webview launcher script not found at: {launcher_path}")
        return None

    logger.info(f"Using existing webview launcher script: {launcher_path}")
    return launcher_path


def open_webview():
    """
    Open a webview in a separate process so it can run on a main thread
    """
    global _WEBVIEW_ACTIVE, _WEBVIEW_PROCESS

    # Don't open if already active
    if is_webview_open():
        logger.info("Webview is already open, not launching a new one")
        return True

    try:
        # Create the launcher script
        launcher_path = create_launcher_script()
        if not launcher_path:
            logger.error("Failed to get launcher script path")
            return False

        # Get the current Python executable
        python_exe = sys.executable

        # Create the command
        cmd = [python_exe, str(launcher_path), WEBUI_URL, f"🥦 Brocc v{get_version()}"]

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

        # Start a thread to monitor the process
        def monitor_process():
            global _WEBVIEW_ACTIVE
            proc = _WEBVIEW_PROCESS  # Local reference
            if not proc:
                return

            logger.info(f"Monitoring webview process PID: {proc.pid}")

            # Read any output
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

        # Start the monitor thread
        monitor_thread = threading.Thread(
            target=monitor_process, daemon=True, name="webview-monitor"
        )
        monitor_thread.start()

        # Give it a moment to start
        time.sleep(0.5)

        # If process is still running, assume success
        if _WEBVIEW_PROCESS and _WEBVIEW_PROCESS.poll() is None:
            logger.info("Webview process started successfully")
            return True
        else:
            logger.error("Webview process failed to start")
            _WEBVIEW_ACTIVE = False
            _WEBVIEW_PROCESS = None
            return False

    except Exception as e:
        logger.error(f"Failed to launch webview: {e}")
        _WEBVIEW_ACTIVE = False
        _WEBVIEW_PROCESS = None
        return False


# For compatibility with existing code
def launch_webview_in_thread(*args, **kwargs):
    """Wrapper around open_webview_direct"""
    return open_webview()


if __name__ == "__main__":
    # Example of direct usage
    open_webview()
