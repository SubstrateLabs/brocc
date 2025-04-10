import platform
import subprocess

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Log, Static

from brocc_li.utils.logger import logger


class LogsPanel(Static):
    def compose(self) -> ComposeResult:
        with Vertical(id="logs-container"):
            yield Log(highlight=True, auto_scroll=True, id="app-logs")
            yield Button("Open logs file", id="open-log-file-btn", name="open_log_file")

    def on_mount(self) -> None:
        log_widget = self.query_one("#app-logs", Log)
        logger.set_log_widget(log_widget)

        # Add a startup message to help with debugging
        logger.debug("Logs panel initialized")

        # Re-enable logging now that we have a UI to show logs
        logger.enabled = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.name == "open_log_file":
            self.action_open_log_file()

    def action_open_log_file(self) -> None:
        """Opens the log file using the default system application."""
        log_file_path = logger.get_log_file_path()
        if log_file_path and log_file_path.exists():
            try:
                logger.debug(f"Attempting to open log file: {log_file_path}")
                if platform.system() == "Windows":
                    subprocess.Popen(["start", str(log_file_path)], shell=True)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.Popen(["open", str(log_file_path)])
                else:  # Linux and other Unix-like systems
                    subprocess.Popen(["xdg-open", str(log_file_path)])
            except Exception as e:
                logger.error(f"Failed to open log file {log_file_path}: {e}")
        elif log_file_path:
            logger.warning(f"Log file not found: {log_file_path}")
        else:
            logger.warning("Log file path is not configured or available.")
