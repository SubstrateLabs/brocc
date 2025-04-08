import asyncio
import time
import webbrowser

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from brocc_li.chrome_manager import ChromeManager
from brocc_li.chrome_tabs import ChromeTabs
from brocc_li.utils.chrome import launch_chrome, quit_chrome
from brocc_li.utils.logger import logger

router = APIRouter(prefix="/chrome", tags=["chrome"])

# ChromeManager singleton - enable auto-connect
chrome_manager = ChromeManager(auto_connect=True)


# Helper function to check if Chrome is connected
def is_chrome_connected():
    """Check if Chrome is connected and usable"""
    return chrome_manager.connected


# Try initial auto-connect on server start
async def try_initial_connect(quiet=True):
    """Try to auto-connect to Chrome on server start asynchronously"""
    try:
        # Just call the async refresh_state method directly
        state = await chrome_manager.refresh_state()

        if state.has_debug_port:
            # Connect with quiet parameter
            is_connected = await chrome_manager.test_connection(quiet=quiet)
            if is_connected:
                if not quiet:
                    logger.debug("Successfully auto-connected to Chrome on server start")
                return True
    except Exception as e:
        if not quiet:
            logger.error(f"Error during initial auto-connect: {e}")

    return False


# Convert the sync wrapper to async
def try_initial_connect_sync(quiet=True):
    """Synchronous wrapper for try_initial_connect for backward compatibility"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(try_initial_connect(quiet=quiet))
    finally:
        loop.close()


# --- Chrome Manager API ---
@router.get("/status")
async def chrome_status():
    """Get the current status of Chrome connection"""
    # Refresh the state which might auto-connect if configured
    try:
        await chrome_manager.refresh_state()
    except Exception as e:
        logger.error(f"Error refreshing Chrome state: {e}")

    # Get status code - this now needs to be awaited
    status_code = await chrome_manager.status_code()

    return {
        "status_code": status_code.value,  # Return the string value of the enum
        "timestamp": time.time(),
    }


@router.post("/launch")
async def chrome_launch_endpoint(
    request: Request, background_tasks: BackgroundTasks, force_relaunch: bool = False
):
    """
    Launch Chrome with a debug port or connect to an existing instance.

    If force_relaunch is True, will quit existing Chrome instances and start fresh.
    Otherwise, it will try to connect to an existing Chrome if possible.
    """
    # Try to extract force_relaunch from JSON body if it wasn't in query params
    if not force_relaunch:
        try:
            body = await request.json()
            if isinstance(body, dict) and "force_relaunch" in body:
                force_relaunch = bool(body["force_relaunch"])
        except Exception:
            # No valid JSON body or other error, stick with default
            pass

    # For regular (non-forced) launch, check if already connected
    if not force_relaunch:
        # Check if already connected directly using the property
        try:
            chrome_connected = chrome_manager.connected
            if chrome_connected:
                return {"status": "already_connected", "message": "Already connected to Chrome"}
        except Exception as e:
            logger.debug(f"Error checking Chrome connection: {e}")

    # Use a helper function to run the sync operation safely from an async context
    async def run_in_thread():
        try:
            await _launch_chrome_in_thread(force_relaunch)
        except Exception as e:
            logger.error(f"Error running Chrome launch in thread: {e}")

    # Run the launch operation in the background
    background_tasks.add_task(run_in_thread)

    return {
        "status": "launching",
        "message": f"{'Relaunching' if force_relaunch else 'Launching'} Chrome in background",
    }


async def _launch_chrome_in_thread(force_relaunch: bool = False):
    """Launch or relaunch Chrome in a background thread"""
    try:
        logger.debug(f"Starting Chrome {'relaunch' if force_relaunch else 'launch'} process")

        # Get the current state - use await
        state = await chrome_manager.refresh_state()
        logger.debug(
            f"Chrome state: running={state.is_running}, has_debug_port={state.has_debug_port}"
        )

        # If we're forcing a relaunch or Chrome is running without debug port
        if force_relaunch or (state.is_running and not state.has_debug_port):
            logger.debug("Quitting existing Chrome instances")

            # Quit all Chrome instances directly
            # Now directly await the async function
            quit_success = await quit_chrome()
            if not quit_success:
                logger.error("Failed to quit existing Chrome instances")
                return

            logger.debug("Successfully quit existing Chrome instances")

            # Chrome needs to be launched with debug port
            needs_launch = True
        else:
            # If Chrome is not running, we need to launch it
            needs_launch = not state.is_running
            logger.debug(f"Chrome needs launch: {needs_launch}")

        # Launch Chrome if needed
        if needs_launch:
            logger.debug("Launching Chrome with debug port")
            # Launch Chrome with debug port
            # Now directly await the async function
            launch_success = await launch_chrome()
            if not launch_success:
                logger.error("Failed to launch Chrome")
                return

            # Give Chrome a moment to initialize - longer time for relaunch
            wait_time = 3 if force_relaunch else 2
            logger.debug(f"Waiting {wait_time}s for Chrome to initialize")
            await asyncio.sleep(wait_time)  # Use asyncio.sleep instead of time.sleep
        else:
            logger.debug("Chrome already running with debug port, skipping launch")

        # Now connect to Chrome using the async method
        logger.debug("Attempting to connect to Chrome")
        try:
            connected = await chrome_manager.test_connection(quiet=True)
            if connected:
                # Use chrome_manager's method to get version
                chrome_version = await chrome_manager._get_chrome_version()
                logger.debug(f"Successfully connected to Chrome {chrome_version}")
            else:
                logger.error("Failed to connect to Chrome")
        except Exception as e:
            logger.error(f"Error connecting to Chrome: {e}")
    except Exception as e:
        logger.error(f"Error in Chrome launch thread: {e}")
        # Add stack trace for better debugging
        import traceback

        logger.error(f"Stack trace: {traceback.format_exc()}")


@router.post("/startup-faq")
async def chrome_startup_faq():
    """Open the Chrome startup FAQ page in the default web browser"""
    try:
        webbrowser.open("https://brocc.li/faq#chrome-startup")
        return {"status": "success", "message": "Opened Chrome startup FAQ in browser"}
    except Exception as e:
        logger.error(f"Error opening Chrome startup FAQ: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error opening Chrome startup FAQ: {str(e)}"
        ) from e


@router.get("/tabs")
async def get_chrome_tabs(include_html: bool = False):
    """
    Get all open Chrome tabs with optional HTML content.

    Args:
        include_html: Whether to include HTML content for each tab
    """
    # Check if Chrome is connected
    if not chrome_manager.connected:
        try:
            # Try to connect using the async method
            connected = await chrome_manager.test_connection(quiet=True)
            if not connected:
                raise HTTPException(
                    status_code=503, detail="Chrome is not connected. Try /chrome/launch first."
                )
        except Exception as e:
            logger.error(f"Error connecting to Chrome: {e}")
            raise HTTPException(status_code=500, detail="Error connecting to Chrome") from e

    # Using ChromeTabs to get tab information
    tabs_manager = ChromeTabs(chrome_manager)

    if include_html:
        try:
            # Get all tabs with HTML content using the async method
            tabs_with_html = await tabs_manager.get_all_tabs_with_html()
            return tabs_with_html
        except Exception as e:
            logger.error(f"Error getting tabs with HTML: {e}")
            raise HTTPException(
                status_code=500, detail=f"Error getting tabs with HTML: {str(e)}"
            ) from e
    else:
        try:
            # Get tabs without HTML content using the async method
            tabs = await chrome_manager.get_all_tabs()
            # Filter for HTTP/HTTPS tabs
            filtered_tabs = [
                tab for tab in tabs if tab.get("url", "").startswith(("http://", "https://"))
            ]
            return filtered_tabs
        except Exception as e:
            logger.error(f"Error getting tabs: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting tabs: {str(e)}") from e
