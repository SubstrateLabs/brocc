"""DEVELOPMENT ONLY: used for extractor debugging"""

import time
from collections.abc import Sequence
from typing import Any

from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from brocc_li.utils.logger import logger

# Default styles for different types of content
DEFAULT_STYLES = {
    "text": "white",
    "title": "bold white",
    "author": "cyan",
    "date": "yellow",
    "url": "blue",
    "summary": "dim",
    "metrics": "yellow",
}


class ProgressTracker:
    """Tracks progress of item extraction and displays time estimates."""

    def __init__(self, label: str = "items", target: int | None = None):
        """Initialize progress tracker.

        Args:
            label: Description of the items being extracted
            target: Optional target number of items (if known)
        """
        self.label = label
        self.target = target
        self.start_time = time.time()
        self.count = 0
        self.last_update_time = self.start_time
        self.last_count = 0
        self.recent_rates = []  # Store recent extraction rates

    def update(
        self,
        count: int | None = None,
        force_display: bool = False,
        item_info: str | None = None,
    ) -> None:
        """Update progress count and display status.

        Args:
            count: Current count (if None, increments by 1)
            force_display: Force display update even if would normally be skipped
            item_info: Optional info about the current item to display
        """
        current_time = time.time()

        # Update count if provided, otherwise increment
        if count is not None:
            self.count = count
        else:
            self.count += 1

        # Only update display every 1 second or if forced
        time_since_last = current_time - self.last_update_time
        if time_since_last < 1 and not force_display and self.count > 1:
            return

        # Calculate extraction rate (items per minute)
        items_since_last = self.count - self.last_count

        if time_since_last > 0 and items_since_last > 0:
            current_rate = (items_since_last / time_since_last) * 60
            self.recent_rates.append(current_rate)
            # Keep only the last 5 rates for smoothing
            if len(self.recent_rates) > 5:
                self.recent_rates.pop(0)

        # Display progress
        self._display_progress(item_info)

        # Update tracking variables
        self.last_update_time = current_time
        self.last_count = self.count

    def _get_current_rate(self) -> float:
        """Get current extraction rate (items per minute) with smoothing."""
        if not self.recent_rates:
            overall_elapsed = max(time.time() - self.start_time, 0.001)  # Avoid division by zero
            return (self.count / overall_elapsed) * 60

        # Use average of recent rates for smoother estimates
        return sum(self.recent_rates) / len(self.recent_rates)

    def _format_time(self, seconds: float) -> str:
        """Format time in a human readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"

    def _display_progress(self, item_info: str | None = None) -> None:
        """Display progress information."""
        elapsed_time = time.time() - self.start_time
        rate = self._get_current_rate()

        # Create a status line
        status = Text()

        # Basic progress info
        status.append("Extracted: ", style="bright_white")
        status.append(f"{self.count} {self.label}", style="green")

        if self.target:
            percent = (self.count / self.target) * 100
            status.append(f" of {self.target} ({percent:.1f}%)", style="green")

        status.append(" | ", style="dim")

        # Rate info
        status.append("Rate: ", style="bright_white")
        status.append(f"{rate:.1f} {self.label}/min", style="cyan")
        status.append(" | ", style="dim")

        # Elapsed time
        status.append("Elapsed: ", style="bright_white")
        status.append(self._format_time(elapsed_time), style="yellow")

        # Estimates for different milestones
        status.append(" | ", style="dim")
        status.append("ETA: ", style="bright_white")

        # Only show estimates if we have a positive rate
        if rate > 0:
            # Next 10 items
            eta_10 = (10 / rate) * 60
            status.append("+10: ", style="bright_white")
            status.append(self._format_time(eta_10), style="magenta")
            status.append(" | ", style="dim")

            # Next 100 items
            eta_100 = (100 / rate) * 60
            status.append("+100: ", style="bright_white")
            status.append(self._format_time(eta_100), style="magenta")

            # Next 1000 items
            eta_1000 = (1000 / rate) * 60
            status.append("+1000: ", style="bright_white")
            status.append(self._format_time(eta_1000), style="magenta")
            status.append(" | ", style="dim")

            # If target is known, show time to completion
            if self.target and self.count < self.target:
                remaining = self.target - self.count
                eta_completion = (remaining / rate) * 60
                status.append(" | ", style="dim")
                status.append("Complete: ", style="bright_white")
                status.append(self._format_time(eta_completion), style="blue")
        else:
            status.append("Calculating...", style="dim")

        # Print the status line, overwriting the previous one
        logger.print(status)

        # If item info is provided, print it on a new line
        if item_info:
            logger.print(f"  → {item_info}", style="dim")


def _get_sampled_indices(total_items: int, max_display_items: int) -> tuple[list[int], int, int]:
    """Calculates indices for head, middle, and tail sampling."""
    # Get head indices (first third)
    head_count = max_display_items // 3
    head_indices = list(range(min(head_count, total_items)))

    # Get tail indices (last third)
    tail_count = max_display_items // 3
    tail_start = total_items
    if tail_count > 0:
        tail_start = max(0, total_items - tail_count)
        tail_indices = list(range(tail_start, total_items))
    else:
        tail_indices = []

    # Get middle indices (middle third)
    middle_count = max_display_items - len(head_indices) - len(tail_indices)
    if middle_count > 0 and total_items > head_count + tail_count:
        middle_start = (total_items // 2) - (middle_count // 2)
        middle_indices = list(range(middle_start, min(middle_start + middle_count, tail_start)))
    else:
        middle_indices = []

    # Combine all indices
    all_indices = head_indices + middle_indices + tail_indices
    head_size = len(head_indices)
    middle_size = len(middle_indices)

    return all_indices, head_size, middle_size


def _add_table_rows(
    table: Table,
    items_to_display: list[dict[str, Any]],
    columns: Sequence[str | tuple[str, str] | tuple[str, str, bool]],
    total_items: int,
    max_display_items: int,
    head_size: int,
    middle_size: int,
) -> None:
    """Adds rows to the table, handling sampling and separators."""
    if total_items > max_display_items:
        # Sampled case - add separators
        for i, item in enumerate(items_to_display):
            # Add a separator row between sections
            if i == head_size or (middle_size > 0 and i == head_size + middle_size):
                separator_row = ["..."] * len(columns)
                table.add_row(*separator_row, style="dim")

            # Add the actual item row
            row_data = []
            for col in columns:
                name = col[0] if isinstance(col, (tuple, list)) else col
                value = item.get(name, "")

                # For Content column, use Markdown renderer
                if name == "Content" and value:
                    value = Markdown(value)
                else:
                    value = str(value) if value is not None else ""

                row_data.append(value)

            table.add_row(*row_data)
    else:
        # Regular case - add all items without separators
        for item in items_to_display:  # Use items_to_display which is just items in this case
            row_data = []
            for col in columns:
                name = col[0] if isinstance(col, (tuple, list)) else col
                value = item.get(name, "")

                # For Content column, use Markdown renderer
                if name == "Content" and value:
                    value = Markdown(value)
                else:
                    value = str(value) if value is not None else ""

                row_data.append(value)

            table.add_row(*row_data)


def display_items(
    items: list[dict[str, Any]],
    title: str,
    columns: Sequence[str | tuple[str, str] | tuple[str, str, bool]],
    max_display_items: int = 15,
) -> None:
    """Display items in a rich table with auto-sizing and smart defaults.

    Args:
        items: List of dictionaries containing item data
        title: Title for the table
        columns: List of column definitions. Each can be:
            - str: Column name (uses default style)
            - tuple[str, str]: (name, style)
            - tuple[str, str, bool]: (name, style, no_wrap)
        max_display_items: Maximum number of items to display in the table
    """
    # Determine which items to display
    total_items = len(items)
    items_to_display = items
    display_title = title
    head_size = 0
    middle_size = 0

    if total_items > max_display_items:
        indices_to_display, head_size, middle_size = _get_sampled_indices(
            total_items, max_display_items
        )
        items_to_display = [items[i] for i in indices_to_display]
        display_title = f"{title} (showing {len(items_to_display)} of {total_items} items)"

    # Create the table
    table = Table(
        title=display_title,
        show_header=True,
        header_style="bold magenta",
        show_lines=True,
        width=logger.console.width,
    )

    # Add columns with smart defaults
    for col in columns:
        if isinstance(col, str):
            name, style, no_wrap = col, DEFAULT_STYLES.get(col.lower(), "white"), False
        elif len(col) == 2:
            name, style = col
            no_wrap = False
        else:
            name, style, no_wrap = col

        table.add_column(name, style=style, no_wrap=no_wrap)

    # Add rows to the table
    _add_table_rows(
        table,
        items_to_display,
        columns,
        total_items,
        max_display_items,
        head_size,
        middle_size,
    )

    logger.print(table)
