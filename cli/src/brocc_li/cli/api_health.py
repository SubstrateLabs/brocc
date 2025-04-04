import time
from typing import Any, Callable, Dict, Optional

import requests

from brocc_li.utils.logger import logger


def check_api_health(api_url: str, is_local: bool = False) -> Dict[str, Any]:
    """
    Check the health of an API endpoint

    Args:
        api_url: URL of the API to check
        is_local: Whether this is a local API (more retries)
    """
    max_retries = 3 if is_local else 1
    retry_delay = 0.5  # seconds

    for attempt in range(max_retries):
        try:
            response = requests.get(f"{api_url}/health", timeout=2)
            if response.ok:
                return {"status": "healthy", "data": response.json()}

            if attempt < max_retries - 1:
                logger.debug(
                    f"Retry {attempt + 1} for {api_url} - got status {response.status_code}"
                )
                time.sleep(retry_delay)
                continue

            return {"status": "unhealthy", "error": f"Status code: {response.status_code}"}
        except requests.RequestException as e:
            error_msg = str(e)
            # Truncate error message if it's too long
            if len(error_msg) > 100:
                error_msg = error_msg[:100] + "..."

            if attempt < max_retries - 1:
                logger.debug(f"Retry {attempt + 1} for {api_url} - {error_msg}")
                time.sleep(retry_delay)
                continue

            # Check if it's a connection error and simplify the message
            if "Connection refused" in str(e):
                return {"status": "error", "error": "Connection refused"}
            return {"status": "error", "error": error_msg}

    # This should never happen but ensures we always return a Dict
    return {"status": "error", "error": "Unknown error during health check"}


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
            update_ui_fn(f"{display_name}: [green]Healthy[/green] - {api_url}/health")
        logger.info(f"{display_name} is healthy: {result['data']}")
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
                                f"{display_name}: [green]Healthy[/green] (restarted) - {api_url}/health"
                            )
                        logger.success(f"Successfully restarted {display_name.lower()}")
                        return True

        # Update UI with error state
        if update_ui_fn:
            update_ui_fn(f"{display_name}: [red]Unavailable[/red] - {error}")
        logger.warning(f"{display_name} is not healthy: {error}")

    return is_healthy
