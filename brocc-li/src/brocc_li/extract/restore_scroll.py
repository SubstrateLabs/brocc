from playwright.sync_api import Page
from brocc_li.utils.logger import logger
import time

# Threshold for considering scroll position "close enough" to target (in pixels)
SCROLL_POSITION_THRESHOLD = 500


def restore_scroll_position(
    page: Page, target_position: int, max_attempts: int = 3
) -> None:
    """Restore scroll position with verification and multiple fallback strategies.

    Implements a robust approach to scroll position restoration, with multiple
    fallback strategies if the initial attempt fails:
    1. Standard scrollTo
    2. Smooth scrolling
    3. Step-by-step scrolling
    4. Bottom-then-adjust approach

    Args:
        page: The page to scroll
        target_position: Target scroll position in pixels
        max_attempts: Maximum number of retry attempts
    """
    if target_position <= 0:
        return  # No need to restore if target is at the top

    try:
        # First attempt: standard scrollTo
        page.evaluate(f"window.scrollTo(0, {target_position})")
        logger.debug(f"Attempted to restore scroll position: {target_position}px")
        time.sleep(0.3)  # Brief delay for scroll to take effect

        # Verify if scroll position was actually restored
        current_position = page.evaluate("window.scrollY")

        if (
            abs(current_position - target_position) < SCROLL_POSITION_THRESHOLD
        ):  # Allow small differences
            logger.success(f"Verified scroll position restored: {current_position}px")
            return

        # If scroll position wasn't restored correctly, try alternative approaches
        logger.warning(
            f"Scroll position not restored correctly. Got {current_position}px, expected ~{target_position}px"
        )

        for attempt in range(max_attempts):
            if attempt == 0:
                # Try smooth scrolling
                logger.debug("Trying smooth scroll restoration...")
                page.evaluate(f"""
                    window.scrollTo({{
                        top: {target_position},
                        left: 0,
                        behavior: 'smooth'
                    }})
                """)
            elif attempt == 1:
                # Try scrolling in steps
                logger.debug("Trying step-by-step scroll restoration...")
                step_size = target_position / 4
                for step in range(1, 5):
                    page.evaluate(f"window.scrollTo(0, {int(step_size * step)})")
                    time.sleep(0.1)
            else:
                # Last resort: scroll to bottom then partially back up
                logger.debug("Force-scrolling to bottom of page then adjusting...")
                # First scroll all the way to bottom
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(0.3)

                # If target is not at the very bottom, adjust up slightly
                if target_position < page.evaluate("document.body.scrollHeight"):
                    # Scroll back up 20% from the bottom if needed
                    page.evaluate(
                        "window.scrollTo(0, document.body.scrollHeight * 0.8)"
                    )

            time.sleep(0.3)  # Wait for scroll to take effect
            current_position = page.evaluate("window.scrollY")

            if abs(current_position - target_position) < SCROLL_POSITION_THRESHOLD:
                logger.success(
                    f"Scroll position restored on attempt {attempt + 1}: {current_position}px"
                )
                return

        logger.warning(
            "Could not precisely restore scroll position after multiple attempts"
        )
        # As a last resort, just make sure we're not at the top of the page
        if current_position < 500:
            logger.warning("Emergency scroll to middle/bottom of page")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.8)")
    except Exception as e:
        logger.error(f"Error restoring scroll position: {str(e)}")
        # Make a final best-effort attempt if there was an error
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)")
        except Exception as e:
            logger.error(f"Error in final scroll attempt: {str(e)}")


def get_current_scroll_position(page: Page) -> int:
    """Get the current vertical scroll position.

    Args:
        page: The page to get scroll position from

    Returns:
        Current scroll position in pixels
    """
    try:
        return page.evaluate("window.scrollY")
    except Exception as e:
        logger.error(f"Error getting scroll position: {str(e)}")
        return 0


def scroll_to_bottom(page: Page, aggressive: bool = False) -> None:
    """Scroll to the bottom of the page.

    Args:
        page: The page to scroll
        aggressive: Whether to use a more aggressive scroll (2x height)
    """
    try:
        if aggressive:
            # Use a more aggressive scroll by multiplying by 2
            page.evaluate(
                "window.scrollTo(0, document.documentElement.scrollHeight * 2)"
            )
        else:
            page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    except Exception as e:
        logger.error(f"Error scrolling to bottom: {str(e)}")
