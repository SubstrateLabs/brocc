from brocc_li.scroll_prototype.rate_limit_backoff_s import (
    RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD,
)


def adjust_timeout_counter(
    consecutive_timeouts: int,
    success: bool = True,
    timeout_occurred: bool = False,
    aggressive: bool = False,
) -> int:
    """Manages the timeout counter according to consistent rules.

    Args:
        consecutive_timeouts: Current count of consecutive timeouts
        success: Whether the operation was successful
        timeout_occurred: Whether a timeout occurred in the current operation
        aggressive: Whether to use more aggressive counter reduction (for definite success)

    Returns:
        Updated timeout counter value
    """
    # Always increment on new timeouts
    if timeout_occurred:
        return consecutive_timeouts + 1

    # For successful operations with significant timeout history
    if success and consecutive_timeouts > RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD and aggressive:
        # Reduce more aggressively but don't fully reset
        return max(1, consecutive_timeouts - 2)
    elif success and consecutive_timeouts > 0:
        # Gradual decrease for normal success
        return max(0, consecutive_timeouts - 1)
    elif success:
        # Full reset for success with no timeout history
        return 0

    # For failures, maintain caution
    return consecutive_timeouts
