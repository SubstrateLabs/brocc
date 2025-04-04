from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Log, Static

from brocc_li.utils.logger import logger


class LogsPanel(Static):
    """Panel for displaying application logs."""

    def compose(self) -> ComposeResult:
        with Vertical(id="logs-container"):
            yield Log(highlight=True, auto_scroll=True, id="app-logs")

    def on_mount(self) -> None:
        log_widget = self.query_one("#app-logs", Log)
        logger.set_log_widget(log_widget)

        # Add a startup message to help with debugging
        logger.info("Logs panel initialized")

        # Re-enable logging now that we have a UI to show logs
        logger.enabled = True
