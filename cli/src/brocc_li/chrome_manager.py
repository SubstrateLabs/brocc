from playwright.sync_api import Browser, Page, Playwright
from rich.prompt import Confirm
from typing import Optional, NamedTuple, Callable
import subprocess
import time
import requests
import platform
import os
import psutil
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

    def __init__(self):
        self._state: ChromeState = self._get_chrome_state()
        logger.debug(f"Initial Chrome state: {self.status_description}")

    def _get_chrome_paths(self) -> list[str]:
        """Get Chrome executable paths based on the current platform."""
        system = platform.system().lower()

        if system == "darwin":  # macOS
            return [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
                os.path.expanduser(
                    "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
                ),
                os.path.expanduser(
                    "~/Applications/Chromium.app/Contents/MacOS/Chromium"
                ),
            ]
        elif system == "linux":
            return [
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium-browser-stable",
                os.path.expanduser("~/.local/bin/google-chrome"),
                os.path.expanduser("~/.local/bin/chromium"),
            ]
        elif system == "windows":
            program_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")
            program_files_x86 = os.environ.get(
                "PROGRAMFILES(X86)", "C:\\Program Files (x86)"
            )
            local_appdata = os.environ.get(
                "LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")
            )

            return [
                os.path.join(program_files, "Google\\Chrome\\Application\\chrome.exe"),
                os.path.join(
                    program_files_x86, "Google\\Chrome\\Application\\chrome.exe"
                ),
                os.path.join(local_appdata, "Google\\Chrome\\Application\\chrome.exe"),
                os.path.join(program_files, "Chromium\\Application\\chrome.exe"),
                os.path.join(program_files_x86, "Chromium\\Application\\chrome.exe"),
            ]
        return []

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
        chrome_paths = self._get_chrome_paths()

        chrome_path = None
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_path = path
                break

        if not chrome_path:
            logger.error("Could not find a valid Chrome/Chromium installation.")
            return False

        logger.info(f"Using Chrome path: {chrome_path}")
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
            logger.info("Launching Chrome with remote debugging...")
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

            logger.error(
                f"Chrome did not become available on port 9222 after {max_wait} seconds."
            )
            return False
        except Exception as e:
            logger.error(f"Failed to launch Chrome: {str(e)}")
            return False

    def _quit_chrome(self) -> bool:
        """Quit all running Chrome/Chromium processes."""
        logger.info("Attempting to quit existing Chrome/Chromium processes...")
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
                    not any(arg.startswith("--type=") for arg in cmdline)
                    if cmdline
                    else True
                )

                if is_chrome_like and is_main_process:
                    logger.debug(
                        f"Terminating process: PID={proc.info['pid']}, Name={proc_name}"
                    )
                    proc.terminate()
                    killed_pids.append(proc.info["pid"])
                    success = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception as e:
                logger.warning(
                    f"Error terminating process {proc.info.get('pid', 'N/A')}: {e}"
                )

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

    def _connect_to_chrome(self, playwright: Playwright) -> Optional[Browser]:
        """Connect to Chrome using Playwright via debug port."""
        try:
            browser = playwright.chromium.connect_over_cdp(
                endpoint_url="http://localhost:9222",
                timeout=10000,
            )
            browser_version = browser.version
            logger.success(
                f"Successfully connected to Chrome {browser_version} via debug port"
            )
            return browser
        except Exception as e:
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

    def connect(
        self,
        playwright: Playwright,
        confirm_fn: Optional[Callable[[str, bool], bool]] = None,
        auto_confirm: bool = False,
    ) -> Optional[Browser]:
        """
        Ensures Chrome is running with the debug port and connects to it.

        Handles launching or relaunching Chrome as needed, using the provided
        confirmation function or auto-confirming if specified.

        Args:
            playwright: The Playwright instance.
            confirm_fn: Custom confirmation function that takes a message and default value
                       and returns a boolean. If None, uses the default Rich confirm.
            auto_confirm: If True, bypass all confirmation prompts and proceed automatically.

        Returns:
            A Playwright Browser instance if connection is successful, otherwise None.
        """
        # Use the provided confirm function or the default
        confirm = (
            lambda msg, default=True: True
            if auto_confirm
            else (
                confirm_fn(msg, default)
                if confirm_fn
                else default_confirm(msg, default)
            )
        )

        self._state = self._get_chrome_state()

        if self._state.has_debug_port:
            logger.info(
                "Chrome already running with debug port. Attempting to connect..."
            )
            browser = self._connect_to_chrome(playwright)
            if browser:
                return browser
            else:
                logger.warning(
                    "Connection failed despite active debug port. Attempting relaunch."
                )
                if not confirm(
                    "Connection failed. Quit existing Chrome and relaunch?", True
                ):
                    logger.error("Connection aborted by user.")
                    return None
                if not self._quit_chrome():
                    logger.error(
                        "Failed to quit existing Chrome instance(s). Cannot proceed."
                    )
                    return None
                # Fall through to launch logic

        elif self._state.is_running:
            logger.warning("Chrome is running without the debug port.")
            if not confirm("Quit existing Chrome and relaunch with debug port?", True):
                logger.error("Relaunch aborted by user.")
                return None
            if not self._quit_chrome():
                logger.error(
                    "Failed to quit existing Chrome instance(s). Cannot proceed."
                )
                return None
            # Fall through to launch logic

        else:
            logger.info("Chrome is not running.")
            if not confirm("Launch Chrome with debug port?", True):
                logger.error("Launch aborted by user.")
                return None
            # Fall through to launch logic

        # Launch logic (reached if not running, or after quitting)
        if self._launch_chrome():
            time.sleep(2)
            logger.info("Attempting to connect to newly launched Chrome...")
            browser = self._connect_to_chrome(playwright)
            if browser:
                return browser
            else:
                logger.error("Failed to connect even after launching Chrome.")
                return None
        else:
            logger.error("Failed to launch Chrome. Cannot connect.")
            return None

    def open_new_tab(self, browser: Browser, url: str) -> Optional[Page]:
        """Open a new tab with the given URL in the managed browser instance."""
        if not browser or not browser.is_connected():
            logger.error("Browser is not connected. Cannot open new tab.")
            return None
        try:
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()
            logger.info(f"Opening URL: {url}")
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            logger.success(f"Successfully opened {url}")
            return page
        except Exception as e:
            logger.error(f"Failed to open URL {url}: {str(e)}")
            try:
                if "page" in locals() and not page.is_closed():
                    page.close()
            except Exception as close_err:
                logger.warning(
                    f"Error closing page after failed navigation: {close_err}"
                )
            return None


# Example of using a custom confirm function with a GUI
def gui_confirm(message: str, default: bool = True) -> bool:
    """Example of a GUI confirmation function."""
    # This would be replaced with actual GUI code, e.g., using PyQt, Tkinter, etc.
    # For demonstration, we'll just print and return True
    print(f"CONFIRM: {message} [Y/n]: ")
    return True  # Always confirm in this example


def main() -> None:
    from playwright.sync_api import sync_playwright

    manager = ChromeManager()
    logger.info(f"Current status: {manager.status_description}")

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
                logger.info(f"Opened page with title: {page.title()}")
                time.sleep(3)
                page.close()
            else:
                logger.error("Failed to open example.com")
        else:
            logger.error("Failed to connect to Chrome.")


if __name__ == "__main__":
    main()
