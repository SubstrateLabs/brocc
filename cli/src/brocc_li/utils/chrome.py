import asyncio
import os
import platform
import shutil
import subprocess
from typing import Optional

import aiohttp
import psutil

from brocc_li.utils.logger import logger

REMOTE_DEBUG_PORT = 9222


def find_chrome_path() -> Optional[str]:
    """Find Chrome executable path based on the current platform."""
    system = platform.system().lower()

    # First try using shutil.which to find Chrome in PATH
    if system == "darwin":  # macOS
        candidates = [
            shutil.which("google-chrome"),
            shutil.which("chromium"),
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            os.path.expanduser("~/Applications/Chromium.app/Contents/MacOS/Chromium"),
        ]
    elif system == "linux":
        candidates = [
            shutil.which("google-chrome"),
            shutil.which("google-chrome-stable"),
            shutil.which("chromium"),
            shutil.which("chromium-browser"),
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
            os.path.expanduser("~/.local/bin/google-chrome"),
            os.path.expanduser("~/.local/bin/chromium"),
        ]
    elif system == "windows":
        program_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")
        program_files_x86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
        local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))

        candidates = [
            shutil.which("chrome"),
            os.path.join(program_files, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(program_files_x86, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(local_appdata, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(program_files, "Chromium\\Application\\chrome.exe"),
            os.path.join(program_files_x86, "Chromium\\Application\\chrome.exe"),
        ]
    else:
        candidates = []

    # Return the first path that exists
    for path in candidates:
        if path and os.path.exists(path):
            return path

    return None


async def is_chrome_debug_port_active(port: int = REMOTE_DEBUG_PORT) -> bool:
    """Check if Chrome is running with debug port active by attempting to connect to it."""
    try:
        timeout = aiohttp.ClientTimeout(total=1.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"http://localhost:{port}/json/version") as response:
                return response.status == 200
    except Exception:
        return False


def is_chrome_process_running() -> bool:
    """Check if Chrome application is running using psutil."""
    for proc in psutil.process_iter(["name"]):
        try:
            proc_name = proc.info["name"].lower()
            if proc_name in ["chrome", "chrome.exe", "google chrome", "chromium"]:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


async def is_chrome_process_running_async() -> bool:
    """Async version of is_chrome_process_running."""
    # Since psutil is synchronous, we need to run this in another thread
    return await asyncio.to_thread(is_chrome_process_running)


async def launch_chrome(debug_port: int = REMOTE_DEBUG_PORT, quiet: bool = False) -> bool:
    """
    Launch Chrome with debug port enabled.

    Args:
        debug_port: Port number to use for remote debugging
        quiet: If True, suppresses most log output

    Returns:
        bool: True if Chrome was successfully launched with debug port, False otherwise
    """
    chrome_path = find_chrome_path()

    if not chrome_path:
        if not quiet:
            logger.error("Could not find a valid Chrome/Chromium installation.")
        return False

    if not quiet:
        logger.debug(f"Using Chrome path: {chrome_path}")

    args = [
        chrome_path,
        f"--remote-debugging-port={debug_port}",
        "--remote-allow-origins=*",  # Allow WebSocket connections from any origin
    ]

    try:
        if not quiet:
            logger.debug("Launching Chrome with remote debugging...")

        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        max_wait = 15
        for i in range(max_wait):
            if await is_chrome_debug_port_active(debug_port):
                if not quiet:
                    logger.success("Chrome launched successfully with debug port.")
                return True
            await asyncio.sleep(1)
            if not quiet:
                logger.debug(f"Waiting for Chrome debug port... ({i + 1}/{max_wait})")

        if not quiet:
            logger.error(
                f"Chrome did not become available on port {debug_port} after {max_wait} seconds."
            )
        return False
    except Exception as e:
        if not quiet:
            logger.error(f"Failed to launch Chrome: {str(e)}")
        return False


async def quit_chrome() -> bool:
    """
    Quit all running Chrome/Chromium processes.

    Returns:
        bool: True if successfully quit all Chrome processes or if none were running,
              False if some processes couldn't be terminated
    """
    logger.debug("Attempting to quit existing Chrome/Chromium processes...")
    success = False
    killed_pids = []
    for proc in psutil.process_iter(["name", "pid", "cmdline"]):
        try:
            proc_name = proc.info["name"].lower()
            cmdline = proc.info["cmdline"]
            is_chrome_like = proc_name in [
                "chrome",
                "chrome.exe",
                "google chrome",
                "chromium",
            ]
            is_main_process = (
                not any(arg.startswith("--type=") for arg in cmdline) if cmdline else True
            )

            if is_chrome_like and is_main_process:
                logger.debug(f"Terminating process: PID={proc.info['pid']}, Name={proc_name}")
                proc.terminate()
                killed_pids.append(proc.info["pid"])
                success = True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        except Exception as e:
            logger.warning(f"Error terminating process {proc.info.get('pid', 'N/A')}: {e}")

    if not success:
        logger.warning("No Chrome/Chromium processes found to quit.")
        return True

    # Use asyncio.sleep instead of time.sleep
    await asyncio.sleep(2)

    still_running = []
    for pid in killed_pids:
        if psutil.pid_exists(pid):
            try:
                proc = psutil.Process(pid)
                if proc.status() != psutil.STATUS_ZOMBIE:
                    logger.warning(
                        f"Process {pid} did not terminate gracefully, attempting force kill."
                    )
                    proc.kill()
                    still_running.append(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            except Exception as e:
                logger.error(f"Error force killing process {pid}: {e}")

    if not still_running:
        logger.success("Successfully quit Chrome/Chromium processes.")
        return True
    else:
        logger.error(f"Failed to quit some Chrome processes: {still_running}")
        return False


async def restart_chrome_with_debug_port(
    debug_port: int = REMOTE_DEBUG_PORT, quiet: bool = False
) -> bool:
    """
    Quit any running Chrome instances and launch a new one with debug port.

    Args:
        debug_port: Port number to use for remote debugging
        quiet: If True, suppresses most log output

    Returns:
        bool: True if Chrome was successfully restarted with debug port, False otherwise
    """
    if not await quit_chrome():
        if not quiet:
            logger.error("Failed to quit existing Chrome instances.")
        return False

    # Allow a moment for processes to fully terminate
    await asyncio.sleep(1)

    return await launch_chrome(debug_port, quiet)
