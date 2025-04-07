#!/usr/bin/env python
import atexit
import os
import platform
import signal
import sys
import threading
import time

import psutil  # Make sure this is in requirements

# Global window reference
window = None
# Flag to track if we're shutting down
shutting_down = False
# Parent process ID to monitor
parent_pid = None

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
title = sys.argv[2] if len(sys.argv) > 2 else "Brocc App"
# Get parent PID from command line args (optional)
if len(sys.argv) > 3:
    try:
        parent_pid = int(sys.argv[3])
        print(f"Monitoring parent process with PID: {parent_pid}")
    except ValueError:
        print(f"Warning: Invalid parent PID provided: {sys.argv[3]}")


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
    global window, shutting_down
    shutting_down = True

    # First destroy the window to release all UI resources
    if window and hasattr(webview, "windows") and webview.windows:
        try:
            print("Destroying window on exit")
            window.destroy()
        except Exception as e:
            print(f"Error destroying window: {e}")

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


# Function to monitor parent process
def monitor_parent_process():
    """Monitor the parent process and exit if it terminates"""
    global shutting_down, parent_pid

    if parent_pid is None:
        # If no parent PID specified, get the parent of this process
        parent_pid = os.getppid()
        print(f"Using current parent process PID: {parent_pid}")

    print(f"Starting parent process monitor for PID: {parent_pid}")

    while not shutting_down:
        try:
            # Check if parent process exists
            if not psutil.pid_exists(parent_pid):
                print(f"Parent process (PID: {parent_pid}) no longer exists, shutting down")
                shutting_down = True
                cleanup()
                os._exit(0)  # Force exit

            # Check if parent is zombie/dead but still in process table
            try:
                parent = psutil.Process(parent_pid)
                if parent.status() == psutil.STATUS_ZOMBIE:
                    print("Parent process is zombie, shutting down")
                    shutting_down = True
                    cleanup()
                    os._exit(0)  # Force exit
            except psutil.NoSuchProcess:
                print("Parent process no longer exists (race condition), shutting down")
                shutting_down = True
                cleanup()
                os._exit(0)  # Force exit

        except Exception as e:
            print(f"Error monitoring parent process: {e}")
            # Don't exit on monitoring errors

        # Check every second
        time.sleep(1)


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

    # Start parent process monitor
    threading.Thread(target=monitor_parent_process, daemon=True).start()

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
