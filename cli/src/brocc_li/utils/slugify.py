import re


def slugify(text: str | None, max_length: int = 150) -> str:
    """Convert text to a URL and filename safe slug.

    Args:
        text: The text to slugify
        max_length: The maximum length of the slug

    Returns:
        A URL-safe version of the text
    """
    if not text:
        return "unknown"

    # Basic encoding
    encoded = (
        text.lower()
        .replace(" ", "-")
        .replace("_", "-")
        .replace("/", "-")
        .replace("?", "-")
        .replace("=", "-")
        .replace("&", "-")
        .replace(".", "-")
    )

    # Remove all non-alphanum except dashes
    encoded = re.sub(r"[^a-z0-9-]", "", encoded)

    # Collapse multiple dashes into single dash
    encoded = re.sub(r"-+", "-", encoded)

    # Truncate
    return encoded[:max_length] or "unknown"
