# Number of consecutive timeouts needed to trigger rate limit detection
RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD = 2
# Initial cooldown period (in ms) when rate limiting is detected
RATE_LIMIT_INITIAL_COOLDOWN_MS = 5000
# Maximum cooldown period (in ms) regardless of consecutive timeouts
RATE_LIMIT_MAX_COOLDOWN_MS = 30000
# Exponential factor for increasing cooldown time with each additional timeout
# Formula: cooldown = min(MAX_COOLDOWN, INITIAL_COOLDOWN * BACKOFF_FACTOR^(timeouts - threshold))
RATE_LIMIT_BACKOFF_FACTOR = 2


def rate_limit_backoff_s(consecutive_timeouts: int) -> float:
    """Calculate the exponential backoff cooldown time based on consecutive timeouts.

    Args:
        consecutive_timeouts: Number of consecutive timeouts that occurred

    Returns:
        The cooldown time in seconds
    """
    if consecutive_timeouts < RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD:
        # For early timeouts, scale cooldown gradually
        return 0.5 + (consecutive_timeouts - 1) * 0.5

    # Calculate exponential backoff for multiple timeouts
    cooldown_ms = min(
        RATE_LIMIT_MAX_COOLDOWN_MS,
        RATE_LIMIT_INITIAL_COOLDOWN_MS
        * (
            RATE_LIMIT_BACKOFF_FACTOR
            ** (consecutive_timeouts - RATE_LIMIT_CONSECUTIVE_TIMEOUTS_THRESHOLD)
        ),
    )
    return cooldown_ms / 1000  # Convert to seconds
