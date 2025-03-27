from typing import Tuple, Optional
from playwright.sync_api import Page
from rich.console import Console
import time
from brocc_li.types.extract_feed_config import NavigateOptions
from brocc_li.extract.rate_limit_backoff_s import (
    rate_limit_backoff_s,
    RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD,
)
from brocc_li.extract.extract_markdown import extract_markdown
from brocc_li.extract.adjust_timeout_counter import adjust_timeout_counter

console = Console()


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
            console.print(
                f"[yellow]Rate limit detected! Cooling down for {cooldown_s:.1f} seconds...[/yellow]"
            )
            time.sleep(cooldown_s)

        page.wait_for_selector(selector, timeout=options.content_timeout_ms)
        console.print(f"[green]Found content with selector: '{selector}'[/green]")

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
        console.print(
            f"[yellow]Timeout error with selector '{selector}': {str(e)}[/yellow]"
        )

        # Apply adaptive cooldown based on consecutive timeouts
        cooldown_s = rate_limit_backoff_s(consecutive_timeouts)

        if consecutive_timeouts >= RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD:
            console.print(
                f"[yellow]Multiple timeouts detected! Cooling down for {cooldown_s:.1f} seconds...[/yellow]"
            )
        else:
            console.print(
                f"[yellow]Timeout detected, brief cooldown for {cooldown_s:.1f} seconds...[/yellow]"
            )

        time.sleep(cooldown_s)

        if consecutive_timeouts >= RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD:
            console.print(
                f"[yellow]Detected {consecutive_timeouts} consecutive timeouts, possible rate limiting[/yellow]"
            )
        return None, consecutive_timeouts
    except Exception as e:
        console.print(f"[yellow]Error with selector '{selector}': {str(e)}[/yellow]")
        # For non-timeout errors, still be a bit cautious if we've had timeouts before
        return None, adjust_timeout_counter(consecutive_timeouts, success=False)
