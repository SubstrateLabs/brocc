#!/usr/bin/env python
"""
Standalone script to run the system tray icon in its own process.
This ensures it has its own main thread which is required for macOS.
"""

import argparse
import base64
import os
import re
import signal
import sys
import time
from io import BytesIO
from pathlib import Path

import requests

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError as e:
    print(f"ERROR: Failed to import required modules: {e}")
    print("Please ensure pystray and pillow are installed")
    sys.exit(1)

# Parse command line arguments
parser = argparse.ArgumentParser(description="Run system tray icon for Brocc")
parser.add_argument("--host", type=str, default="127.0.0.1", help="WebUI host")
parser.add_argument("--port", type=str, default="8023", help="WebUI port")
parser.add_argument("--api-host", type=str, default="127.0.0.1", help="API host")
parser.add_argument("--api-port", type=str, default="8022", help="API port")
parser.add_argument("--version", type=str, default="0.0.1", help="App version")
parser.add_argument("--exit-file", type=str, help="Path to file to watch for exit signal")
args = parser.parse_args()

# Set up the URL for the WebUI and API
WEBUI_URL = f"http://{args.host}:{args.port}"
API_URL = f"http://{args.api_host}:{args.api_port}"
VERSION = args.version

# Store the tray icon reference
icon = None


def extract_png_from_svg(svg_path):
    """Extract the base64-encoded PNG image from an SVG file"""
    try:
        # Read the SVG file
        with open(svg_path, "r") as f:
            svg_content = f.read()

        # Extract the base64-encoded PNG data using regex
        match = re.search(r'xlink:href="data:image/png;base64,([^"]+)"', svg_content)
        if match:
            # Decode the base64 data
            png_data = base64.b64decode(match.group(1))
            # Create a PIL Image from the PNG data
            return Image.open(BytesIO(png_data))
    except Exception as e:
        print(f"Error extracting PNG from SVG: {e}")

    return None


def create_tray_icon():
    """Create a broccoli icon for system tray using the SVG file"""
    # Try to load the broccoli SVG
    script_dir = Path(__file__).parent
    svg_path = script_dir / "brocc.svg"

    if svg_path.exists():
        # Extract the PNG from the SVG file
        image = extract_png_from_svg(svg_path)
        if image:
            # Resize to appropriate size for menu bar (16x16 or 22x22)
            # Use integer constant instead of enum for better compatibility
            return image.resize((22, 22), 1)  # 1 = high quality downsampling

    # Fallback to a simple circle if SVG loading fails
    print("Using fallback icon (SVG loading failed)")
    width, height = 22, 22
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Draw a simple black circle with white outline
    circle_x, circle_y = width // 2, height // 2
    circle_radius = 9
    draw.ellipse(
        (
            circle_x - circle_radius,
            circle_y - circle_radius,
            circle_x + circle_radius,
            circle_y + circle_radius,
        ),
        fill=(0, 0, 0, 255),
        outline=(255, 255, 255, 255),
    )

    return image


def on_open_window(icon, item):
    """Open the WebUI window using the API"""
    try:
        print("Launching WebUI window via API")
        response = requests.post(
            f"{API_URL}/webview/launch",
            params={"webui_url": WEBUI_URL, "title": f"🥦 Brocc v{VERSION}"},
        )

        if response.status_code == 200:
            result = response.json()
            print(f"API response: {result}")
            if result.get("status") == "launching":
                print("Successfully launched webview via API")
            elif result.get("status") == "already_running":
                print("Webview is already running but couldn't bring to foreground")
            elif result.get("status") == "focused":
                print("Successfully brought existing webview to the foreground")
        else:
            print(f"Error launching webview: {response.status_code}")
            # Fallback to direct browser open if API fails
            import webbrowser

            print(f"Falling back to direct browser open: {WEBUI_URL}")
            webbrowser.open(WEBUI_URL)
    except Exception as e:
        print(f"Error calling API to launch webview: {e}")
        # Fallback to direct browser open if API fails
        import webbrowser

        print(f"Falling back to direct browser open: {WEBUI_URL}")
        webbrowser.open(WEBUI_URL)


def setup_icon():
    """Set up and run the system tray icon"""
    global icon

    # Create the icon image
    icon_image = create_tray_icon()

    # Create the menu
    menu = pystray.Menu(
        pystray.MenuItem("Open Window", on_open_window, default=True),
    )

    # Create the icon
    icon = pystray.Icon("brocc", icon=icon_image, title=f"Brocc v{VERSION}", menu=menu)

    print(f"Starting system tray icon for Brocc v{VERSION}")
    print(f"WebUI URL: {WEBUI_URL}")
    print(f"API URL: {API_URL}")

    # Run the icon
    icon.run()
    print("System tray icon stopped")


def signal_handler(sig, frame):
    """Handle termination signals"""
    print("Received signal to terminate")
    if icon:
        icon.stop()
    sys.exit(0)


def watch_exit_file():
    """Monitor exit file for parent process termination"""
    if not args.exit_file:
        return

    import threading

    def monitor_file():
        while True:
            try:
                if not os.path.exists(args.exit_file):
                    print("Exit file removed, shutting down")
                    if icon:
                        icon.stop()
                    break
                time.sleep(1)
            except Exception as e:
                print(f"Error monitoring exit file: {e}")
                pass

    threading.Thread(target=monitor_file, daemon=True).start()


if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start file monitoring in a thread if exit file is provided
    watch_exit_file()

    # Run the icon in the main thread
    setup_icon()
