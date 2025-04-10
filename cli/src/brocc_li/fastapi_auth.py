import webbrowser

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from brocc_li.utils.api_url import get_api_url
from brocc_li.utils.auth_data import is_logged_in, load_auth_data, save_auth_data
from brocc_li.utils.logger import logger

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthStatusResponse(BaseModel):
    is_logged_in: bool = Field(..., description="Indicates if the user is currently logged in.")
    email: str | None = Field(None, description="The email of the logged-in user, if available.")


class LoginStartResponse(BaseModel):
    auth_url: str = Field(..., description="The URL to open in the browser for authentication.")
    session_id: str = Field(..., description="The session ID to use for polling.")


class LoginPollResponse(BaseModel):
    status: str = Field(..., description="Polling status (e.g., 'pending', 'complete', 'error').")
    email: str | None = Field(None, description="User email if login is complete.")
    message: str | None = Field(None, description="Optional message, e.g., for errors.")


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status():
    """
    Check the current authentication status based on saved credentials.
    """
    auth_data: dict | None = load_auth_data()
    logged_in = is_logged_in(auth_data)
    email = auth_data.get("email") if auth_data and logged_in else None

    return AuthStatusResponse(is_logged_in=logged_in, email=email)


@router.post("/open-dashboard")
async def open_dashboard_link():
    """Constructs the dashboard URL and opens it in the default web browser."""
    base_api_url = get_api_url()
    # Remove trailing '/api' if present
    if base_api_url.endswith("/api"):
        base_url = base_api_url[:-4]
    else:
        base_url = base_api_url

    dashboard_url = f"{base_url}/dashboard"
    logger.debug(f"Opening dashboard URL: {dashboard_url}")
    try:
        webbrowser.open(dashboard_url)
        return {"message": "Dashboard opened successfully."}
    except Exception as e:
        logger.error(f"Failed to open dashboard URL: {e}")
        # Consider returning a proper HTTP error response here
        return {"error": "Failed to open dashboard URL"}


async def _call_main_api(url: str, method: str = "GET") -> httpx.Response:
    """Helper to call the main Brocc API."""
    async with httpx.AsyncClient() as client:
        try:
            if method.upper() == "GET":
                response = await client.get(url, timeout=10)
            else:
                # Add other methods if needed
                raise NotImplementedError(f"HTTP method {method} not implemented")
            response.raise_for_status()  # Raise exception for 4xx/5xx errors
            return response
        except httpx.RequestError as e:
            logger.error(f"Error calling main API {url}: {e}")
            # Re-raise or handle as appropriate for the endpoint
            raise
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Main API returned error for {url}: {e.response.status_code} {e.response.text[:200]}"
            )
            raise


@router.get("/login/start", response_model=LoginStartResponse)
async def start_login():
    """Initiates the login flow by contacting the main API."""
    main_api_url = get_api_url()
    start_url = f"{main_api_url}/auth/cli/start"
    logger.debug(f"Initiating login via: {start_url}")
    try:
        response = await _call_main_api(start_url)
        data = response.json()
        auth_url = data.get("authUrl")
        session_id = data.get("sessionId")
        if not auth_url or not session_id:
            raise Exception("Invalid response from main API /auth/cli/start")

        # --- ADDED BACK: Open browser from backend ---
        logger.debug(f"Opening auth URL in browser: {auth_url}")
        try:
            webbrowser.open(auth_url)
        except Exception as wb_err:
            logger.error(f"Failed to open browser automatically: {wb_err}")
            pass  # Continue execution
        # --- End re-addition ---

        return LoginStartResponse(auth_url=auth_url, session_id=session_id)
    except Exception as e:
        logger.error(f"Login start failed: {e}")
        # Consider returning a proper HTTP error response
        # For now, re-raising might be handled by FastAPI's exception handlers
        raise


@router.get("/login/poll", response_model=LoginPollResponse)
async def poll_login_status(session_id: str):
    """Polls the main API for login completion status using the session ID."""
    main_api_url = get_api_url()
    token_url = f"{main_api_url}/auth/cli/token?sessionId={session_id}"
    logger.debug(f"Polling login status: {token_url}")
    try:
        response = await _call_main_api(token_url)
        data = response.json()

        if data.get("status") == "complete":
            logger.success(
                f"Authentication complete via polling. API key received: {bool(data.get('apiKey'))}"
            )
            auth_data = {
                "accessToken": data["accessToken"],
                "userId": data["userId"],
                "email": data.get("email"),
                "apiKey": data.get("apiKey"),
                "_source": "fastapi-poll",
            }
            save_auth_data(auth_data)  # Save on the server side
            return LoginPollResponse(status="complete", email=auth_data.get("email"), message=None)
        else:
            # Still pending or other status from main API
            logger.debug(f"Polling status: {data.get('status', 'unknown')}")
            return LoginPollResponse(status=data.get("status", "pending"), email=None, message=None)

    except httpx.HTTPStatusError as e:
        # Handle specific errors if needed, e.g., 404 might mean session expired
        logger.warning(f"Polling error: {e.response.status_code}")
        return LoginPollResponse(
            status="error", email=None, message=f"Polling failed: {e.response.status_code}"
        )
    except Exception as e:
        logger.error(f"Polling failed: {e}")
        return LoginPollResponse(status="error", email=None, message=f"Polling failed: {e}")
