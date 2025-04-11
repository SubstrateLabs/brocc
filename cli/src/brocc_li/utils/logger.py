import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TextIO

from rich.console import Console

from brocc_li.cli.config_dir import get_config_dir

# Define log file path in user config directory
CONFIG_DIR = get_config_dir()
LOG_FILE = CONFIG_DIR / "brocc_session.log"

# Open the log file, overwriting if it exists
try:
    log_file_handle = open(LOG_FILE, "w", encoding="utf-8")
except Exception as e:
    # Fallback to stderr if file cannot be opened
    print(f"Error opening log file {LOG_FILE}: {e}", file=sys.stderr)
    log_file_handle = None


class Logger:
    def __init__(self, enabled: bool = True, file: TextIO | None = log_file_handle):
        self.enabled = enabled
        self._console = Console(file=file)
        self._null_console = Console(file=open(os.devnull, "w"))
        self._log_widget = None
        self._log_history = []
        self._max_history = 1000  # Store last 1000 log messages
        self._shutting_down = False  # Flag to suppress output during shutdown

    def mark_shutting_down(self):
        """Mark logger as shutting down to suppress further output"""
        self._shutting_down = True

    def print(self, *args, **kwargs):
        """Print to console if enabled."""
        if self.enabled and not self._shutting_down:
            self._console.print(*args, **kwargs)

    def log(self, *args, **kwargs):
        """Alias for print."""
        self.print(*args, **kwargs)

    def debug(self, message: Any, *args, **kwargs):
        """Print debug-level messages."""
        if self.enabled and not self._shutting_down:
            self._console.print(f"[dim]{message}[/dim]", *args, **kwargs)

    def info(self, message: Any, *args, **kwargs):
        """Print info-level messages."""
        if self.enabled and not self._shutting_down:
            self._console.print(message, *args, **kwargs)

    def warning(self, message: Any, *args, **kwargs):
        """Print warning-level messages."""
        if self.enabled and not self._shutting_down:
            self._console.print(f"[yellow]{message}[/yellow]", *args, **kwargs)

    def error(self, message: Any, *args, **kwargs):
        """Print error-level messages."""
        if self.enabled and not self._shutting_down:
            self._console.print(f"[red]{message}[/red]", *args, **kwargs)

    def success(self, message: Any, *args, **kwargs):
        """Print success messages."""
        if self.enabled and not self._shutting_down:
            self._console.print(f"[green]{message}[/green]", *args, **kwargs)

    @contextmanager
    def suppress(self):
        """Temporarily suppress all output."""
        old_enabled = self.enabled
        self.enabled = False
        try:
            yield
        finally:
            self.enabled = old_enabled

    @property
    def console(self) -> Console:
        """Get the underlying Rich console."""
        return self._console if self.enabled else self._null_console

    def get_log_file_path(self) -> Path | None:
        """Return the path to the log file, if configured."""
        if log_file_handle:
            return LOG_FILE
        return None


# Create a default instance
logger = Logger()

# Add a startup log message indicating where logs are stored
if log_file_handle:
    logger.debug(f"Logging to file: {LOG_FILE}")
else:
    logger.warning("Logging to file disabled due to error during file open.")
