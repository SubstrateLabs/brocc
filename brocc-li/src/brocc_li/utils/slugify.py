import re
from typing import Optional
import unicodedata


def slugify(text: Optional[str]) -> str:
    """Convert text to a URL and filename safe slug that is reversible.

    Uses rare character sequences to maintain reversibility:
    - '~s~' represents spaces
    - '~{hex}~' represents special characters

    Args:
        text: The text to slugify

    Returns:
        A URL-safe version of the text that can be unslugified
    """
    if not text:
        return "unknown"

    # Convert to lowercase for consistency
    text = text.lower()

    # First, encode any non-alphanumeric chars except hyphens and Unicode letters
    result = ""
    for char in text:
        category = unicodedata.category(char)

        # Keep alphanumerics, hyphens, and Unicode letters
        if char.isalnum() or char == "-" or category.startswith("L"):
            # Safe characters pass through unchanged
            result += char
        elif char == " ":
            # Spaces get a special marker
            result += "~s~"
        else:
            # All other chars get hex encoded
            hex_char = format(ord(char), "x")
            result += f"~{hex_char}~"

    return result or "unknown"


def unslugify(slug: str) -> str:
    """Convert a slug back to a human-readable string.

    Args:
        slug: The slug to convert back

    Returns:
        The original string before slugification
    """
    if not slug or slug == "unknown":
        return ""

    # Replace our space marker with actual spaces
    text = slug.replace("~s~", " ")

    # Replace encoded special characters
    def decode_special(match):
        hex_str = match.group(1)
        try:
            return chr(int(hex_str, 16))
        except ValueError:
            return ""

    # Replace all encoded chars with their original forms
    text = re.sub(r"~([0-9a-f]+)~", decode_special, text)

    return text
