from brocc_li.types.extract_feed_config import (
    ScrollPattern,
)
from playwright.sync_api import Page
import random
import time
from brocc_li.utils.logger import logger


# Multiplier ranges for viewport height when scrolling in different patterns
# (min_multiplier, max_multiplier) - random value in this range * viewport height = scroll amount
SCROLL_PATTERN_CONFIGS = {
    ScrollPattern.NORMAL: (0.8, 1.2),  # Regular scrolling, ~1 viewport
    ScrollPattern.FAST: (1.5, 2.5),  # Fast scrolling, 1.5-2.5 viewports at once
    ScrollPattern.SLOW: (0.5, 0.8),  # Slow scrolling, less than 1 viewport
    ScrollPattern.BOUNCE: (1.2, 1.5),  # Bounce scrolling, slightly more than 1 viewport
}
# For bounce pattern: min ratio of up-scroll compared to down-scroll
BOUNCE_SCROLL_UP_RATIO_MIN = 0.3
# For bounce pattern: max ratio of up-scroll compared to down-scroll
BOUNCE_SCROLL_UP_RATIO_MAX = 0.5
# For bounce pattern: min pause time (seconds) between down and up scroll
BOUNCE_SCROLL_PAUSE_MIN = 0.2
# For bounce pattern: max pause time (seconds) between down and up scroll
BOUNCE_SCROLL_PAUSE_MAX = 0.4


def human_scroll(
    page: Page, pattern: ScrollPattern, seen_only_multiplier: float = 1.0
) -> None:
    """Simulate human-like scrolling behavior.

    Args:
        page: The current page
        pattern: The scrolling pattern to use
        seen_only_multiplier: Multiplier to increase scroll distance when only seen items are found
    """
    viewport_height = page.evaluate("window.innerHeight")

    if pattern == ScrollPattern.BOUNCE:
        down_amount = int(
            viewport_height
            * random.uniform(*SCROLL_PATTERN_CONFIGS[pattern])
            * seen_only_multiplier
        )
        up_amount = int(
            down_amount
            * random.uniform(BOUNCE_SCROLL_UP_RATIO_MIN, BOUNCE_SCROLL_UP_RATIO_MAX)
        )
        page.evaluate(f"window.scrollBy(0, {down_amount})")
        time.sleep(random.uniform(BOUNCE_SCROLL_PAUSE_MIN, BOUNCE_SCROLL_PAUSE_MAX))
        page.evaluate(f"window.scrollBy(0, -{up_amount})")
    else:
        scroll_amount = int(
            viewport_height
            * random.uniform(*SCROLL_PATTERN_CONFIGS[pattern])
            * seen_only_multiplier
        )
        page.evaluate(f"window.scrollBy(0, {scroll_amount})")

        # When using a large multiplier for aggressive scrolling, log it
        if seen_only_multiplier > 1.5:
            logger.debug(
                f"Fast-scrolling with {seen_only_multiplier:.1f}x multiplier ({scroll_amount} pixels)"
            )
