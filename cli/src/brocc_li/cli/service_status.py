import time
from typing import Any, Callable, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from brocc_li.utils.logger import logger


def check_api_health(api_url: str, is_local: bool = False) -> Dict[str, Any]:
    """
    Check the health of an API endpoint

    Args:
        api_url: URL of the API to check
        is_local: Whether this is a local API (more retries)
    """
    max_retries = 3 if is_local else 1

    # Configure retry strategy
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=0.1,  # Short delay between retries
        status_forcelist=[500, 502, 503, 504],  # Retry on server errors
        allowed_methods=["GET"],
        raise_on_status=False,  # Don't raise HTTPError, handle below
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    for attempt in range(max_retries):
        try:
            response = session.get(f"{api_url}/health", timeout=2)
            if response.ok:
                return {"status": "healthy", "data": response.json()}

            # If status is not ok, log and prepare for potential final failure message
            logger.debug(
                f"Attempt {attempt + 1}/{max_retries} for {api_url} - got status {response.status_code}"
            )
            # Don't sleep here, retry adapter handles backoff
            if attempt == max_retries - 1:
                return {"status": "unhealthy", "error": f"Status code: {response.status_code}"}

        except requests.exceptions.ConnectionError as e:
            logger.debug(
                f"Attempt {attempt + 1}/{max_retries} for {api_url} - Connection Error: {e}"
            )
            if attempt == max_retries - 1:
                return {"status": "error", "error": "Connection refused"}
            # Let the retry adapter handle sleeping/backoff for connection errors
        except requests.RequestException as e:
            error_msg = str(e)
            if len(error_msg) > 100:
                error_msg = error_msg[:100] + "..."

            logger.debug(
                f"Attempt {attempt + 1}/{max_retries} for {api_url} - Request Error: {error_msg}"
            )
            # Don't sleep here, retry adapter handles backoff
            if attempt == max_retries - 1:
                return {"status": "error", "error": error_msg}

    # This return is now reachable if all retries fail with exceptions not caught above
    return {"status": "error", "error": "Unknown error after retries during health check"}


def check_webview_status(api_url: str) -> Dict[str, Any]:
    """
    Check if the webview is active via the API

    Args:
        api_url: URL of the API to check (should be local FastAPI server)

    Returns:
        Dict with status information
    """
    try:
        response = requests.get(f"{api_url}/webview/status", timeout=2)
        if response.status_code == 200:
            return {"status": "checked", "data": response.json()}
        return {"status": "error", "error": f"Status code: {response.status_code}"}
    except requests.RequestException as e:
        error_msg = str(e)
        # Truncate error message if it's too long
        if len(error_msg) > 100:
            error_msg = error_msg[:100] + "..."
        return {"status": "error", "error": error_msg}


def check_and_update_api_status(
    api_name: str,
    api_url: str,
    is_local: bool = False,
    update_ui_fn: Optional[Callable[[str], None]] = None,
    restart_server_fn: Optional[Callable[[], bool]] = None,
) -> bool:
    """
    Check API health and update UI status

    Args:
        api_name: Display name of the API ("Site API" or "Local API")
        api_url: URL of the API to check
        is_local: Whether this is a local API
        update_ui_fn: Function to update UI with status
        restart_server_fn: Function to restart server if local API fails

    Returns:
        bool: Whether the API is healthy
    """
    display_name = api_name

    # Step 1: Update UI to show we're checking
    if update_ui_fn:
        update_ui_fn(f"{display_name}: Checking...")

    # Step 2: Check health
    result = check_api_health(api_url, is_local)
    is_healthy = result["status"] == "healthy"

    # Step 3: Handle results and update UI
    if is_healthy:
        if update_ui_fn:
            update_ui_fn(f"{display_name}: [green]Connected[/green] - {api_url}/health")
        logger.debug(f"{display_name} is healthy: {result['data']}")
    else:
        error = result.get("error", "Unknown error")

        # Handle connection refused specifically for local API
        if is_local and "Connection refused" in error:
            error = "Not started properly (server thread may have failed)"

            # Try restarting the server if we have a restart function
            if restart_server_fn:
                logger.warning(f"{display_name} not running, attempting to restart...")
                restart_success = restart_server_fn()

                if restart_success:
                    # Re-check health after restart
                    time.sleep(1)
                    result = check_api_health(api_url, is_local)
                    is_healthy = result["status"] == "healthy"

                    if is_healthy:
                        if update_ui_fn:
                            update_ui_fn(
                                f"{display_name}: [green]Connected[/green] (restarted) - {api_url}/health"
                            )
                        logger.success(f"Successfully restarted {display_name.lower()}")
                        return True

        # Update UI with error state
        if update_ui_fn:
            update_ui_fn(f"{display_name}: [red]Unavailable[/red] - {error}")
        logger.warning(f"{display_name} is not healthy: {error}")

    return is_healthy


def check_and_update_webview_status(
    api_url: str,
    ui_status_mapping: Optional[Dict[str, str]] = None,
    update_ui_fn: Optional[Callable[[str], None]] = None,
    update_button_fn: Optional[Callable[[bool, bool], None]] = None,
    previous_status: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Check webview status and update UI accordingly

    Args:
        api_url: URL of the API to check for webview status
        ui_status_mapping: Mapping of status strings for UI display
        update_ui_fn: Function to update UI with status message
        update_button_fn: Function to update button state (enabled, label)
        previous_status: Previous webview status for state change detection

    Returns:
        Dict with status information including:
        - is_open: Whether the webview is currently open
        - status_changed: Whether the status changed from previous check
        - previous_status: The previous status that was passed in
    """
    # Get default status messages if not provided
    if ui_status_mapping is None:
        ui_status_mapping = {
            "OPEN": "Window: [green]Open[/green]",
            "READY": "Window: [blue]Ready to launch[/blue]",
            "CLOSED": "Window: [yellow]Closed[/yellow]",
        }

    # Check webview status
    result = check_webview_status(api_url)

    # Extract actual webview status
    is_open = False
    if result["status"] == "checked" and "data" in result:
        data = result["data"]
        # Both 'active' and 'process_running' must be True for window to be considered open
        is_open = data.get("active", False) and data.get("process_running", False)

    # Detect status change
    status_changed = previous_status is not None and is_open != previous_status

    # Update UI if function provided
    if update_ui_fn:
        if is_open:
            update_ui_fn(ui_status_mapping.get("OPEN", "Window is open"))
        else:
            if status_changed and previous_status:
                update_ui_fn(ui_status_mapping.get("CLOSED", "Window was closed"))
            else:
                update_ui_fn(ui_status_mapping.get("READY", "Window ready to launch"))

    # Update button if function provided
    if update_button_fn:
        update_button_fn(is_open, status_changed)

    # Return comprehensive status
    return {
        "is_open": is_open,
        "status_changed": status_changed,
        "previous_status": previous_status,
        "raw_result": result,
    }
