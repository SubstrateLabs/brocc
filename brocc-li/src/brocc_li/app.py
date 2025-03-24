from textual.app import App, ComposeResult
from textual.widgets import Footer, Header


class BroccApp(App):
    """A Textual app to manage stopwatches."""

    TITLE = "🥦 brocc"
    BINDINGS = [("ctrl+c", "request_quit", "Quit")]

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Footer()

    def action_request_quit(self) -> None:
        """Action to quit the app."""
        self.exit()


if __name__ == "__main__":
    app = BroccApp()
    app.run()
