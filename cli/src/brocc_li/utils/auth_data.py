import json

from brocc_li.utils.constants import AUTH_FILE
from brocc_li.utils.logger import logger


def is_logged_in(auth_data):
    """Check if the user is logged in"""
    if auth_data is None:
        return False

    return "apiKey" in auth_data and bool(auth_data["apiKey"])


def load_auth_data(auth_file=None):
    """
    Load auth data from local file

    Args:
        auth_file: Optional Path object for the auth file, defaults to AUTH_FILE from constants
    """
    auth_file = auth_file or AUTH_FILE
    config_dir = auth_file.parent

    try:
        config_dir.mkdir(exist_ok=True)
        if auth_file.exists():
            with open(auth_file) as f:
                auth_data = json.load(f)
            logger.info(f"Loaded auth data for user: {auth_data.get('email', 'unknown')}")
            return auth_data
        else:
            logger.debug("No saved auth data found")
            return None
    except Exception as e:
        logger.error(f"Error loading auth data: {e}")
        return None


def save_auth_data(auth_data, auth_file=None):
    """
    Save auth data to local file

    Args:
        auth_data: Auth data to save
        auth_file: Optional Path object for the auth file, defaults to AUTH_FILE from constants
    """
    auth_file = auth_file or AUTH_FILE
    config_dir = auth_file.parent

    try:
        config_dir.mkdir(exist_ok=True)
        with open(auth_file, "w") as f:
            json.dump(auth_data, f)
        logger.info(f"Saved auth data for user: {auth_data.get('email', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Error saving auth data: {e}")
        return False


def clear_auth_data(auth_file=None):
    """
    Clear auth data from local file

    Args:
        auth_file: Optional Path object for the auth file, defaults to AUTH_FILE from constants
    """
    auth_file = auth_file or AUTH_FILE

    try:
        if auth_file.exists():
            auth_file.unlink()
        logger.info("Cleared auth data")
        return True
    except Exception as e:
        logger.error(f"Error clearing auth data: {e}")
        return False
