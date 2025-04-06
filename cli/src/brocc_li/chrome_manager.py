import os
import platform
import shutil
import subprocess
import time
from collections.abc import Callable
from typing import NamedTuple, Optional

import psutil
import requests
from playwright.sync_api import Browser, Page, Playwright
from rich.prompt import Confirm

from brocc_li.utils.logger import logger


class ChromeState(NamedTuple):
    is_running: bool
    has_debug_port: bool


# Default confirmation function that uses Rich
def default_confirm(message: str, default: bool = True) -> bool:
    """Default confirmation function using Rich."""
    return Confirm.ask(message, default=default)


class ChromeManager:
    """Manages the connection to a Chrome instance with remote debugging."""

    def __init__(self, auto_connect: bool = False):
        """
        Initialize the Chrome Manager.

        Args:
            auto_connect: If True, will automatically try to connect to Chrome
                         if a debug port is detected.
        """
        self._state: ChromeState = self._get_chrome_state()
        self._browser: Optional[Browser] = None
        self._auto_connect = auto_connect

        # Only log detailed status when used directly, not during import
        if auto_connect and self._state.has_debug_port:
            # Attempt auto-connect without detailed logging during import
            # We'll just log the final result if successful
            self._try_auto_connect(quiet=True)

    def _try_auto_connect(self, quiet: bool = False) -> bool:
        """
        Attempt to automatically connect to Chrome with debug port.

        Args:
            quiet: If True, suppress most log output during connection

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            from playwright.sync_api import sync_playwright

            # Create a new playwright instance
            with sync_playwright() as playwright:
                # Try to connect
                browser = self._connect_to_chrome(playwright, quiet=quiet)
                if browser:
                    self._browser = browser
                    if not quiet:
                        logger.debug(f"Auto-connected to Chrome {browser.version}")
                    return True
                else:
                    if not quiet:
                        logger.warning("Auto-connect: Failed to connect despite active debug port")
        except Exception as e:
            if not quiet:
                logger.error(f"Auto-connect error: {e}")

        return False

    def _find_chrome_path(self) -> Optional[str]:
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

    def _is_chrome_process_running(self) -> bool:
        """Check if Chrome application is running using psutil."""
        for proc in psutil.process_iter(["name"]):
            try:
                proc_name = proc.info["name"].lower()
                if proc_name in ["chrome", "chrome.exe", "google chrome", "chromium"]:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def _is_chrome_debug_port_active(self) -> bool:
        """Check if Chrome is running by attempting to connect to its debug port."""
        try:
            response = requests.get("http://localhost:9222/json/version", timeout=1)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def _get_chrome_state(self) -> ChromeState:
        """Get the current state of Chrome (running and debug port status)."""
        has_debug_port = self._is_chrome_debug_port_active()
        is_running = has_debug_port or self._is_chrome_process_running()
        return ChromeState(
            is_running=is_running,
            has_debug_port=has_debug_port,
        )

    def _launch_chrome(self) -> bool:
        """Launch Chrome with debug port enabled."""
        chrome_path = self._find_chrome_path()

        if not chrome_path:
            logger.error("Could not find a valid Chrome/Chromium installation.")
            return False

        logger.debug(f"Using Chrome path: {chrome_path}")
        args = [
            chrome_path,
            "--remote-debugging-port=9222",
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--disable-background-timer-throttling",
            "--disable-popup-blocking",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--no-first-run",
            "--no-default-browser-check",
        ]

        try:
            logger.debug("Launching Chrome with remote debugging...")
            subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            max_wait = 15
            for i in range(max_wait):
                if self._is_chrome_debug_port_active():
                    logger.success("Chrome launched successfully with debug port.")
                    return True
                time.sleep(1)
                logger.debug(f"Waiting for Chrome debug port... ({i + 1}/{max_wait})")

            logger.error(f"Chrome did not become available on port 9222 after {max_wait} seconds.")
            return False
        except Exception as e:
            logger.error(f"Failed to launch Chrome: {str(e)}")
            return False

    def _quit_chrome(self) -> bool:
        """Quit all running Chrome/Chromium processes."""
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

        time.sleep(2)
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

    def _connect_to_chrome(self, playwright: Playwright, quiet: bool = False) -> Browser | None:
        """Connect to Chrome using Playwright via debug port."""
        try:
            browser = playwright.chromium.connect_over_cdp(
                endpoint_url="http://localhost:9222",
                timeout=10000,
            )
            browser_version = browser.version
            if not quiet:
                logger.success(f"Successfully connected to Chrome {browser_version} via debug port")
            return browser
        except Exception as e:
            if not quiet:
                logger.error(f"Playwright failed to connect to Chrome debug port: {str(e)}")
            return None

    @property
    def status_description(self) -> str:
        """Returns a human-readable description of the Chrome state."""
        self._state = self._get_chrome_state()
        if self._state.has_debug_port:
            return "Chrome is running and connected via debug port."
        elif self._state.is_running:
            return "Chrome is running, but the debug port is not active. Relaunch required."
        else:
            return "Chrome is not running. Launch required."

    @property
    def connected_browser(self) -> Browser | None:
        """Return the currently connected browser if available."""
        return self._browser

    def refresh_state(self) -> ChromeState:
        """Refresh and return the current Chrome state."""
        self._state = self._get_chrome_state()
        # Try to auto-connect if configured and debug port is active
        if self._auto_connect and self._state.has_debug_port and self._browser is None:
            self._try_auto_connect()
        return self._state

    def connect(
        self,
        playwright: Playwright,
        confirm_fn: Callable[[str, bool], bool] | None = None,
        auto_confirm: bool = False,
        quiet: bool = False,
    ) -> Browser | None:
        """
        Ensures Chrome is running with the debug port and connects to it.

        Handles launching or relaunching Chrome as needed, using the provided
        confirmation function or auto-confirming if specified.

        Args:
            playwright: The Playwright instance.
            confirm_fn: Custom confirmation function that takes a message and default value
                       and returns a boolean. If None, uses the default Rich confirm.
            auto_confirm: If True, bypass all confirmation prompts and proceed automatically.
            quiet: If True, suppress most logging output.

        Returns:
            A Playwright Browser instance if connection is successful, otherwise None.
        """

        # Use the provided confirm function or the default
        def make_confirm_function():
            def confirm_wrapper(msg, default=True):
                if auto_confirm:
                    return True
                else:
                    return confirm_fn(msg, default) if confirm_fn else default_confirm(msg, default)

            return confirm_wrapper

        confirm = make_confirm_function()

        self._state = self._get_chrome_state()

        # Check if we already have a connected browser
        if self._browser and self._browser.is_connected():
            if not quiet:
                logger.debug("Already connected to Chrome browser")
            return self._browser

        if self._state.has_debug_port:
            if not quiet:
                logger.debug("Chrome already running with debug port. Attempting to connect...")
            browser = self._connect_to_chrome(playwright, quiet=quiet)
            if browser:
                self._browser = browser
                return browser
            else:
                if not quiet:
                    logger.warning(
                        "Connection failed despite active debug port. Attempting relaunch."
                    )
                if not confirm("Connection failed. Quit existing Chrome and relaunch?", True):
                    if not quiet:
                        logger.error("Connection aborted by user.")
                    return None
                if not self._quit_chrome():
                    if not quiet:
                        logger.error("Failed to quit existing Chrome instance(s). Cannot proceed.")
                    return None
                # Fall through to launch logic

        elif self._state.is_running:
            if not quiet:
                logger.warning("Chrome is running without the debug port.")
            if not confirm("Quit existing Chrome and relaunch with debug port?", True):
                if not quiet:
                    logger.error("Relaunch aborted by user.")
                return None
            if not self._quit_chrome():
                if not quiet:
                    logger.error("Failed to quit existing Chrome instance(s). Cannot proceed.")
                return None
            # Fall through to launch logic

        else:
            if not quiet:
                logger.debug("Chrome is not running.")
            if not confirm("Launch Chrome with debug port?", True):
                if not quiet:
                    logger.error("Launch aborted by user.")
                return None
            # Fall through to launch logic

        # Launch logic (reached if not running, or after quitting)
        if self._launch_chrome():
            time.sleep(2)
            if not quiet:
                logger.debug("Attempting to connect to newly launched Chrome...")
            browser = self._connect_to_chrome(playwright, quiet=quiet)
            if browser:
                self._browser = browser
                return browser
            else:
                if not quiet:
                    logger.error("Failed to connect even after launching Chrome.")
                return None
        else:
            if not quiet:
                logger.error("Failed to launch Chrome. Cannot connect.")
            return None

    def open_new_tab(self, browser: Browser | None = None, url: str = "") -> Page | None:
        """
        Open a new tab with the given URL.

        If browser is not provided, will use the internal browser instance if available.
        """
        # Use provided browser or the internal one if available
        browser_to_use = browser or self._browser

        if not browser_to_use or not browser_to_use.is_connected():
            logger.error("Browser is not connected. Cannot open new tab.")
            return None
        try:
            context = (
                browser_to_use.contexts[0]
                if browser_to_use.contexts
                else browser_to_use.new_context()
            )
            page = context.new_page()
            if url:
                logger.debug(f"Opening URL: {url}")
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                logger.success(f"Successfully opened {url}")
            return page
        except Exception as e:
            logger.error(f"Failed to open URL {url}: {str(e)}")
            try:
                if "page" in locals() and not page.is_closed():
                    page.close()
            except Exception as close_err:
                logger.warning(f"Error closing page after failed navigation: {close_err}")
            return None

    def disconnect(self) -> bool:
        """
        Disconnect from Chrome browser if connected.

        Returns:
            bool: True if disconnected or already not connected, False if error occurs.
        """
        if not self._browser:
            logger.debug("No active browser connection to disconnect")
            return True

        try:
            self._browser.close()
            self._browser = None
            logger.debug("Successfully disconnected from Chrome")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from Chrome: {str(e)}")
            return False


# Example of using a custom confirm function with a GUI
def gui_confirm(message: str, default: bool = True) -> bool:
    """Example of a GUI confirmation function."""
    # This would be replaced with actual GUI code, e.g., using PyQt, Tkinter, etc.
    logger.debug(f"CONFIRM: {message} [Y/n]: ")
    return True  # Always confirm in this example


def main() -> None:
    from playwright.sync_api import sync_playwright

    manager = ChromeManager(auto_connect=True)
    logger.debug(f"Current status: {manager.status_description}")

    # Example of different confirmation approaches:
    with sync_playwright() as p:
        # 1. Using default Rich confirmation
        # browser = manager.connect(p)

        # 2. Using auto-confirm (no prompts)
        # browser = manager.connect(p, auto_confirm=True)

        # 3. Using custom confirmation function
        browser = manager.connect(p, confirm_fn=gui_confirm)

        if browser:
            page = manager.open_new_tab(browser, "https://example.com")
            if page:
                logger.debug(f"Opened page with title: {page.title()}")
                time.sleep(3)
                page.close()
            else:
                logger.error("Failed to open example.com")
        else:
            logger.error("Failed to connect to Chrome.")


if __name__ == "__main__":
    main()
