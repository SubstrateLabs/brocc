from pathlib import Path

from platformdirs import user_config_dir

CONFIG_DIR = Path(user_config_dir("brocc"))
AUTH_FILE = CONFIG_DIR / "auth.json"
