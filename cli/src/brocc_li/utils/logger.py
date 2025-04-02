import os
from contextlib import contextmanager
from typing import Any, TextIO

from rich.console import Console


class Logger:
    def __init__(self, enabled: bool = True, file: TextIO | None = None):
        self.enabled = enabled
        self._console = Console(file=file)
        self._null_console = Console(file=open(os.devnull, "w"))

    def print(self, *args, **kwargs):
        """Print to console if enabled."""
        if self.enabled:
            self._console.print(*args, **kwargs)

    def log(self, *args, **kwargs):
        """Alias for print."""
        self.print(*args, **kwargs)

    def debug(self, message: Any, *args, **kwargs):
        """Print debug-level messages."""
        if self.enabled:
            self._console.print(f"[dim]{message}[/dim]", *args, **kwargs)

    def info(self, message: Any, *args, **kwargs):
        """Print info-level messages."""
        if self.enabled:
            self._console.print(message, *args, **kwargs)

    def warning(self, message: Any, *args, **kwargs):
        """Print warning-level messages."""
        if self.enabled:
            self._console.print(f"[yellow]{message}[/yellow]", *args, **kwargs)

    def error(self, message: Any, *args, **kwargs):
        """Print error-level messages."""
        if self.enabled:
            self._console.print(f"[red]{message}[/red]", *args, **kwargs)

    def success(self, message: Any, *args, **kwargs):
        """Print success messages."""
        if self.enabled:
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


# Create a default instance
logger = Logger()
