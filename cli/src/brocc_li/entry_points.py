from brocc_li.cli.app import BroccApp
from brocc_li.utils.logger import logger


def start():
    # Suppress normal logging until the app is properly initialized
    # This prevents logs from appearing before the Textual UI starts
    initial_enabled = logger.enabled
    logger.enabled = False

    try:
        app = BroccApp()
        app.run()
    finally:
        # Restore original logger state if app fails to start
        logger.enabled = initial_enabled
