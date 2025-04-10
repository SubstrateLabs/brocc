from brocc_li.cli.webview_manager import close_webview, is_webview_open, open_webview
from brocc_li.utils.logger import logger


def get_service_url(host, port):
    """Generate service URL from host and port"""
    return f"http://{host}:{port}"


def launch_webview():
    """Launch webview if it's not already running

    Returns:
        bool: True if webview was launched or is already running
    """
    return open_webview()


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
    logger.debug("Opening App in standalone window or focusing existing window")
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
