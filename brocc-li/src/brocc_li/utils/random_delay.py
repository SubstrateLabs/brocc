import time
import random
from brocc_li.utils.logger import logger


def random_delay(base_delay: float, variation: float = 0.2) -> None:
    """Add random variation to delays."""
    time.sleep(base_delay * random.uniform(1 - variation, 1 + variation))


def random_delay_with_jitter(
    min_ms: int, max_ms: int, jitter_factor: float = 0.3
) -> None:
    """Add a random delay with jitter to make scraping more human-like."""
    min_delay = min_ms / 1000
    max_delay = max_ms / 1000
    base_delay = random.uniform(min_delay, max_delay)
    jitter = base_delay * jitter_factor * random.choice([-1, 1])
    final_delay = min(max_delay, max(0.1, base_delay + jitter))
    logger.debug(f"Waiting for {final_delay:.2f} seconds...")
    time.sleep(final_delay)
