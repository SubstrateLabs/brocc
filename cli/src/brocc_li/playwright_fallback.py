"""
Playwright fallback module for getting HTML from pages when CDP fails.

This module provides a fallback method to get HTML content from a URL when
Chrome DevTools Protocol methods fail, especially for sites with anti-automation measures.
"""

from functools import lru_cache

import requests
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

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
        self._default_context = None
        self._context_count = 0
        self._max_contexts = 5  # Maximum number of contexts before we recycle

    def _ensure_browser(self):
        """Ensure we have a browser instance initialized."""
        if self._browser is None:
            try:
                self._playwright = get_playwright()
                # Use a persistent context with stealth mode to avoid detection
                self._browser = self._playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-features=IsolateOrigins,site-per-process",
                    ],
                )
                logger.debug("Successfully initialized Playwright browser for fallback")
                # Reset the context counter
                self._context_count = 0
            except Exception as e:
                logger.error(f"Failed to initialize Playwright browser: {e}")
                self._browser = None

    def get_html_from_url(self, url: str) -> str:
        """
        Get HTML content from a URL using Playwright.

        This method uses Playwright's anti-detection capabilities to load a page
        even when CDP methods fail, especially for sites with anti-automation measures.

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

        # Check if we need to recycle contexts to prevent memory leaks
        self._context_count += 1
        if self._context_count > self._max_contexts:
            logger.debug(f"Recycling Playwright contexts after {self._context_count} uses")
            self.cleanup_contexts()
            self._context_count = 1

        page = None
        context = None
        try:
            # Create context with anti-detection settings
            context = self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                bypass_csp=True,
            )

            # Add stealth mode scripts
            context.add_init_script("""
                // Override automation properties
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                
                // Hide automation-related properties
                if (window.chrome) {
                    // Make navigator.chrome.runtime undefined
                    Object.defineProperty(window, 'chrome', {
                        get: () => {
                            return {
                                runtime: undefined
                            };
                        }
                    });
                }
            """)

            # Create a new page
            page = context.new_page()

            # Navigate to the URL
            logger.debug(f"Playwright: Navigating to {url}")
            page.goto(url, wait_until="networkidle", timeout=10000)

            # Get the HTML content
            html = page.content()

            if html:
                logger.debug(f"Successfully retrieved HTML via Playwright ({len(html)} chars)")
                return html
            else:
                logger.warning("Playwright returned empty HTML content")
                return ""

        except PlaywrightError as e:
            logger.error(f"Playwright error navigating to {url}: {e}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error with Playwright: {e}")
            return ""
        finally:
            # Clean up resources
            if page:
                try:
                    page.close()
                except Exception as e:
                    logger.debug(f"Error closing page: {e}")
            if context:
                try:
                    context.close()
                except Exception as e:
                    logger.debug(f"Error closing context: {e}")

    def cleanup_contexts(self):
        """Clean up browser contexts to prevent memory leaks."""
        if self._browser:
            try:
                # Close all browser contexts except the default one
                for context in self._browser.contexts:
                    try:
                        context.close()
                    except Exception as e:
                        logger.debug(f"Error closing context: {e}")
            except Exception as e:
                logger.error(f"Error cleaning up browser contexts: {e}")

    def cleanup(self):
        """Clean up all resources including the browser."""
        self.cleanup_contexts()
        try:
            if self._browser:
                self._browser.close()
                self._browser = None
        except Exception as e:
            logger.error(f"Error cleaning up Playwright resources: {e}")

    def __del__(self):
        """Ensure resources are cleaned up when object is garbage collected."""
        self.cleanup()

    def get_html_from_tab(self, tab_id: str, debug_port: int = 9222) -> str:
        """
        Get HTML content by creating a new tab with the same URL as the original tab.

        This is a fallback method for when CDP methods fail.

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

            # Use the URL to create a new tab and get content
            return self.get_html_from_url(url)

        except Exception as e:
            logger.error(f"Error getting tab info for Playwright fallback: {e}")
            return ""


# Singleton instance
playwright_fallback = PlaywrightFallback()
