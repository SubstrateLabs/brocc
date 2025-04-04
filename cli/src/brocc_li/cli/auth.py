import json
import time
import webbrowser

import requests

from brocc_li.utils.auth_data import clear_auth_data, save_auth_data
from brocc_li.utils.logger import logger


def initiate_login(api_url, update_status_fn=None, display_auth_url_fn=None):
    """
    Start the login process

    Args:
        api_url: The base API URL
        update_status_fn: Optional callback to update UI status
        display_auth_url_fn: Optional callback to display auth URL

    Returns:
        auth_data or None if failed
    """
    if update_status_fn:
        update_status_fn("Initiating authentication...")

    try:
        # Initial auth request
        target_url = f"{api_url}/auth/cli/start"
        logger.info(f"Connecting to: {target_url}")

        response = requests.get(target_url)

        if response.status_code == 404:
            raise Exception(
                f"API route not found (404): {target_url}\nIs your Next.js server running?"
            )

        if not response.ok:
            error_text = response.text
            if len(error_text) > 500 and "<!DOCTYPE html>" in error_text:
                error_text = f"{error_text[:150]}... [HTML content truncated]"
            raise Exception(f"Server returned {response.status_code}: {error_text}")

        data = response.json()
        auth_url = data.get("authUrl")
        session_id = data.get("sessionId")

        if not auth_url or not session_id:
            raise Exception("Invalid response from server")

        if update_status_fn:
            update_status_fn("Opening browser for authentication...")

        # Display the auth URL in the UI if callback provided
        if display_auth_url_fn:
            display_auth_url_fn(auth_url)

        logger.info("Authentication URL ready")
        logger.info("Please open this URL in your browser to authenticate")

        # Open browser
        try:
            webbrowser.open(auth_url)
        except Exception as e:
            logger.error(f"Error opening browser: {e}")
            logger.info(f"Please open this URL manually: {auth_url}")

        if update_status_fn:
            update_status_fn("Waiting for authentication in browser...")

        # Poll for token
        token = poll_for_token(api_url, session_id)

        if update_status_fn:
            update_status_fn("Authentication successful!")

        # Debug auth token info
        logger.debug(
            f"Auth info: {token['userId']} / API key length: {len(token.get('apiKey', ''))}"
        )

        # Check if we have an API key
        api_key = token.get("apiKey")
        if api_key:
            logger.debug(f"API key: {api_key[:8]}...{api_key[-5:]}")
        else:
            logger.warning("No API key received from authentication process")
            if update_status_fn:
                update_status_fn("Warning: No API key received")

        # Save the token locally
        auth_data = {
            "accessToken": token["accessToken"],
            "userId": token["userId"],
            "email": token.get("email"),
            "apiKey": token.get("apiKey"),
            "_source": "browser",
        }
        save_auth_data(auth_data)

        return auth_data

    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        if update_status_fn:
            update_status_fn("Authentication failed")
        return None


def poll_for_token(api_url, session_id, max_attempts=120):
    """Poll the token endpoint until auth is complete"""
    attempts = 0
    consecutive_errors = 0

    token_url = f"{api_url}/auth/cli/token?sessionId={session_id}"
    logger.info(f"Polling for token at: {token_url}")

    while attempts < max_attempts:
        try:
            logger.debug(f"Poll attempt #{attempts + 1}...")
            response = requests.get(token_url, timeout=10)

            logger.debug(f"Poll response status: {response.status_code}")

            # Handle 404 errors specially on first attempt
            if response.status_code == 404 and attempts == 0:
                logger.error(f"Error: API route not found (404): {token_url}")
                raise Exception(
                    f"API route not found: {token_url}\nIs your Next.js server running with the correct routes?"
                )

            # Reset consecutive errors on successful request
            consecutive_errors = 0

            # Process response
            try:
                data = response.json()
                logger.debug(f"Poll response data: {json.dumps(data, indent=2)}")
            except Exception as e:
                # Handle non-JSON responses
                text = response.text
                logger.error(f"Error parsing JSON: {e}")
                logger.error(f"Response text: {text[:150]}...")
                raise Exception(f"Server returned non-JSON response: {text[:150]}...") from e

            if response.ok and data.get("status") == "complete":
                logger.success(
                    f"Authentication complete. API key received: {bool(data.get('apiKey'))}"
                )
                return {
                    "accessToken": data["accessToken"],
                    "userId": data["userId"],
                    "email": data.get("email"),
                    "apiKey": data.get("apiKey"),
                }

            # If the response indicates an error, throw it to be caught below
            if not response.ok:
                raise Exception(f"Server returned {response.status_code}: {json.dumps(data)}")

            # Wait before trying again
            time.sleep(1)
            attempts += 1

        except Exception as e:
            error_message = str(e)
            is_abort_error = "abort" in error_message or "timeout" in error_message

            if is_abort_error:
                logger.warning(f"Poll attempt {attempts + 1} timed out")
            else:
                logger.error(f"Poll attempt {attempts + 1} failed: {e}")

            # Count consecutive errors
            consecutive_errors += 1

            # After 3 consecutive errors, increase wait time
            if consecutive_errors >= 3:
                # If we've had many consecutive errors, throw to exit the loop
                if consecutive_errors >= 10:
                    raise Exception(
                        "Connection to authentication server failed repeatedly. Please check your network connection and try again."
                    ) from e

                # Exponential backoff
                backoff_delay = min(5, 1 * pow(1.5, consecutive_errors - 3))
                time.sleep(backoff_delay)
            else:
                time.sleep(1)

            attempts += 1

    raise Exception("Authentication timed out. Please try again.")


def logout():
    """
    Handle logout

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        clear_auth_data()
        return True
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        return False
