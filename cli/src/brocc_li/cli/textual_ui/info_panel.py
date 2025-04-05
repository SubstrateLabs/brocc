from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Label, Static


class InfoPanel(Static):
    def __init__(self, app_instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app_instance = app_instance

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Site API: Checking...", id="site-health"),
            Static("Local API: Checking...", id="local-health"),
            Static("Window: Checking...", id="webapp-health"),
            Label("Not logged in", id="auth-status"),
            id="health-container",
        )
        yield Container(
            Horizontal(
                Button(label="Login", id="login-btn", variant="default", name="login"),
                id="auth-buttons",
            ),
            Static("", id="auth-url-display"),
            id="auth-container",
        )
