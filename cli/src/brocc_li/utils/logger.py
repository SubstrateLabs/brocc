import os
from contextlib import contextmanager
from typing import Any, TextIO

from rich.console import Console


class Logger:
    def __init__(self, enabled: bool = True, file: TextIO | None = None):
        self.enabled = enabled
        self._console = Console(file=file)
        self._null_console = Console(file=open(os.devnull, "w"))
        self._log_widget = None
        self._log_history = []
        self._max_history = 1000  # Store last 1000 log messages

    def set_log_widget(self, log_widget):
        """Set a Textual Log widget to send logs to."""
        self._log_widget = log_widget

        # Clear any existing content in the widget
        if log_widget:
            log_widget.clear()
            # Write any existing history to the widget
            if self._log_history:
                log_widget.write_lines(self._log_history)

    def _write_to_log(self, level: str, message: str):
        """Write to the log widget if available and store in history."""
        # Format with timestamp
        import datetime

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] [{level}] {message}"

        # Store in history
        if len(self._log_history) >= self._max_history:
            self._log_history.pop(0)
        self._log_history.append(formatted_msg)

        # Write to widget if available
        if self._log_widget:
            try:
                # Check if the log widget has a write_line method
                # This is a simple check to see if the app is still running
                # If the app is shutting down, this will likely raise an exception
                if hasattr(self._log_widget, "write_line") and callable(
                    self._log_widget.write_line
                ):
                    self._log_widget.write_line(formatted_msg)
                else:
                    # If the app is shutting down, just suppress output
                    pass
            except Exception:
                # During shutdown, don't show errors about log widget
                # Just suppress the error and continue
                pass

    def print(self, *args, **kwargs):
        """Print to console if enabled."""
        if self.enabled:
            self._console.print(*args, **kwargs)
            message = " ".join(str(arg) for arg in args)
            self._write_to_log("INFO", message)

    def log(self, *args, **kwargs):
        """Alias for print."""
        self.print(*args, **kwargs)

    def debug(self, message: Any, *args, **kwargs):
        """Print debug-level messages."""
        if self.enabled:
            self._console.print(f"[dim]{message}[/dim]", *args, **kwargs)
            self._write_to_log("DEBUG", str(message))

    def info(self, message: Any, *args, **kwargs):
        """Print info-level messages."""
        if self.enabled:
            self._console.print(message, *args, **kwargs)
            self._write_to_log("INFO", str(message))

    def warning(self, message: Any, *args, **kwargs):
        """Print warning-level messages."""
        if self.enabled:
            self._console.print(f"[yellow]{message}[/yellow]", *args, **kwargs)
            self._write_to_log("WARNING", str(message))

    def error(self, message: Any, *args, **kwargs):
        """Print error-level messages."""
        if self.enabled:
            self._console.print(f"[red]{message}[/red]", *args, **kwargs)
            self._write_to_log("ERROR", str(message))

    def success(self, message: Any, *args, **kwargs):
        """Print success messages."""
        if self.enabled:
            self._console.print(f"[green]{message}[/green]", *args, **kwargs)
            self._write_to_log("SUCCESS", str(message))

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
