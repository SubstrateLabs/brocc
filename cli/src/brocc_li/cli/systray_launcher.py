import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from brocc_li.utils.logger import logger

# Global reference to the systray process
_SYSTRAY_PROCESS = None
_EXIT_FILE = None


def launch_systray(webapp_host, webapp_port, api_host, api_port, version):
    """Start the system tray icon in a separate process

    Args:
        webapp_host: Host address for the webapp
        webapp_port: Port for the webapp
        api_host: Host address for the API
        api_port: Port for the API
        version: App version string

    Returns:
        tuple: (bool success, str exit_file_path)
    """
    global _SYSTRAY_PROCESS, _EXIT_FILE

    try:
        # Create a temp file to monitor for exit
        fd, _EXIT_FILE = tempfile.mkstemp(prefix="brocc_exit_")
        os.close(fd)  # We just need the path

        script_dir = Path(__file__).parent
        launcher_path = script_dir / "systray_process.py"
        if not launcher_path.exists():
            logger.error(f"Systray script not found at: {launcher_path}")
            return False, None

        # Get the current Python executable
        python_exe = sys.executable

        # Create the command
        cmd = [
            python_exe,
            str(launcher_path),
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
            "--exit-file",
            _EXIT_FILE,
        ]

        logger.info(f"Launching systray process: {' '.join(cmd)}")

        # Launch the process
        _SYSTRAY_PROCESS = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
        )

        # Start a thread to monitor systray process
        def monitor_systray():
            proc = _SYSTRAY_PROCESS  # Local reference
            if not proc:
                return

            logger.info(f"Monitoring systray process PID: {proc.pid}")

            # Read output
            while proc and proc.poll() is None:
                try:
                    if proc.stdout:
                        line = proc.stdout.readline().strip()
                        if line:
                            logger.info(f"Systray process: {line}")
                except (IOError, BrokenPipeError) as e:
                    logger.debug(f"Error reading from systray stdout: {e}")
                    break

            # Process has exited
            exit_code = proc.returncode if proc and proc.returncode is not None else "unknown"
            logger.info(f"Systray process exited with code: {exit_code}")

            # Check for errors
            if proc and proc.stderr:
                try:
                    error = proc.stderr.read()
                    if error:
                        logger.error(f"Systray process error: {error}")
                except (IOError, BrokenPipeError) as e:
                    logger.debug(f"Error reading from systray stderr: {e}")

        # Start the monitor thread
        threading.Thread(target=monitor_systray, daemon=True, name="systray-monitor").start()

        # Wait a moment to verify process started
        time.sleep(0.5)

        if _SYSTRAY_PROCESS and _SYSTRAY_PROCESS.poll() is None:
            logger.info("Systray process started successfully")
            return True, _EXIT_FILE
        else:
            logger.error("Systray process failed to start")
            return False, None

    except Exception as e:
        logger.error(f"Failed to launch systray: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False, None


def terminate_systray():
    """Close the systray process if it's running

    Returns:
        bool: True if successfully terminated
    """
    global _SYSTRAY_PROCESS, _EXIT_FILE

    if _SYSTRAY_PROCESS:
        try:
            logger.info("Terminating systray process")
            _SYSTRAY_PROCESS.terminate()
            # Give it a moment to terminate gracefully
            time.sleep(0.5)
            if _SYSTRAY_PROCESS.poll() is None:
                logger.info("Systray process still running, killing it")
                _SYSTRAY_PROCESS.kill()
            _SYSTRAY_PROCESS = None
            return True
        except Exception as e:
            logger.error(f"Error closing systray process: {e}")

    # Remove the exit file if it exists
    if _EXIT_FILE and Path(_EXIT_FILE).exists():
        try:
            Path(_EXIT_FILE).unlink()
        except Exception as e:
            logger.debug(f"Error removing exit file: {e}")

    return False


def is_systray_running():
    """Check if the systray process is running

    Returns:
        bool: True if the process is running
    """
    global _SYSTRAY_PROCESS
    return _SYSTRAY_PROCESS is not None and _SYSTRAY_PROCESS.poll() is None
