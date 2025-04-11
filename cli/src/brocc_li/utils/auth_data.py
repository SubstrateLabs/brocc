import json

from brocc_li.cli.config_dir import get_config_dir
from brocc_li.utils.logger import logger

CONFIG_DIR = get_config_dir()
AUTH_FILE = CONFIG_DIR / "auth.json"


def is_logged_in(auth_data):
    """Check if the user is logged in"""
    if auth_data is None:
        return False

    return "apiKey" in auth_data and bool(auth_data["apiKey"])


def load_auth_data():
    try:
        if AUTH_FILE.exists():
            with open(AUTH_FILE) as f:
                auth_data = json.load(f)
            logger.debug(f"Loaded auth data for user: {auth_data.get('email', 'unknown')}")
            return auth_data
        else:
            logger.debug("No saved auth data found")
            return None
    except Exception as e:
        logger.error(f"Error loading auth data: {e}")
        return None


def save_auth_data(auth_data):
    try:
        with open(AUTH_FILE, "w") as f:
            json.dump(auth_data, f)
        logger.debug(f"Saved auth data for user: {auth_data.get('email', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Error saving auth data: {e}")
        return False


def clear_auth_data():
    try:
        if AUTH_FILE.exists():
            AUTH_FILE.unlink()
        logger.debug("Cleared auth data")
        return True
    except Exception as e:
        logger.error(f"Error clearing auth data: {e}")
        return False
