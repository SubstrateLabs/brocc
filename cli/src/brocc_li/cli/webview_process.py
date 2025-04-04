#!/usr/bin/env python
import atexit
import json
import os  # Re-add this important import
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
# Counter for connection attempts
reconnect_count = 0
# Max number of reconnection attempts
MAX_RECONNECT_ATTEMPTS = 3

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
title = sys.argv[2] if len(sys.argv) > 2 else "Brocc WebApp"
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
    print(f"WebSocket connection established to {ws_url}")
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

        time.sleep(5)  # Send heartbeat every 5 seconds instead of 15 for faster detection


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

    # Force exit the process after cleanup to ensure nothing keeps it alive
    print("Cleanup complete - exiting process")
    # Give a moment for cleanup to complete before exit
    threading.Timer(1.0, lambda: os._exit(0)).start()


# Register cleanup handler
atexit.register(cleanup)


# Function to handle window closing
def on_window_close():
    """Called when the webview window is closed by the user"""
    print("Window closed by user - initiating cleanup")
    global shutting_down
    shutting_down = True
    # This will trigger the atexit handler after the function completes
    sys.exit(0)


# Main execution
if __name__ == "__main__":
    # Set up a more reasonable shutdown timer - gives time to start up
    # but ensures we don't stay alive forever if something gets stuck
    def delayed_watchdog():
        global shutting_down, window
        # Give the app 30 seconds to properly initialize
        time.sleep(30)
        # If we're still running (GUI is active) after 30 seconds, don't exit
        if not shutting_down and window is None:
            print("Watchdog: Window failed to initialize after 30 seconds. Exiting.")
            os._exit(1)  # Force exit if window never appears

    # Start watchdog timer
    threading.Thread(target=delayed_watchdog, daemon=True).start()

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
            # Create window with on_close handler to ensure cleanup
            window = webview.create_window(
                title, url, width=1024, height=768, resizable=True, on_top=False
            )

            # Set on_close handler if supported
            if hasattr(window, "events") and hasattr(window.events, "closed"):
                window.events.closed += on_window_close
                print("Registered window close handler")

            print("Starting webview GUI loop")
            # Start webview in a way that ensures it will exit
            webview.start(func=lambda: None, debug=False)
            print("Webview closed")

            # If we get here, it means the webview loop has ended
            # Make sure we exit
            on_window_close()
        else:
            print("ERROR: The webview module doesn't have create_window attribute")
            print(f"Available attributes: {dir(webview)}")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR creating window: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
