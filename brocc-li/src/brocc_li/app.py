from textual.app import App, ComposeResult
from textual.widgets import Footer, Header


class BroccApp(App):
    """A Textual app to manage stopwatches."""

    BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Footer()


if __name__ == "__main__":
    app = BroccApp()
    app.run()
