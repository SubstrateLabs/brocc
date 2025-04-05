import threading

from brocc_li.cli.fastapi_server import FASTAPI_HOST, FASTAPI_PORT
from brocc_li.cli.webview_manager import close_webview, is_webview_open, open_webview
from brocc_li.utils.logger import logger


def get_service_url(host, port):
    """Generate service URL from host and port"""
    return f"http://{host}:{port}"


def notify_webview_shutdown():
    """Send shutdown message to webview via API"""
    try:
        logger.info("Sending shutdown signal to webview")
        # Use a completely non-blocking approach with no wait
        import requests

        def make_request():
            try:
                # Call the synchronous endpoint
                response = requests.post(
                    f"{get_service_url(FASTAPI_HOST, FASTAPI_PORT)}/webview/shutdown",
                    timeout=2.0,  # Give it a reasonable timeout
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Webview shutdown response: {result}")
                    return True
                else:
                    logger.warning(f"Failed to send shutdown signal: {response.status_code}")
                    return False
            except Exception as e:
                logger.error(f"Error sending shutdown signal: {e}")
                return False

        # Start the thread but don't wait for it
        thread = threading.Thread(target=make_request, daemon=True)
        thread.start()
        # Give a short time for the request to complete
        thread.join(timeout=0.5)

    except Exception as e:
        logger.error(f"Error initiating webview shutdown: {e}")
        # Fall back to direct termination in case API call fails
        try:
            from brocc_li.cli.fastapi_server import _WEBVIEW_PROCESS

            if _WEBVIEW_PROCESS and _WEBVIEW_PROCESS.poll() is None:
                logger.info("Fallback: Directly terminating webview process")
                _WEBVIEW_PROCESS.terminate()
        except Exception as term_err:
            logger.error(f"Error in fallback termination: {term_err}")


def launch_webview():
    """Launch webview if it's not already running

    Returns:
        bool: True if webview was launched or is already running
    """
    return open_webview()


def maybe_launch_webview_if_logged_in(is_logged_in, update_ui_fn=None, update_button_fn=None):
    """Launch webview if user is logged in and webview not already running

    Args:
        is_logged_in: Boolean indicating if user is logged in
        update_ui_fn: Optional function to update UI status
        update_button_fn: Optional function to update button state
    """
    if is_logged_in and not is_webview_open():
        logger.info("User is logged in - launching webview")
        # Launch the webview for logged in users
        success = open_webview()
        logger.info(f"Webview launch {'succeeded' if success else 'failed'}")
        if update_ui_fn and update_button_fn:
            update_ui_fn()
            update_button_fn()
        return success
    elif is_logged_in and is_webview_open():
        logger.info("User is logged in but webview is already open")
        return True
    else:
        logger.info("User is not logged in - not launching webview")
        # Just update UI to show it's ready
        if update_ui_fn and update_button_fn:
            update_ui_fn()
            update_button_fn()
        return False


def handle_webview_after_logout(update_ui_fn=None, update_button_fn=None):
    """Check and close webview after logout if needed

    Args:
        update_ui_fn: Optional function to update UI status
        update_button_fn: Optional function to update button state

    Returns:
        bool: True if webview was closed
    """
    # Update UI to note webview may still be running
    if is_webview_open():
        # Show logged out status if function provided
        if update_ui_fn:
            update_ui_fn(status="LOGGED_OUT")

        # Close the webview since user is no longer logged in
        if close_webview():
            # Update UI if function provided
            if update_ui_fn:
                update_ui_fn(status="CLOSED")

            # Update button state if function provided
            if update_button_fn:
                update_button_fn()

            return True
    return False


def open_or_focus_webview(ui_status_mapping, update_ui_fn=None, previous_status=None):
    """Open webview or focus existing window

    Args:
        ui_status_mapping: Dictionary mapping status to UI messages
        update_ui_fn: Optional function to update UI status
        previous_status: Previous webview status for comparison

    Returns:
        bool: True if successful
    """
    logger.info("Opening App in standalone window or focusing existing window")
    success = open_webview()

    if success and update_ui_fn:
        # Check if it was launched or just focused
        if is_webview_open():
            if previous_status is None or not previous_status:
                # It was just launched
                update_ui_fn(ui_status_mapping["WINDOW_LAUNCHED"])
            else:
                # It was already running and focused
                update_ui_fn(ui_status_mapping["WINDOW_FOCUSED"])
        else:
            # Launching failed despite success=True
            update_ui_fn(ui_status_mapping["WINDOW_STATUS_UNCLEAR"])
    elif not success and update_ui_fn:
        update_ui_fn(ui_status_mapping["WINDOW_LAUNCH_FAILED"])

    return success
