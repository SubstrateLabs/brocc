import os


def get_api_url() -> str:
    return os.environ.get("API_URL", "https://brocc.li/api")
