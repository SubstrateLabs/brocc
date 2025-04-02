import random
import time

from playwright.sync_api import Page

from brocc_li.extract.human_scroll import human_scroll
from brocc_li.extract.restore_scroll import (
    get_current_scroll_position,
    scroll_to_bottom,
)
from brocc_li.types.extract_feed_config import ExtractFeedConfig, ScrollPattern
from brocc_li.utils.logger import logger
from brocc_li.utils.random_delay import random_delay

# Threshold for determining when we're at the bottom of the page (in pixels)
BOTTOM_THRESHOLD = 200


def execute_turbo_scroll(page: Page) -> None:
    """Execute an aggressive turbo scroll to quickly reach unseen content.

    Performs multiple aggressive scrolls with minimal delays to quickly
    traverse large sections of content.

    Args:
        page: The page to scroll
    """
    logger.warning("Executing turbo scroll to reach unseen content faster...")

    # First aggressive scroll
    scroll_to_bottom(page, aggressive=True)
    time.sleep(0.1)  # Ultra-minimal delay

    # Second aggressive scroll to ensure maximum distance
    scroll_to_bottom(page, aggressive=True)
    time.sleep(0.2)  # Minimal wait time


def execute_bottom_jump(page: Page, consecutive_all_seen: int = 0) -> bool:
    """Jump directly to the bottom of the page and check if actually at bottom.

    Args:
        page: The page to scroll
        consecutive_all_seen: How many consecutive scrolls had all seen items

    Returns:
        Whether we reached the actual bottom of the page
    """
    logger.warning("Jumping to bottom of page...")

    # Scroll to bottom
    scroll_to_bottom(page)
    time.sleep(0.5)

    # Check if we reached actual bottom by seeing if scroll position is near page height
    scroll_pos = get_current_scroll_position(page)
    page_height = page.evaluate("document.documentElement.scrollHeight")
    viewport_height = page.evaluate("window.innerHeight")

    # We're at bottom if remaining scroll distance is less than threshold
    at_bottom = (page_height - (scroll_pos + viewport_height)) < BOTTOM_THRESHOLD

    if at_bottom:
        # Shorter wait for consecutive seen content
        wait_time = 1.0 if consecutive_all_seen < 6 else 0.3
        logger.success(f"Reached bottom of page, waiting {wait_time}s for new content to load...")
        time.sleep(wait_time)

    return at_bottom


def trigger_lazy_loading(page: Page, consecutive_all_seen: int) -> None:
    """Trigger lazy loading by scrolling up slightly and back down.

    Only triggers occasionally based on the consecutive_all_seen counter.

    Args:
        page: The page to scroll
        consecutive_all_seen: How many consecutive scrolls had all seen items
    """
    # Only do this occasionally to avoid unnecessary scrolls
    if consecutive_all_seen % 3 != 0:
        return

    viewport_height = page.evaluate("window.innerHeight")

    # Scroll up slightly to trigger potential lazy loading
    page.evaluate(f"window.scrollBy(0, -{viewport_height / 3})")
    time.sleep(0.2)

    # Scroll back to bottom
    scroll_to_bottom(page)
    time.sleep(0.2)


def get_adaptive_scroll_multiplier(all_items_seen: bool, consecutive_all_seen: int) -> float:
    """Get an adaptive scroll multiplier based on scrolling context.

    When repeatedly seeing already seen items, increase scroll distance.

    Args:
        all_items_seen: Whether all items in the current view were already seen
        consecutive_all_seen: How many consecutive scrolls had all items seen

    Returns:
        A scroll multiplier to use (1.0 = normal, >1.0 = faster)
    """
    if not all_items_seen:
        return 1.0

    # Exponentially increase scroll distance when we keep seeing only seen items
    # Start with 1.5x, then 2.0x, 2.5x, 3.0x, etc. up to 5x
    return min(5.0, 1.5 + (consecutive_all_seen * 0.5))


def apply_adaptive_delay(
    new_items: int,
    all_items_seen: bool,
    consecutive_all_seen: int,
    consecutive_same_height: int,
) -> None:
    """Apply an adaptive delay based on the current context.

    Use shorter delays when stuck or only seeing already seen items.

    Args:
        new_items: Number of new items found in this iteration
        all_items_seen: Whether all items in this view were already seen
        consecutive_all_seen: Number of consecutive "all seen" scrolls
        consecutive_same_height: Number of consecutive scrolls with same height
    """
    if new_items > 0:
        random_delay(0.3, 0.2)  # Normal delay when finding new items
    elif all_items_seen:
        # Use progressively shorter delays the longer we've been seeing only seen items
        delay_base = max(0.05, 0.2 - (consecutive_all_seen * 0.02))
        time.sleep(delay_base)  # Minimal delay for repeated all-seen cases
    elif consecutive_same_height > 0:
        random_delay(0.5, 0.2)  # Reduced from 1.0 to 0.5
    else:
        random_delay(0.3, 0.2)  # Reduced from 0.5 to 0.3


def handle_stuck_at_same_height(
    page: Page,
    consecutive_same_height: int,
    config: ExtractFeedConfig,
    scroll_multiplier: float,
) -> int:
    """Handle case where page height isn't changing despite scrolling.

    Args:
        page: The page to scroll
        consecutive_same_height: Number of consecutive scrolls with same height
        config: Feed configuration
        scroll_multiplier: Current scroll multiplier

    Returns:
        Updated consecutive_same_height (reset to 0 if action taken)
    """
    if consecutive_same_height >= config.scroll_config.max_consecutive_same_height:
        if consecutive_same_height % 2 == 0:
            # When stuck at same height for a while, try a dramatic jump to bottom
            logger.debug("Stuck at same height, jumping to bottom of page...")
            # Instead of scrolling up and down, go directly to bottom
            scroll_to_bottom(page)
            random_delay(0.5, 0.2)  # Reduced delay from 1.0 to 0.5
        else:
            human_scroll(page, ScrollPattern.FAST, scroll_multiplier)
        return 0  # Reset counter
    return consecutive_same_height  # No action taken


def perform_adaptive_scroll(
    page: Page,
    new_items: int,
    consecutive_same_height: int,
    config: ExtractFeedConfig,
    all_items_seen: bool = False,
    consecutive_all_seen: int = 0,
    is_turbo_mode: bool = False,
) -> tuple[int, int, int, bool]:
    """Perform adaptive scrolling based on the current context.

    Manages different scrolling strategies based on the state of content traversal.

    Args:
        page: The page to scroll
        new_items: Number of new items found in this iteration
        consecutive_same_height: Number of consecutive scrolls with same height
        config: Feed configuration
        all_items_seen: Whether all items in the current view were already seen
        consecutive_all_seen: Number of consecutive scrolls where all items were seen
        is_turbo_mode: Whether turbo mode is currently active

    Returns:
        Tuple containing:
        - updated consecutive_same_height
        - last_height
        - consecutive_all_seen
        - is_turbo_mode
    """
    current_height = page.evaluate("document.documentElement.scrollHeight")
    last_height = current_height

    # Turbo mode - super-fast scrolling to quickly traverse lots of seen content
    if is_turbo_mode:
        logger.warning("Continuing turbo mode to reach unseen content faster...")
        execute_turbo_scroll(page)
        return 0, current_height, consecutive_all_seen, True  # Keep turbo mode active

    # Activate turbo mode after many consecutive scrolls with only seen items
    if all_items_seen and consecutive_all_seen >= 5:
        logger.warning("Entering turbo mode to reach unseen content faster...")
        execute_turbo_scroll(page)
        return 0, current_height, consecutive_all_seen, True  # Activate turbo mode

    # Jump to bottom after several consecutive all-seen scrolls
    if all_items_seen and consecutive_all_seen >= 3:
        at_bottom = execute_bottom_jump(page, consecutive_all_seen)

        # Try to trigger lazy loading at bottom
        if at_bottom:
            trigger_lazy_loading(page, consecutive_all_seen)

        return 0, current_height, consecutive_all_seen, False

    # Calculate adaptive scroll multiplier
    scroll_multiplier = get_adaptive_scroll_multiplier(all_items_seen, consecutive_all_seen)

    # Handle the same-height case (potentially stuck)
    if current_height == last_height:
        consecutive_same_height += 1
        consecutive_same_height = handle_stuck_at_same_height(
            page, consecutive_same_height, config, scroll_multiplier
        )

        # If we didn't reset to 0, do a normal scroll
        if consecutive_same_height > 0:
            # When all items are seen, prefer faster scrolling patterns
            if all_items_seen and consecutive_all_seen > 1:
                human_scroll(page, ScrollPattern.FAST, scroll_multiplier)
            else:
                human_scroll(page, random.choice(list(ScrollPattern)), scroll_multiplier)
    else:
        # Height changed, reset counter and do normal scroll
        consecutive_same_height = 0
        if all_items_seen and consecutive_all_seen > 2:
            # Page height changed but still all seen - scroll faster toward bottom
            logger.debug("Page height changed, continuing fast scroll to bottom...")
            human_scroll(page, ScrollPattern.FAST, scroll_multiplier)
        else:
            human_scroll(page, random.choice(list(ScrollPattern)), scroll_multiplier)

    # Apply appropriate delay based on context
    apply_adaptive_delay(new_items, all_items_seen, consecutive_all_seen, consecutive_same_height)

    return consecutive_same_height, last_height, consecutive_all_seen, False
