import subprocess
import sys
import threading
import time
from pathlib import Path

import requests

from brocc_li.utils.logger import logger

# Global variable to track the systray process
_SYSTRAY_PROCESS = None


def launch_systray(
    webapp_host="127.0.0.1",
    webapp_port=8023,
    api_host="127.0.0.1",
    api_port=8022,
    version="0.0.1",
):
    """
    Launch the system tray icon in a separate process.

    Args:
        webapp_host: Host for the App
        webapp_port: Port for the App
        api_host: Host for the API server
        api_port: Port for the API server
        version: App version

    Returns:
        Tuple of (success, None) - exit_file parameter is kept for backwards compatibility
    """
    global _SYSTRAY_PROCESS

    # If already running, do nothing
    if _SYSTRAY_PROCESS and _SYSTRAY_PROCESS.poll() is None:
        logger.info("Systray process already running")
        return True, None

    try:
        # Get the path to the systray_process.py script
        script_dir = Path(__file__).parent
        systray_script = script_dir / "systray_process.py"

        if not systray_script.exists():
            logger.error(f"Systray script not found: {systray_script}")
            return False, None

        # Import sys to get the Python executable
        python_exe = sys.executable

        # Build the command
        cmd = [
            python_exe,
            str(systray_script),
            "--host",
            webapp_host,
            "--port",
            str(webapp_port),
            "--api-host",
            api_host,
            "--api-port",
            str(api_port),
            "--version",
            version,
        ]

        # Start the process
        logger.info(f"Starting systray process: {' '.join(cmd)}")
        _SYSTRAY_PROCESS = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
        )

        # Start a thread to monitor the process output
        def monitor_systray():
            proc = _SYSTRAY_PROCESS  # Local reference

            if not proc:
                return

            logger.info(f"Monitoring systray process (PID: {proc.pid})")

            while proc and proc.poll() is None:
                try:
                    if proc.stdout:
                        line = proc.stdout.readline().strip()
                        if line:
                            logger.info(f"Systray: {line}")
                except (IOError, BrokenPipeError) as e:
                    logger.debug(f"Error reading from systray stdout: {e}")
                    break

            # Process has exited
            exit_code = proc.returncode if proc else "unknown"
            logger.info(f"Systray process exited with code: {exit_code}")

            # Check for errors
            if proc and proc.stderr:
                try:
                    error = proc.stderr.read()
                    if error:
                        logger.error(f"Systray process error: {error}")
                except (IOError, BrokenPipeError) as e:
                    logger.debug(f"Error reading from systray stderr: {e}")

        # Start monitor thread
        threading.Thread(target=monitor_systray, daemon=True).start()

        # Wait a moment for process to start
        time.sleep(0.5)

        # Check if process started successfully
        if _SYSTRAY_PROCESS.poll() is not None:
            logger.error(
                f"Systray process failed to start (exit code: {_SYSTRAY_PROCESS.returncode})"
            )
            return False, None

        logger.info(f"Systray process started successfully (PID: {_SYSTRAY_PROCESS.pid})")
        return True, None

    except Exception as e:
        logger.error(f"Failed to launch systray process: {e}")
        return False, None


def terminate_systray():
    """
    Terminate the systray process using WebSocket communication.

    Returns:
        bool: True if successfully terminated or already not running, False on error
    """
    global _SYSTRAY_PROCESS

    # If not running, nothing to do
    if not _SYSTRAY_PROCESS or _SYSTRAY_PROCESS.poll() is not None:
        logger.info("No systray process to terminate")
        return True

    try:
        # First try to gracefully shutdown via API
        api_url = "http://127.0.0.1:8022"  # Hard-coded for simplicity

        logger.info("Sending shutdown message to systray via API")
        try:
            response = requests.post(f"{api_url}/systray/shutdown", timeout=1)
            if response.status_code == 200:
                logger.info("Successfully sent shutdown signal to systray")

                # Wait briefly for process to terminate
                for _ in range(5):  # Wait up to 500ms
                    if _SYSTRAY_PROCESS.poll() is not None:
                        logger.info("Systray process terminated gracefully")
                        return True
                    time.sleep(0.1)
            else:
                logger.warning(f"Failed to send shutdown signal via API: {response.status_code}")
        except requests.RequestException as e:
            logger.warning(f"Error sending shutdown via API: {e}")

        # If still running, terminate directly
        if _SYSTRAY_PROCESS.poll() is None:
            logger.info(f"Terminating systray process (PID: {_SYSTRAY_PROCESS.pid})")
            _SYSTRAY_PROCESS.terminate()

            # Wait for process to terminate
            try:
                _SYSTRAY_PROCESS.wait(timeout=1.0)
                logger.info("Systray process terminated")
            except subprocess.TimeoutExpired:
                logger.warning("Systray process did not terminate gracefully, killing")
                _SYSTRAY_PROCESS.kill()
                _SYSTRAY_PROCESS.wait(timeout=1.0)

        return True

    except Exception as e:
        logger.error(f"Error terminating systray process: {e}")
        return False


def is_systray_running():
    """Check if the systray process is running

    Returns:
        bool: True if the process is running
    """
    global _SYSTRAY_PROCESS
    return _SYSTRAY_PROCESS is not None and _SYSTRAY_PROCESS.poll() is None
