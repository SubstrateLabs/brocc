from playwright.sync_api import Browser, Page
from rich.console import Console
from rich.prompt import Confirm
from typing import Optional, NamedTuple
import subprocess
import time
import requests
import platform
import os
import psutil

console = Console()


class ChromeState(NamedTuple):
    is_running: bool
    has_debug_port: bool


def get_chrome_paths() -> list[str]:
    """Get Chrome executable paths based on the current platform."""
    system = platform.system().lower()

    if system == "darwin":  # macOS
        return [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            os.path.expanduser(
                "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            ),
            os.path.expanduser("~/Applications/Chromium.app/Contents/MacOS/Chromium"),
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
            os.path.join(program_files_x86, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(local_appdata, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(program_files, "Chromium\\Application\\chrome.exe"),
            os.path.join(program_files_x86, "Chromium\\Application\\chrome.exe"),
        ]
    return []


def is_chrome_process_running() -> bool:
    """Check if Chrome application is running using psutil."""
    for proc in psutil.process_iter(["name"]):
        try:
            if "chrome" in proc.info["name"].lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def is_chrome_debug_port_active() -> bool:
    """Check if Chrome is running by attempting to connect to its debug port."""
    try:
        response = requests.get("http://localhost:9222/json/version", timeout=2)
        return response.status_code == 200
    except:
        return False


def get_chrome_state() -> ChromeState:
    """Get the current state of Chrome (running and debug port status)."""
    return ChromeState(
        is_running=is_chrome_process_running(),
        has_debug_port=is_chrome_debug_port_active(),
    )


def launch_chrome() -> bool:
    """Launch Chrome with debug port enabled."""
    chrome_paths = get_chrome_paths()

    chrome_path = None
    for path in chrome_paths:
        try:
            if os.path.exists(path):
                subprocess.run([path, "--version"], capture_output=True, check=True)
                chrome_path = path
                break
        except:
            continue

    if not chrome_path:
        console.print("[red]Could not find Chrome installation[/red]")
        return False

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
        "--disable-window-activation",
        "--disable-focus-on-load",
        "--no-first-run",
        "--no-default-browser-check",
        "--no-startup-window",
        "--window-position=0,0",
        # disable_security
        # '--disable-web-security',
        # '--disable-site-isolation-trials',
        # '--disable-features=IsolateOrigins,site-per-process',
    ]

    try:
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for Chrome to start
        for _ in range(10):
            if is_chrome_debug_port_active():
                return True
            time.sleep(1)

        return False
    except Exception as e:
        console.print(f"[red]Failed to launch Chrome: {str(e)}[/red]")
        return False


def quit_chrome() -> bool:
    """Quit all running Chrome processes."""
    success = False
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            if "chrome" in proc.info["name"].lower():
                proc.terminate()
                success = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return success


def connect_to_chrome(playwright) -> Optional[Browser]:
    """Connect to Chrome using Playwright via debug port."""
    try:
        browser = playwright.chromium.connect_over_cdp(
            endpoint_url="http://localhost:9222",
            timeout=5000,  # 5s connection timeout
        )
        console.print("[green]Successfully connected to Chrome via debug port[/green]")
        return browser
    except Exception as e:
        console.print(f"[red]Failed to connect to Chrome: {str(e)}[/red]")
        return None


def open_new_tab(browser: Browser, url: str) -> Optional[Page]:
    """Open a new tab with the given URL."""
    try:
        # Get existing context or create new one
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        page.goto(url)
        console.print(f"[green]Successfully opened {url}[/green]")
        return page
    except Exception as e:
        console.print(f"[red]Failed to open {url}: {str(e)}[/red]")
        return None


def main() -> None:
    state = get_chrome_state()

    if state.has_debug_port:
        console.print("[green]Chrome is already running with debug port[/green]")
        return

    if state.is_running:
        if not Confirm.ask(
            "Chrome is running but without debug port. Would you like to quit and relaunch it with debug port?"
        ):
            console.print("[yellow]Skipping Chrome relaunch[/yellow]")
            return
    else:
        if not Confirm.ask(
            "Chrome is not running. Would you like to launch it with debug port?"
        ):
            console.print("[yellow]Skipping Chrome launch[/yellow]")
            return

    if state.is_running:
        if quit_chrome():
            console.print("[green]Successfully quit existing Chrome instances[/green]")

    if launch_chrome():
        console.print("[green]Successfully launched Chrome with debug port[/green]")
        return
    else:
        console.print("[red]Failed to launch Chrome[/red]")
        return
