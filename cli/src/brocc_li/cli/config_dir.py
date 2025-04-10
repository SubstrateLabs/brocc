from pathlib import Path

from platformdirs import user_config_dir

CONFIG_DIR_NAME = "brocc"


def get_config_dir() -> Path:
    """Get the application's configuration directory path."""
    config_dir = Path(user_config_dir(CONFIG_DIR_NAME))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir
