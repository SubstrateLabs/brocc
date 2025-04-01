from typing import Tuple, Optional
from playwright.sync_api import Page
import time
from brocc_li.types.extract_feed_config import NavigateOptions
from brocc_li.extract.rate_limit_backoff_s import (
    rate_limit_backoff_s,
    RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD,
)
from brocc_li.extract.extract_markdown import extract_markdown
from brocc_li.extract.adjust_timeout_counter import adjust_timeout_counter
from brocc_li.utils.logger import logger


def extract_navigate_content(
    page: Page, options: NavigateOptions, consecutive_timeouts: int = 0
) -> Tuple[Optional[str], int]:
    """Extract content from a page using the provided selector.

    Returns:
        Tuple containing the extracted content (or None) and the number of consecutive timeouts.
    """
    selector = options.content_selector.strip()

    try:
        # If we've hit consecutive timeouts, implement a cooldown
        if consecutive_timeouts >= RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD:
            cooldown_s = rate_limit_backoff_s(consecutive_timeouts)
            logger.warning(
                f"Rate limit detected! Cooling down for {cooldown_s:.1f} seconds..."
            )
            time.sleep(cooldown_s)

        page.wait_for_selector(selector, timeout=options.content_timeout_ms)
        logger.success(f"Found content with selector: '{selector}'")

        # Extract and convert content
        html_content = extract_markdown(page, selector)
        if html_content:
            return html_content, adjust_timeout_counter(
                consecutive_timeouts, success=True
            )
        else:
            return None, adjust_timeout_counter(consecutive_timeouts, success=False)

    except TimeoutError as e:
        # Increment timeout counter for rate limiting detection
        consecutive_timeouts = adjust_timeout_counter(
            consecutive_timeouts, success=False, timeout_occurred=True
        )
        logger.warning(f"Timeout error with selector '{selector}': {str(e)}")

        # Apply adaptive cooldown based on consecutive timeouts
        cooldown_s = rate_limit_backoff_s(consecutive_timeouts)

        if consecutive_timeouts >= RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD:
            logger.warning(
                f"Multiple timeouts detected! Cooling down for {cooldown_s:.1f} seconds..."
            )
        else:
            logger.warning(
                f"Timeout detected, brief cooldown for {cooldown_s:.1f} seconds..."
            )

        time.sleep(cooldown_s)

        if consecutive_timeouts >= RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD:
            logger.warning(
                f"Detected {consecutive_timeouts} consecutive timeouts, possible rate limiting"
            )
        return None, consecutive_timeouts
    except Exception as e:
        logger.warning(f"Error with selector '{selector}': {str(e)}")
        # For non-timeout errors, still be a bit cautious if we've had timeouts before
        return None, adjust_timeout_counter(consecutive_timeouts, success=False)
