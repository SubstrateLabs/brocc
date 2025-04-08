"""
Playwright fallback module for getting HTML from pages when faster CDP method fails.
Opens a new tab using Playwright, navigates to the URL, and gets the HTML content.
This module uses async Playwright API for better thread safety.
"""

import asyncio
import time
from collections import deque
from typing import Deque, Tuple

import aiohttp
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from brocc_li.utils.chrome import REMOTE_DEBUG_PORT, is_chrome_debug_port_active
from brocc_li.utils.logger import logger

# Banner text shown in the browser when using Playwright fallback
BANNER_TEXT = "🥦 READING... (Page will close automatically in a moment)"

# Estimated time per tab in seconds (average) - initial default value
ESTIMATED_SECONDS_PER_TAB = 8  # Playwright navigation takes ~8 seconds per tab on average

# Cache the playwright instance
_playwright_instance = None

# Track processing times to calculate a running average (last N tabs)
_tab_processing_times: Deque[Tuple[float, float]] = deque(
    maxlen=10
)  # Store (timestamp, duration) pairs


def get_current_time_estimate() -> float:
    """
    Get the current estimated seconds per tab based on recent processing history.

    Returns:
        float: Estimated seconds per tab (defaults to ESTIMATED_SECONDS_PER_TAB if no data)
    """
    if not _tab_processing_times:
        return ESTIMATED_SECONDS_PER_TAB

    # Calculate average from recent times
    total_time = sum(duration for _, duration in _tab_processing_times)
    return total_time / len(_tab_processing_times)


def add_tab_processing_time(duration: float) -> None:
    """
    Add a tab processing time measurement to our running average.

    Args:
        duration: The time in seconds it took to process the tab
    """
    current_time = time.time()
    _tab_processing_times.append((current_time, duration))
    logger.debug(
        f"Tab processed in {duration:.2f}s. New average: {get_current_time_estimate():.2f}s"
    )


async def get_playwright():
    """Get or create a Playwright instance (cached)."""
    global _playwright_instance
    if _playwright_instance is None:
        logger.debug("Starting async Playwright instance")
        _playwright_instance = await async_playwright().start()
    return _playwright_instance


class PlaywrightFallback:
    """Fallback helper for getting HTML content when CDP methods fail."""

    def __init__(self):
        """Initialize the Playwright fallback helper."""
        self._browser = None
        self._debug_port = REMOTE_DEBUG_PORT
        self._lock = asyncio.Lock()  # Add a lock to prevent concurrent browser connections

    async def _ensure_browser(self):
        """Ensure we have a connection to the existing Chrome instance."""
        async with self._lock:  # Use a lock to prevent multiple concurrent connections
            if self._browser is None:
                try:
                    # Check if Chrome is running with debug port - now directly use the async function
                    if not await is_chrome_debug_port_active(self._debug_port):
                        logger.error(
                            f"Chrome debug port {self._debug_port} not active. Please start Chrome with --remote-debugging-port={self._debug_port}"
                        )
                        return

                    # Connect to the running Chrome instance
                    playwright = await get_playwright()
                    self._browser = await playwright.chromium.connect_over_cdp(
                        f"http://localhost:{self._debug_port}"
                    )

                    logger.debug("Successfully connected to local Chrome instance for fallback")
                except Exception as e:
                    logger.error(f"Failed to connect to Chrome browser: {e}")
                    self._browser = None

    async def get_html_from_url(self, url: str, current_tab: int = 0, total_tabs: int = 0) -> str:
        """
        Get HTML content from a URL using Playwright.

        Creates a temporary tab in an existing Chrome window,
        gets the content, and immediately closes the tab.

        Args:
            url: The URL to get HTML from
            current_tab: Current tab number being processed (1-indexed)
            total_tabs: Total number of tabs to process

        Returns:
            HTML content as string, empty string if failed
        """
        if not url or not url.startswith(("http://", "https://")):
            logger.error(f"Invalid URL for Playwright fallback: {url}")
            return ""

        await self._ensure_browser()
        if not self._browser:
            return ""

        page = None
        html = ""
        start_time = time.time()  # Start timing

        try:
            # First check if there are any existing browser contexts (windows)
            contexts = self._browser.contexts
            if not contexts:
                logger.warning(
                    "No existing browser windows found. Fallback may create a new window."
                )
                # Create a context since none exists
                context = await self._browser.new_context()
                page = await context.new_page()
            else:
                # Use the first existing context/window
                context = contexts[0]
                # Create a new tab in the existing window
                page = await context.new_page()
                logger.debug("Created new tab in existing Chrome window")

            # Get current time estimate based on the running average
            current_estimate = get_current_time_estimate()

            # Calculate banner text with progress if available
            banner_text = BANNER_TEXT
            if current_tab > 0 and total_tabs > 0:
                # Calculate remaining tabs and time estimate
                remaining_tabs = total_tabs - current_tab + 1  # Include current tab
                time_estimate = remaining_tabs * current_estimate

                # Check if we're at or above the cap
                if time_estimate >= 60:
                    # Use "Wait a minute..." instead of the time
                    time_display = "About a minute remaining"
                else:
                    # For shorter times, display seconds
                    time_display = f"{int(time_estimate)}s remaining"

                banner_text = f"🥦 Reading {current_tab}/{total_tabs} pages... {time_display}"

            broccoli_marker_script = f"""
            (function() {{
                function createBroccoliMarker() {{
                    // Remove any existing markers first
                    const existingMarkers = document.querySelectorAll('.brocc-li-marker');
                    existingMarkers.forEach(marker => marker.remove());
                    
                    // Create top banner
                    const banner = document.createElement('div');
                    banner.className = 'brocc-li-marker';
                    banner.textContent = '{banner_text}';
                    banner.style.cssText = `
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        background-color: rgba(30, 150, 0, 0.95);
                        color: white;
                        text-align: center;
                        font-size: 14px;
                        font-weight: bold;
                        padding: 10px;
                        line-height: 24px;
                        z-index: 2147483647;
                        font-family: system-ui, sans-serif;
                    `;
                    
                    // Add banner to page
                    document.body.appendChild(banner);
                }}
                
                // Create/restore marker when needed
                function ensureMarkerExists() {{
                    // Check if our marker exists and is visible
                    const markers = document.querySelectorAll('.brocc-li-marker');
                    if (markers.length < 1) {{
                        createBroccoliMarker();
                    }}
                }}
                
                // Apply immediately if document is ready
                if (document.body) {{
                    createBroccoliMarker();
                }} else {{
                    // Wait for DOM to be ready
                    document.addEventListener('DOMContentLoaded', createBroccoliMarker);
                }}
                
                // Set up continuous monitoring to ensure our marker stays visible
                const observer = new MutationObserver(function() {{
                    ensureMarkerExists();
                }});
                
                // Start observing once body exists
                if (document.body) {{
                    observer.observe(document.body, {{ 
                        childList: true, 
                        subtree: true 
                    }});
                }} else {{
                    // Set up observer once body is available
                    document.addEventListener('DOMContentLoaded', function() {{
                        observer.observe(document.body, {{ 
                            childList: true, 
                            subtree: true 
                        }});
                    }});
                }}
                
                // Check periodically to ensure our marker stays visible
                setInterval(ensureMarkerExists, 500);
            }})();
            """

            # Add this script to run on every navigation and in every frame
            await page.add_init_script(broccoli_marker_script)

            # 'load' = wait for the load event to be fired (more reliable than networkidle)
            logger.debug(f"Playwright: Navigating to {url}")
            try:
                await page.goto(url, wait_until="load", timeout=10000)
            except PlaywrightError as e:
                # Even if navigation "fails", we might still have loaded content
                logger.warning(f"Navigation had issues: {e}")

                # Give the page a moment to settle
                try:
                    await page.wait_for_timeout(1000)
                except Exception as e:
                    logger.debug(f"Timeout wait interrupted: {e}")
                    pass

            # Try to get HTML content even if navigation had issues
            try:
                # Wait a bit longer to ensure our marker script has run
                await page.wait_for_timeout(500)

                # Get the page content
                html = await page.content()
                if html and len(html) > 500:  # Ensure we have meaningful content
                    logger.debug(f"Successfully retrieved HTML via Playwright ({len(html)} chars)")
                else:
                    logger.warning("Playwright returned insufficient HTML content")
            except Exception as e:
                logger.warning(f"Error getting page content: {e}")

            return html

        except PlaywrightError as e:
            logger.error(f"Playwright error with {url}: {e}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error with Playwright: {e}")
            return ""
        finally:
            # Calculate processing time and update the running average if content was retrieved
            end_time = time.time()
            duration = end_time - start_time

            if html:  # Only track successful extractions
                # Add this measurement to our running average
                add_tab_processing_time(duration)
                logger.debug(f"Tab processing took {duration:.2f}s")

            # Make sure to clean up the temporary tab/page
            if page:
                try:
                    await page.close()
                    logger.debug("Closed temporary tab")
                except Exception as e:
                    logger.debug(f"Error closing page: {e}")

    async def get_html_from_tab(
        self,
        tab_id: str,
        current_tab: int = 0,
        total_tabs: int = 0,
        debug_port: int = REMOTE_DEBUG_PORT,
    ) -> str:
        """
        Get HTML content from an existing Chrome tab using Playwright.

        This is a fallback method for when CDP methods fail.
        It creates a temporary tab, gets the content, and immediately closes it.

        Args:
            tab_id: The Chrome tab ID
            current_tab: Current tab number being processed (1-indexed)
            total_tabs: Total number of tabs to process
            debug_port: Chrome debug port

        Returns:
            HTML content as string, empty string if failed
        """
        try:
            # Get the tab details to find its URL using aiohttp
            timeout = aiohttp.ClientTimeout(total=1.0)  # 1 second timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"http://localhost:{debug_port}/json/list") as response:
                    if response.status != 200:
                        logger.error(f"Failed to get tab list: HTTP {response.status}")
                        return ""

                    # Parse the JSON response
                    tabs = await response.json()

            # Find the tab with matching ID
            tab = next((t for t in tabs if t.get("id") == tab_id), None)

            if not tab:
                logger.error(f"Tab with ID {tab_id} not found")
                return ""

            # Get the tab URL
            url = tab.get("url", "")
            title = tab.get("title", "Untitled")

            if not url or url == "about:blank":
                logger.warning(f"Tab {tab_id} has blank or empty URL")
                return ""

            logger.debug(f"Using Playwright fallback for tab '{title}' ({tab_id}) at {url}")

            # Get HTML using a temporary tab in the main window, passing progress info
            return await self.get_html_from_url(url, current_tab, total_tabs)

        except Exception as e:
            logger.error(f"Error getting tab info for Playwright fallback: {e}")
            return ""

    async def cleanup(self):
        """Clean up browser connection."""
        try:
            if self._browser:
                await self._browser.close()
                self._browser = None
        except Exception as e:
            logger.error(f"Error cleaning up Playwright resources: {e}")

    def __del__(self):
        """Ensure resources are cleaned up when object is garbage collected."""
        # During interpreter shutdown, we can't do async cleanup
        # Just log a warning and let the process exit
        try:
            import sys

            if sys.meta_path is None:
                logger.debug("Skipping Playwright cleanup during interpreter shutdown")
                return

            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.cleanup())
            else:
                # If no loop is running, we can't do async cleanup here
                logger.warning(
                    "No event loop running, can't clean up Playwright resources properly"
                )
        except (RuntimeError, ImportError):
            # No event loop in this thread or during shutdown
            pass


# Singleton instance
playwright_fallback = PlaywrightFallback()
