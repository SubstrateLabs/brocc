#!/usr/bin/env python
"""
Standalone script to run the system tray icon in its own process.
This ensures it has its own main thread which is required for macOS.
"""

import argparse
import atexit
import base64
import json
import os
import re
import signal
import sys
import threading
import time
from io import BytesIO
from pathlib import Path

import requests
import websocket  # pip install websocket-client

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError as e:
    print(f"ERROR: Failed to import required modules: {e}")
    print("Please ensure pystray and pillow are installed")
    sys.exit(1)

# Parse command line arguments
parser = argparse.ArgumentParser(description="Run system tray icon for Brocc")
parser.add_argument("--host", type=str, default="127.0.0.1", help="App host")
parser.add_argument("--port", type=str, default="8023", help="App port")
parser.add_argument("--api-host", type=str, default="127.0.0.1", help="API host")
parser.add_argument("--api-port", type=str, default="8022", help="API port")
parser.add_argument("--version", type=str, default="0.0.1", help="App version")
parser.add_argument(
    "--exit-file", type=str, help="Path to file to watch for exit signal (deprecated)"
)
args = parser.parse_args()

# Set up the URL for the App and API
WEBAPP_URL = f"http://{args.host}:{args.port}"
API_URL = f"http://{args.api_host}:{args.api_port}"
VERSION = args.version
WS_URL = f"ws://{args.api_host}:{args.api_port}/ws/systray"

# Store the tray icon reference
icon = None
# WebSocket connection
ws_client = None
# Flag to track if we're shutting down
shutting_down = False
# Counter for connection attempts
reconnect_count = 0
# Max number of reconnection attempts
MAX_RECONNECT_ATTEMPTS = 3


# WebSocket event handlers
def on_ws_message(ws, message):
    global shutting_down
    try:
        data = json.loads(message)
        print(f"WebSocket message: {data}")

        # Handle shutdown command
        if data.get("action") == "shutdown":
            print("Received shutdown command via WebSocket")
            shutting_down = True
            cleanup()
            sys.exit(0)

        # Handle heartbeat response
        if data.get("action") == "heartbeat" and data.get("status") == "ok":
            print("Heartbeat acknowledged by server")
    except Exception as e:
        print(f"Error processing WebSocket message: {e}")


def on_ws_error(ws, error):
    global shutting_down, reconnect_count
    print(f"WebSocket error: {error}")

    # If the main app is shutting down or has stopped, we should close too
    if not shutting_down:
        # Check if we've hit the max reconnection attempts
        if reconnect_count >= MAX_RECONNECT_ATTEMPTS:
            print(
                f"Failed to maintain connection after {MAX_RECONNECT_ATTEMPTS} attempts. Exiting."
            )
            shutting_down = True
            cleanup()
            sys.exit(1)
        else:
            print(
                f"WebSocket error - attempting to reconnect (attempt {reconnect_count + 1}/{MAX_RECONNECT_ATTEMPTS})..."
            )
            threading.Thread(
                target=reconnect_websocket_after_delay, args=(reconnect_count + 1,), daemon=True
            ).start()


def on_ws_close(ws, close_status_code, close_msg):
    global shutting_down, reconnect_count
    print(f"WebSocket connection closed: {close_status_code} - {close_msg}")

    # If connection was closed and we're not already shutting down,
    # it likely means the main app has exited. We should exit too.
    if not shutting_down:
        # Check if we've hit the max reconnection attempts
        if reconnect_count >= MAX_RECONNECT_ATTEMPTS:
            print(
                f"WebSocket connection lost - main app may have exited. Shutting down after {MAX_RECONNECT_ATTEMPTS} reconnection attempts."
            )
            shutting_down = True
            cleanup()
            sys.exit(0)
        else:
            print(
                f"WebSocket disconnected - attempting to reconnect (attempt {reconnect_count + 1}/{MAX_RECONNECT_ATTEMPTS})..."
            )
            threading.Thread(
                target=reconnect_websocket_after_delay, args=(reconnect_count + 1,), daemon=True
            ).start()


def on_ws_open(ws):
    global reconnect_count
    print(f"WebSocket connection established to {WS_URL}")
    # Reset reconnection counter on successful connection
    reconnect_count = 0
    # Start heartbeat thread
    threading.Thread(target=heartbeat_thread, daemon=True).start()


def heartbeat_thread():
    """Send periodic heartbeats to keep the connection alive"""
    global ws_client, shutting_down

    # Counter for consecutive failed heartbeats
    failed_heartbeats = 0

    while ws_client and not shutting_down:
        try:
            if ws_client.sock and ws_client.sock.connected:
                print("Sending heartbeat to server...")
                ws_client.send(json.dumps({"action": "heartbeat"}))
                failed_heartbeats = 0  # Reset on successful send
            else:
                failed_heartbeats += 1
                print(f"WebSocket not connected for heartbeat ({failed_heartbeats})")

                # If multiple heartbeats fail, the server is likely gone
                if failed_heartbeats >= 3:
                    print("Multiple heartbeats failed. Server may be gone, shutting down.")
                    shutting_down = True
                    cleanup()
                    # Exit using timer to avoid blocking in heartbeat thread
                    threading.Timer(0.5, lambda: sys.exit(0)).start()
                    return
        except Exception as e:
            print(f"Error sending heartbeat: {e}")
            failed_heartbeats += 1

            # If multiple heartbeats fail, the server is likely gone
            if failed_heartbeats >= 3:
                print("Multiple heartbeats failed with error. Server may be gone, shutting down.")
                shutting_down = True
                cleanup()
                # Exit using timer to avoid blocking in heartbeat thread
                threading.Timer(0.5, lambda: sys.exit(0)).start()
                return

        time.sleep(5)  # Send heartbeat every 5 seconds


def reconnect_websocket_after_delay(attempt=1):
    """Wait a bit and then try to reconnect the WebSocket"""
    global shutting_down, reconnect_count

    # Update the global counter
    reconnect_count = attempt

    time.sleep(5)  # Wait 5 seconds before attempting reconnection

    if shutting_down:
        return

    try:
        # After multiple failed attempts, we should exit to prevent zombie processes
        if attempt > MAX_RECONNECT_ATTEMPTS:
            print(
                f"Failed to reconnect after {MAX_RECONNECT_ATTEMPTS} attempts. Exiting gracefully."
            )
            shutting_down = True
            cleanup()
            # Give a moment for cleanup to complete before exit
            time.sleep(1)
            sys.exit(1)

        setup_websocket()
    except Exception as e:
        print(f"Failed to reconnect WebSocket: {e}")
        # Try again with increased attempt counter
        threading.Thread(
            target=lambda: reconnect_websocket_after_delay(attempt + 1), daemon=True
        ).start()


# Setup WebSocket connection
def setup_websocket():
    global ws_client
    try:
        # Create WebSocket client
        ws_client = websocket.WebSocketApp(
            WS_URL,
            on_message=on_ws_message,
            on_error=on_ws_error,
            on_close=on_ws_close,
            on_open=on_ws_open,
        )

        # Start WebSocket in a background thread
        threading.Thread(target=ws_client.run_forever, daemon=True).start()
        print(f"Started WebSocket client connecting to {WS_URL}")
    except Exception as e:
        print(f"Failed to start WebSocket client: {e}")


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
    """Open the App window using the API"""
    try:
        print("Launching App window via API")
        response = requests.post(
            f"{API_URL}/webview/launch",
            params={"webapp_url": WEBAPP_URL, "title": f"🥦 Brocc v{VERSION}"},
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

            print(f"Falling back to direct browser open: {WEBAPP_URL}")
            webbrowser.open(WEBAPP_URL)
    except Exception as e:
        print(f"Error calling API to launch webview: {e}")
        # Fallback to direct browser open if API fails
        import webbrowser

        print(f"Falling back to direct browser open: {WEBAPP_URL}")
        webbrowser.open(WEBAPP_URL)


def setup_icon():
    """Set up and run the system tray icon"""
    global icon

    # Create the icon image
    icon_image = create_tray_icon()

    # Create the menu
    menu = pystray.Menu(
        pystray.MenuItem("Show Brocc window", on_open_window, default=True),
    )

    # Create the icon
    icon = pystray.Icon("brocc", icon=icon_image, title=f"Brocc v{VERSION}", menu=menu)

    print(f"Starting system tray icon for Brocc v{VERSION}")
    print(f"App URL: {WEBAPP_URL}")
    print(f"API URL: {API_URL}")

    # Run the icon
    icon.run()
    print("System tray icon stopped")


def signal_handler(sig, frame):
    """Handle termination signals"""
    print("Received signal to terminate")
    cleanup()
    # Use os._exit which doesn't raise SystemExit exception
    os._exit(0)  # Exit immediately without throwing SystemExit


def cleanup():
    """Clean up resources before exiting"""
    global icon, ws_client, shutting_down

    shutting_down = True

    # First stop the icon
    try:
        if icon:
            print("Stopping system tray icon")
            icon.stop()
            # Wait briefly for the icon to stop
            time.sleep(0.1)
    except Exception as e:
        print(f"Error stopping icon: {e}")

    # Then close WebSocket connection
    if ws_client:
        try:
            # Let the server know we're shutting down
            try:
                if ws_client.sock and ws_client.sock.connected:
                    ws_client.send(json.dumps({"action": "closing"}))
            except Exception:
                # Ignore errors during shutdown
                pass

            # Close the connection
            try:
                ws_client.close()
            except Exception:
                # Ignore errors during shutdown
                pass

            print("WebSocket connection closed")
        except Exception as e:
            print(f"Error closing WebSocket: {e}")


# Register cleanup function to ensure tray icon is removed on exit
atexit.register(cleanup)


def watch_exit_file():
    """Monitor exit file for parent process termination (deprecated)"""
    if not args.exit_file:
        return

    print("WARNING: Using deprecated exit-file mechanism. WebSocket is preferred.")

    def monitor_file():
        while not shutting_down:
            try:
                if not os.path.exists(args.exit_file):
                    print("Exit file removed, shutting down")
                    cleanup()
                    # Use os._exit to exit cleanly
                    os._exit(0)
                time.sleep(1)
            except Exception as e:
                print(f"Error monitoring exit file: {e}")
                # Don't use bare except
                pass

    threading.Thread(target=monitor_file, daemon=True).start()


if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start file monitoring in a thread if exit file is provided (legacy support)
    watch_exit_file()

    # Setup WebSocket connection
    setup_websocket()

    # Run the icon in the main thread
    setup_icon()
