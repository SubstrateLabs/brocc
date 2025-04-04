#!/usr/bin/env python
import signal
import sys

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


# Handle signals properly
def signal_handler(sig, frame):
    sys.exit(0)


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

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
