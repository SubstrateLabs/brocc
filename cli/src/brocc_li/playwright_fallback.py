"""
Playwright fallback module for getting HTML from pages when faster CDP method fails.
Opens a new tab using Playwright, navigates to the URL, and gets the HTML content.
"""

from functools import lru_cache

import requests
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from brocc_li.utils.chrome import REMOTE_DEBUG_PORT, is_chrome_debug_port_active
from brocc_li.utils.logger import logger


@lru_cache(maxsize=1)
def get_playwright():
    """Get or create a Playwright instance (cached)."""
    logger.debug("Starting Playwright instance")
    return sync_playwright().start()


class PlaywrightFallback:
    """Fallback helper for getting HTML content when CDP methods fail."""

    def __init__(self):
        """Initialize the Playwright fallback helper."""
        self._playwright = None
        self._browser = None
        self._debug_port = REMOTE_DEBUG_PORT

    def _ensure_browser(self):
        """Ensure we have a connection to the existing Chrome instance."""
        if self._browser is None:
            try:
                # Check if Chrome is running with debug port
                if not is_chrome_debug_port_active(self._debug_port):
                    logger.error(
                        f"Chrome debug port {self._debug_port} not active. Please start Chrome with --remote-debugging-port={self._debug_port}"
                    )
                    return

                # Connect to the running Chrome instance
                self._playwright = get_playwright()
                self._browser = self._playwright.chromium.connect_over_cdp(
                    f"http://localhost:{self._debug_port}"
                )

                logger.debug("Successfully connected to local Chrome instance for fallback")
            except Exception as e:
                logger.error(f"Failed to connect to Chrome browser: {e}")
                self._browser = None

    def get_html_from_url(self, url: str) -> str:
        """
        Get HTML content from a URL using Playwright.

        Creates a temporary tab in an existing Chrome window,
        gets the content, and immediately closes the tab.

        Args:
            url: The URL to get HTML from

        Returns:
            HTML content as string, empty string if failed
        """
        if not url or not url.startswith(("http://", "https://")):
            logger.error(f"Invalid URL for Playwright fallback: {url}")
            return ""

        self._ensure_browser()
        if not self._browser:
            return ""

        page = None
        try:
            # First check if there are any existing browser contexts (windows)
            contexts = self._browser.contexts
            if not contexts:
                logger.warning(
                    "No existing browser windows found. Fallback may create a new window."
                )
                # Create a context since none exists
                context = self._browser.new_context()
                page = context.new_page()
            else:
                # Use the first existing context/window
                context = contexts[0]
                # Create a new tab in the existing window
                page = context.new_page()
                logger.debug("Created new tab in existing Chrome window")

            broccoli_marker_script = """
            (function() {
                function createBroccoliMarker() {
                    // Remove any existing markers first
                    const existingMarkers = document.querySelectorAll('.brocc-li-marker');
                    existingMarkers.forEach(marker => marker.remove());
                    
                    // Create top banner
                    const banner = document.createElement('div');
                    banner.className = 'brocc-li-marker';
                    banner.textContent = '🥦 READING... (Page will close automatically in a moment)';
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
                        border-bottom: 2px solid #036303;
                        box-shadow: 0 1px 5px rgba(0,0,0,0.3);
                    `;
                    
                    // Add banner to page
                    document.body.appendChild(banner);
                }
                
                // Create/restore marker when needed
                function ensureMarkerExists() {
                    // Check if our marker exists and is visible
                    const markers = document.querySelectorAll('.brocc-li-marker');
                    if (markers.length < 1) {
                        createBroccoliMarker();
                    }
                }
                
                // Apply immediately if document is ready
                if (document.body) {
                    createBroccoliMarker();
                } else {
                    // Wait for DOM to be ready
                    document.addEventListener('DOMContentLoaded', createBroccoliMarker);
                }
                
                // Set up continuous monitoring to ensure our marker stays visible
                const observer = new MutationObserver(function() {
                    ensureMarkerExists();
                });
                
                // Start observing once body exists
                if (document.body) {
                    observer.observe(document.body, { 
                        childList: true, 
                        subtree: true 
                    });
                } else {
                    // Set up observer once body is available
                    document.addEventListener('DOMContentLoaded', function() {
                        observer.observe(document.body, { 
                            childList: true, 
                            subtree: true 
                        });
                    });
                }
                
                // Check periodically to ensure our marker stays visible
                setInterval(ensureMarkerExists, 500);
            })();
            """

            # Add this script to run on every navigation and in every frame
            page.add_init_script(broccoli_marker_script)

            # 'load' = wait for the load event to be fired (more reliable than networkidle)
            logger.debug(f"Playwright: Navigating to {url}")
            try:
                page.goto(url, wait_until="load", timeout=10000)
            except PlaywrightError as e:
                # Even if navigation "fails", we might still have loaded content
                logger.warning(f"Navigation had issues: {e}")

                # Give the page a moment to settle
                try:
                    page.wait_for_timeout(1000)
                except Exception as e:
                    logger.debug(f"Timeout wait interrupted: {e}")
                    pass

            # Try to get HTML content even if navigation had issues
            try:
                # Wait a bit longer to ensure our marker script has run
                page.wait_for_timeout(500)

                # Get the page content
                html = page.content()
                if html and len(html) > 500:  # Ensure we have meaningful content
                    logger.debug(f"Successfully retrieved HTML via Playwright ({len(html)} chars)")
                    return html
                else:
                    logger.warning("Playwright returned insufficient HTML content")
            except Exception as e:
                logger.warning(f"Error getting page content: {e}")

            return ""

        except PlaywrightError as e:
            logger.error(f"Playwright error with {url}: {e}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error with Playwright: {e}")
            return ""
        finally:
            # Make sure to clean up the temporary tab/page
            if page:
                try:
                    page.close()
                    logger.debug("Closed temporary tab")
                except Exception as e:
                    logger.debug(f"Error closing page: {e}")

    def get_html_from_tab(self, tab_id: str, debug_port: int = REMOTE_DEBUG_PORT) -> str:
        """
        Get HTML content from an existing Chrome tab using Playwright.

        This is a fallback method for when CDP methods fail.
        It creates a temporary tab, gets the content, and immediately closes it.

        Args:
            tab_id: The Chrome tab ID
            debug_port: Chrome debug port

        Returns:
            HTML content as string, empty string if failed
        """
        try:
            # Get the tab details to find its URL
            response = requests.get(f"http://localhost:{debug_port}/json/list", timeout=1)
            if response.status_code != 200:
                logger.error(f"Failed to get tab list: HTTP {response.status_code}")
                return ""

            # Find the tab with matching ID
            tabs = response.json()
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

            # Get HTML using a temporary tab in the main window
            return self.get_html_from_url(url)

        except Exception as e:
            logger.error(f"Error getting tab info for Playwright fallback: {e}")
            return ""

    def cleanup(self):
        """Clean up browser connection."""
        try:
            if self._browser:
                self._browser.close()
                self._browser = None
        except Exception as e:
            logger.error(f"Error cleaning up Playwright resources: {e}")

    def __del__(self):
        """Ensure resources are cleaned up when object is garbage collected."""
        self.cleanup()


# Singleton instance
playwright_fallback = PlaywrightFallback()
