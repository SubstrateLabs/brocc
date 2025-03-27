from brocc_li.extract.is_valid_page import is_valid_page
from brocc_li.types.extract_feed_config import ExtractFeedConfig
from rich.console import Console
from playwright.sync_api import Page, TimeoutError
from typing import Optional
from brocc_li.utils.random_delay import random_delay_with_jitter


console = Console()

# Factor to add random variation to delays (0.3 = ±30% variation)
DEFAULT_JITTER_FACTOR = 0.3
# Minimum delay between retry attempts when navigation fails
NAVIGATE_RETRY_DELAY_MIN_MS = 1000
# Maximum delay between retry attempts when navigation fails
NAVIGATE_RETRY_DELAY_MAX_MS = 2000


def wait_for_navigation(
    page: Page, config: ExtractFeedConfig, wait_condition: Optional[str] = None
) -> bool:
    """Wait for navigation to complete with proper error handling.

    Args:
        page: The page being navigated
        config: Feed configuration
        wait_condition: Override the wait condition, otherwise use config settings

    Returns:
        True if navigation completed successfully, False otherwise
    """
    try:
        # Determine wait condition based on config
        if wait_condition in ("domcontentloaded", "load", "networkidle"):
            condition = wait_condition
        elif config.navigate_options and config.navigate_options.wait_networkidle:
            condition = "networkidle"
        else:
            condition = "domcontentloaded"

        # Set timeout based on whether this is networkidle or not
        timeout = config.network_idle_timeout_ms if condition == "networkidle" else 5000

        # Wait for the condition
        page.wait_for_load_state(condition, timeout=timeout)

        # Add a brief delay to ensure page is ready
        random_delay_with_jitter(
            NAVIGATE_RETRY_DELAY_MIN_MS,
            NAVIGATE_RETRY_DELAY_MAX_MS,
            DEFAULT_JITTER_FACTOR,
        )

        # Verify page is in a valid state
        return is_valid_page(page)

    except TimeoutError:
        # Fall back to domcontentloaded if networkidle times out
        if condition == "networkidle":
            try:
                console.print(
                    "[yellow]Networkidle timed out, falling back to domcontentloaded[/yellow]"
                )
                page.wait_for_load_state("domcontentloaded", timeout=2000)
                return is_valid_page(page)
            except Exception:
                return False
        return False
    except Exception as e:
        console.print(f"[yellow]Navigation wait error: {str(e)}[/yellow]")
        return False
