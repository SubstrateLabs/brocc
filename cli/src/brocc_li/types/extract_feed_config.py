from typing import Optional, Tuple
from enum import Enum
from datetime import datetime
from dataclasses import dataclass
from pydantic import BaseModel


# Maximum time to wait for initial feed containers to load before aborting
INITIAL_LOAD_TIMEOUT_MS = 10000
# Brief delay after clicking expandable elements, allows UI to respond
CLICK_WAIT_TIMEOUT_MS = 500
# Time to wait for all network activity to finish when navigating between pages
NETWORK_IDLE_TIMEOUT_MS = 5000
# Default CSS selector to locate article content on detail pages
DEFAULT_CONTENT_SELECTOR = "article"
# Maximum time to wait for the article content selector to be found on a detail page
CONTENT_EXTRACTION_TIMEOUT_MS = 3000
# Default minimum delay between sactions
DEFAULT_MIN_DELAY_MS = 1000
# Default maximum delay between actions
DEFAULT_MAX_DELAY_MS = 3000


@dataclass
class ScrollConfig:
    # Minimum delay in seconds between scrolls
    min_delay: float = 0.5
    # Maximum delay in seconds between scrolls
    max_delay: float = 2.0
    # Random variation factor applied to delays (0.3 = ±30% variation)
    jitter_factor: float = 0.3
    # How many scrolls without finding new items before stopping extraction
    max_no_new_items: int = 3
    # How many scrolls with same page height before trying aggressive scroll strategies
    max_consecutive_same_height: int = 3
    # Add a longer random pause after this many items (min, max range)
    random_pause_interval: Tuple[int, int] = (15, 25)


class ScrollPattern(Enum):
    NORMAL = "normal"
    FAST = "fast"
    SLOW = "slow"
    BOUNCE = "bounce"


class ExtractFeedConfig(BaseModel):
    # Schema definition
    feed_schema: type[BaseModel]

    # Navigate to each item
    navigate_options: Optional["NavigateOptions"] = None

    # Runtime behavior
    max_items: Optional[int] = None
    expand_item_selector: Optional[str] = None
    container_selector: Optional[str] = None

    # Source information (required)
    source: str
    source_location_identifier: str
    source_location_name: Optional[str] = None

    # Scroll behavior
    scroll_pattern: ScrollPattern = ScrollPattern.NORMAL
    scroll_config: ScrollConfig = ScrollConfig()

    # Timeouts (in milliseconds)
    initial_load_timeout_ms: int = INITIAL_LOAD_TIMEOUT_MS
    network_idle_timeout_ms: int = NETWORK_IDLE_TIMEOUT_MS
    click_wait_timeout_ms: int = CLICK_WAIT_TIMEOUT_MS

    # Storage options
    use_storage: bool = False
    storage_path: Optional[str] = None
    continue_on_seen: bool = False

    # Date cutoff options
    stop_after_date: Optional[datetime] = None

    # Debug options
    debug: bool = False
    debug_file: Optional[str] = None


class NavigateOptions(BaseModel):
    """Configuration options for deep scraping content.

    Provides a simple way to customize the behavior of deep scraping
    when navigating to individual content pages.
    """

    # CSS selector to find the content element on the detail page
    content_selector: str = DEFAULT_CONTENT_SELECTOR

    # Whether to wait for network idle when navigating to pages
    wait_networkidle: bool = True

    # Maximum time in milliseconds to wait for content selector to appear
    content_timeout_ms: int = CONTENT_EXTRACTION_TIMEOUT_MS

    # Minimum delay in milliseconds between scraping actions
    min_delay_ms: int = DEFAULT_MIN_DELAY_MS

    # Maximum delay in milliseconds between scraping actions
    max_delay_ms: int = DEFAULT_MAX_DELAY_MS
