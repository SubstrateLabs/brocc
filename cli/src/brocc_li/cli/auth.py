from brocc_li.utils.auth_data import clear_auth_data
from brocc_li.utils.logger import logger


def logout():
    """
    Handle logout

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        clear_auth_data()
        return True
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        return False
