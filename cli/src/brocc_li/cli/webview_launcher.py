#!/usr/bin/env python
import atexit
import json
import os
import platform
import signal
import sys
import threading
import time

import websocket  # pip install websocket-client

# Global window reference
window = None
# WebSocket connection
ws_client = None
# Flag to track if we're shutting down
shutting_down = False

# Try to import webview - the import name for pywebview is simply 'webview'
try:
    import webview

    print(f"Successfully imported webview (version: {getattr(webview, '__version__', 'unknown')})")
except ImportError as e:
    print(f"ERROR: Failed to import webview module - {e}")
    print("Please ensure pywebview is installed: pip install pywebview>=5.4")
    sys.exit(1)

# Get URL and title from command line args
url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8023"
title = sys.argv[2] if len(sys.argv) > 2 else "Brocc WebUI"
# Default API details
api_host = "127.0.0.1"
api_port = "8022"

# Parse optional API arguments
if len(sys.argv) > 3:
    api_host = sys.argv[3]
if len(sys.argv) > 4:
    api_port = sys.argv[4]

ws_url = f"ws://{api_host}:{api_port}/ws/webview"


# Handle WebSocket messages
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
    except Exception as e:
        print(f"Error processing WebSocket message: {e}")


def on_ws_error(ws, error):
    global shutting_down
    print(f"WebSocket error: {error}")
    # Any WebSocket error is likely a sign the server is gone
    if not shutting_down:
        print("WebSocket error - server may be gone. Shutting down.")
        shutting_down = True
        cleanup()
        # Use a thread to exit after a short delay to avoid blocking
        threading.Thread(target=lambda: (time.sleep(0.5), sys.exit(0)), daemon=True).start()


def on_ws_close(ws, close_status_code, close_msg):
    global shutting_down
    print(f"WebSocket connection closed: {close_status_code} - {close_msg}")
    # If the WebSocket closes unexpectedly, this might mean the server is gone
    if not shutting_down:
        print("WebSocket disconnected - server may have terminated. Shutting down.")
        shutting_down = True
        cleanup()
        # Use a thread to exit after a short delay to avoid blocking
        threading.Thread(target=lambda: (time.sleep(0.5), sys.exit(0)), daemon=True).start()


def on_ws_open(ws):
    print(f"WebSocket connection established to {ws_url}")
    # Start heartbeat thread
    threading.Thread(target=heartbeat_thread, daemon=True).start()


def heartbeat_thread():
    """Send periodic heartbeats to keep the connection alive"""
    global ws_client, shutting_down
    while ws_client and not shutting_down:
        try:
            if ws_client.sock and ws_client.sock.connected:
                ws_client.send(json.dumps({"action": "heartbeat"}))
        except Exception as e:
            print(f"Error sending heartbeat: {e}")
        time.sleep(15)  # Send heartbeat every 15 seconds


# Setup WebSocket connection
def setup_websocket():
    global ws_client
    try:
        # Create WebSocket client
        ws_client = websocket.WebSocketApp(
            ws_url,
            on_message=on_ws_message,
            on_error=on_ws_error,
            on_close=on_ws_close,
            on_open=on_ws_open,
        )

        # Start WebSocket in a background thread
        threading.Thread(target=ws_client.run_forever, daemon=True).start()
        print(f"Started WebSocket client connecting to {ws_url}")
    except Exception as e:
        print(f"Failed to start WebSocket client: {e}")


# Handle signals properly
def signal_handler(sig, frame):
    global shutting_down
    print(f"Received signal {sig}, closing webview")
    shutting_down = True
    cleanup()
    sys.exit(0)


# Setup signal handlers for graceful shutdown
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Add Windows-specific signal handlers
if platform.system() == "Windows":
    try:
        # Use getattr to avoid linter errors
        win_break_signal = getattr(signal, "SIGBREAK", None)
        if win_break_signal is not None:
            signal.signal(win_break_signal, signal_handler)
    except (AttributeError, ValueError):
        # SIGBREAK doesn't exist or can't be used on this Windows installation
        pass


# Cleanup function to ensure window is destroyed
def cleanup():
    global window, ws_client, shutting_down
    shutting_down = True

    # First destroy the window to release all UI resources
    if window and hasattr(webview, "windows") and webview.windows:
        try:
            print("Destroying window on exit")
            window.destroy()
        except Exception as e:
            print(f"Error destroying window: {e}")

    # Then close WebSocket
    if ws_client:
        try:
            # Let the server know we're shutting down
            try:
                if ws_client.sock and ws_client.sock.connected:
                    ws_client.send(json.dumps({"action": "closing"}))
            except Exception:  # Specify exception type
                # Ignore errors during shutdown
                pass

            # Close the connection
            try:
                ws_client.close()
            except Exception:  # Specify exception type
                # Ignore errors during shutdown
                pass

            print("WebSocket connection closed")
        except Exception as e:
            print(f"Error closing WebSocket: {e}")


# Register cleanup handler
atexit.register(cleanup)


# Main execution
if __name__ == "__main__":
    # Set up a force quit timer
    def force_exit():
        global shutting_down
        # Wait for a bit, then force exit if still running
        time.sleep(5)
        if not shutting_down:
            print("Force quitting after timeout")
            os._exit(1)  # Force immediate exit

    # Start force exit timer in case anything hangs
    threading.Thread(target=force_exit, daemon=True).start()

    # Set up WebSocket connection
    setup_websocket()

    # Create and start the window
    print(f"Creating webview for: {url}")
    try:
        # Check if create_window exists
        if hasattr(webview, "create_window"):
            print(f"Webview module: {webview.__name__}")
            print(
                f"Available webview functions: {[name for name in dir(webview) if not name.startswith('_')]}"
            )
            window = webview.create_window(title, url, width=1024, height=768, resizable=True)
            print("Starting webview GUI loop")
            webview.start()
            print("Webview closed")
        else:
            print("ERROR: The webview module doesn't have create_window attribute")
            print(f"Available attributes: {dir(webview)}")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR creating window: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
