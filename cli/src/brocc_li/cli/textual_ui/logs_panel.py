from textual.app import ComposeResult
from textual.widgets import Log, Static

from brocc_li.utils.logger import logger


class LogsPanel(Static):
    def compose(self) -> ComposeResult:
        yield Log(highlight=True, auto_scroll=True, id="app-logs")

    def on_mount(self) -> None:
        log_widget = self.query_one("#app-logs", Log)
        logger.set_log_widget(log_widget)

        # Re-enable logging now that we have a UI to show logs
        logger.enabled = True
