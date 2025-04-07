import atexit
import os
import subprocess
import sys
import time
from pathlib import Path

from brocc_li.utils.logger import logger

# Global vars
_SYSTRAY_PROCESS = None


def launch_systray(
    webapp_host="127.0.0.1",
    webapp_port=8023,
    api_host="127.0.0.1",
    api_port=8022,
    version="0.0.0",
):
    """
    Launch the system tray icon in a separate process.
    Returns success (bool): True if the systray process was launched successfully.
    """
    global _SYSTRAY_PROCESS

    # Make sure Python executable is available
    python_exe = sys.executable
    if not python_exe:
        logger.error("Could not determine Python executable")
        return False

    # Get the script path
    script_dir = Path(__file__).parent
    systray_script = script_dir / "systray_process.py"

    if not systray_script.exists():
        logger.error(f"Systray script not found at: {systray_script}")
        return False

    # Get current process ID
    current_pid = os.getpid()

    try:
        # Build command
        cmd = [
            python_exe,
            str(systray_script),
            "--host",
            str(webapp_host),
            "--port",
            str(webapp_port),
            "--api-host",
            str(api_host),
            "--api-port",
            str(api_port),
            "--version",
            str(version),
            "--parent-pid",
            str(current_pid),  # Pass parent PID for monitoring
        ]

        logger.debug(f"Launching systray with command: {cmd}")

        # Launch the process
        _SYSTRAY_PROCESS = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
        )

        logger.debug(f"Systray process launched with PID: {_SYSTRAY_PROCESS.pid}")

        # Give it a moment to start
        time.sleep(0.2)

        # Check if process is still running
        if _SYSTRAY_PROCESS.poll() is not None:
            # Process exited immediately - check for errors
            errors = _SYSTRAY_PROCESS.stderr.read() if _SYSTRAY_PROCESS.stderr else "Unknown error"
            logger.error(f"Systray process failed to start: {errors}")
            return False

        # Register cleanup on program exit
        atexit.register(terminate_systray)

        return True

    except Exception as e:
        logger.error(f"Error launching systray: {e}")
        return False


def terminate_systray():
    """
    Terminate the systray process if it's running.
    Returns True if successfully terminated, False otherwise.
    """
    global _SYSTRAY_PROCESS

    if not _SYSTRAY_PROCESS:
        logger.debug("No systray process to terminate")
        return False

    try:
        if _SYSTRAY_PROCESS.poll() is None:
            logger.debug(f"Terminating systray process: {_SYSTRAY_PROCESS.pid}")
            _SYSTRAY_PROCESS.terminate()

            # Wait briefly for termination
            try:
                _SYSTRAY_PROCESS.wait(1.0)
            except subprocess.TimeoutExpired:
                logger.warning("Systray did not terminate gracefully, forcing kill")
                _SYSTRAY_PROCESS.kill()

        # Process has terminated
        logger.debug("Systray process terminated")
        _SYSTRAY_PROCESS = None
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
