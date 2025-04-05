from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.css.query import NoMatches
from textual.widgets import Button, Label, LoadingIndicator, Static

from brocc_li.utils.logger import logger

# Constants for UI messages and labels
UI_STATUS = {
    "WINDOW_OPEN": "Window: [green]Open[/green]",
    "WINDOW_READY": "Window: [blue]Ready to launch[/blue]",
    "WINDOW_CLOSED": "Window: [blue]Closed after logout[/blue]",
    "WINDOW_LAUNCHED": "Window: [green]Launched successfully[/green]",
    "WINDOW_FOCUSED": "Window: [green]Brought to foreground[/green]",
    "WINDOW_LAUNCH_FAILED": "Window: [red]Failed to launch[/red]",
    "WINDOW_STATUS_UNCLEAR": "Window: [yellow]Status unclear[/yellow]",
    "WINDOW_LOGGED_OUT": "Window: [yellow]Running but logged out, closing automatically...[/yellow]",
    "WEBAPP_OPEN": "App: [green]Open[/green]",
    "WEBAPP_READY": "App: [blue]Ready to launch[/blue]",
}

BUTTON_LABELS = {
    "OPENING_WINDOW": "✷  Opening Brocc window...  ✷",
    "OPEN_WINDOW": "✷  Open Brocc window  ✷",
    "SHOW_WINDOW": "✷  Show Brocc window  ✷",
    "LOGIN_TO_OPEN": "✷  Login to start Brocc  ✷",
}


class InfoPanel(Static):
    def __init__(self, app_instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app_instance = app_instance

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Site API: Checking...", id="siteapi-health"),
            Static("Local API: Checking...", id="localapi-health"),
            Static("Window: Checking...", id="webapp-health"),
            Static("DuckDB: Initializing...", id="duckdb-health"),
            Static("LanceDB: Initializing...", id="lancedb-health"),
            Label("Not logged in", id="auth-status"),
            id="health-container",
        )
        yield Container(
            Horizontal(
                Button(
                    label="Open DuckDB UI",
                    id="duckdb-ui-btn",
                    variant="default",
                    name="launch_duckdb_ui",
                ),
                Button(label="Login", id="login-btn", variant="default", name="login"),
                id="auth-buttons",
            ),
            Static("", id="auth-url-display"),
            id="auth-container",
        )

    def update_ui_status(self, message: str, element_id: str) -> bool:
        """Update UI status element with a message"""
        try:
            element = self.query_one(f"#{element_id}", Static)
            element.update(message)
            return True
        except NoMatches:
            logger.debug(f"Could not update UI status: element #{element_id} not found")
            return False

    def update_auth_status(self):
        """Update authentication status display"""
        try:
            status_label = self.query_one("#auth-status", Label)
            login_btn = self.query_one("#login-btn", Button)

            # Get references to app for status info
            auth_data = self.app_instance.auth_data
            is_logged_in = self.app_instance.is_logged_in
            site_api_healthy = self.app_instance.site_api_healthy

            # Find open_webapp_btn from main app, not in InfoPanel
            try:
                open_webapp_btn = self.app_instance.query_one("#open-webapp-btn", Button)
            except NoMatches:
                logger.debug("Could not find open-webapp-btn")
                open_webapp_btn = None

            if auth_data is None:
                status_label.update("Not logged in")
                login_btn.disabled = False or not site_api_healthy
                if open_webapp_btn:
                    open_webapp_btn.disabled = True
                return

            if is_logged_in:
                email = auth_data.get("email", "Unknown user")
                api_key = auth_data.get("apiKey", "")
                masked_key = f"{api_key[:8]}...{api_key[-5:]}" if api_key else "None"

                status_label.update(f"Logged in as: {email} (API Key: {masked_key})")
                login_btn.disabled = True
                if open_webapp_btn:
                    open_webapp_btn.disabled = False
            else:
                status_label.update("Not logged in")
                login_btn.disabled = False or not site_api_healthy
                if open_webapp_btn:
                    open_webapp_btn.disabled = True
        except NoMatches:
            logger.debug("Could not update auth status: UI not ready")

    def update_webapp_status(self):
        """Update the App status in the UI based on current state"""
        # Get reference to app and its helper method
        is_webview_open = self.app_instance.is_webview_open

        try:
            webapp_status = self.query_one("#webapp-health", Static)

            # These are in main app, not in InfoPanel
            try:
                open_webapp_btn = self.app_instance.query_one("#open-webapp-btn", Button)
                loading = self.app_instance.query_one("#webapp-loading", LoadingIndicator)
            except NoMatches:
                logger.debug("Could not find webapp UI components")
                return

            is_opening_webapp = getattr(self.app_instance, "is_opening_webapp", False)

            # Check if webview is already open
            if is_webview_open():
                webapp_status.update(UI_STATUS["WEBAPP_OPEN"])
                open_webapp_btn.disabled = False  # Keep enabled for focus functionality
                open_webapp_btn.label = BUTTON_LABELS["SHOW_WINDOW"]
                open_webapp_btn.remove_class("hidden")
                loading.add_class("hidden")
                self.app_instance.is_opening_webapp = False
            else:
                webapp_status.update(UI_STATUS["WEBAPP_READY"])
                # If we're not actively opening the webapp, show the button
                if not is_opening_webapp:
                    open_webapp_btn.disabled = False
                    open_webapp_btn.remove_class("hidden")
                    loading.add_class("hidden")
                else:
                    open_webapp_btn.label = BUTTON_LABELS["OPEN_WINDOW"]

        except NoMatches:
            logger.debug("Could not update App status: UI component not found")

    def update_doc_db_status(self):
        """Update the document database status in the UI"""
        doc_db = self.app_instance.doc_db

        if not doc_db:
            try:
                self.query_one("#duckdb-health", Static).update(
                    "DuckDB: [red]Not initialized[/red]"
                )
                self.query_one("#lancedb-health", Static).update(
                    "LanceDB: [red]Not initialized[/red]"
                )
            except NoMatches:
                logger.debug("Could not update DocDB status: UI component not found")
            return

        # Get status information
        try:
            duckdb_status = doc_db.get_duckdb_status()
            lancedb_status = doc_db.get_lancedb_status()

            # Format DuckDB status
            if duckdb_status.get("healthy", False):
                doc_count = duckdb_status.get("doc_count", 0)
                chunk_count = duckdb_status.get("chunk_count", 0)
                duckdb_msg = (
                    f"DuckDB: [green]Connected[/green] ({doc_count} docs, {chunk_count} chunks)"
                )
            elif duckdb_status.get("initialized", False):
                error = duckdb_status.get("error", "Unknown error")
                duckdb_msg = f"DuckDB: [yellow]Initialized with errors[/yellow] ({error})"
            else:
                error = duckdb_status.get("error", "Unknown error")
                duckdb_msg = f"DuckDB: [red]Not initialized[/red] ({error})"

            # Format LanceDB status - including embeddings info on the same line
            if lancedb_status.get("healthy", False):
                chunk_count = lancedb_status.get("chunk_count", 0)

                # Add embeddings status to the LanceDB line
                embeddings_status = lancedb_status.get("embeddings_status", "Unknown")
                embeddings_details = lancedb_status.get("embeddings_details", "")

                if lancedb_status.get("embeddings_available", False):
                    lancedb_msg = f"LanceDB: [green]Connected[/green] ({chunk_count} chunks) - Embeddings: [green]Ready[/green]"
                else:
                    if "Error" in embeddings_status or "failed" in embeddings_status.lower():
                        lancedb_msg = f"LanceDB: [green]Connected[/green] ({chunk_count} chunks) - Embeddings: [red]Unavailable[/red]"
                    else:
                        lancedb_msg = f"LanceDB: [green]Connected[/green] ({chunk_count} chunks) - Embeddings: [yellow]Not configured[/yellow]"

                # Always add details if they exist
                if embeddings_details:
                    lancedb_msg += f" - {embeddings_details}"

            elif lancedb_status.get("initialized", False):
                error = lancedb_status.get("error", "Unknown error")

                # Add embeddings status
                embeddings_status = lancedb_status.get("embeddings_status", "Unknown")
                embeddings_details = lancedb_status.get("embeddings_details", "")

                if lancedb_status.get("embeddings_available", False):
                    lancedb_msg = f"LanceDB: [yellow]Initialized with errors[/yellow] - Embeddings: [green]Ready[/green]"
                else:
                    if "Error" in embeddings_status or "failed" in embeddings_status.lower():
                        lancedb_msg = f"LanceDB: [yellow]Initialized with errors[/yellow] - Embeddings: [red]Unavailable[/red]"
                    else:
                        lancedb_msg = f"LanceDB: [yellow]Initialized with errors[/yellow] - Embeddings: [yellow]Not configured[/yellow]"

                # Add error and details
                lancedb_msg += f" ({error})"
                if embeddings_details:
                    lancedb_msg += f" - {embeddings_details}"
            else:
                error = lancedb_status.get("error", "Unknown error")
                lancedb_msg = f"LanceDB: [red]Not initialized[/red] ({error})"

                # Add embeddings status if available
                embeddings_status = lancedb_status.get("embeddings_status", "Unknown")
                embeddings_details = lancedb_status.get("embeddings_details", "")
                if embeddings_details:
                    lancedb_msg += f" - {embeddings_details}"

            # Update UI
            try:
                self.query_one("#duckdb-health", Static).update(duckdb_msg)
                self.query_one("#lancedb-health", Static).update(lancedb_msg)
            except NoMatches:
                logger.debug("Could not update DocDB status: UI component not found")

        except Exception as e:
            logger.error(f"Failed to update DocDB status: {e}")
            try:
                self.query_one("#duckdb-health", Static).update("DuckDB: [red]Status error[/red]")
                self.query_one("#lancedb-health", Static).update("LanceDB: [red]Status error[/red]")
            except NoMatches:
                pass

    def display_auth_url(self, url: str) -> None:
        """Display auth URL in the info panel"""
        try:
            auth_url_display = self.query_one("#auth-url-display", Static)
            auth_url_display.update(
                f"🔐 Authentication URL:\n[link={url}]{url}[/link]\n\nClick to open in browser"
            )
        except NoMatches:
            logger.error("Could not display auth URL: UI component not found")
