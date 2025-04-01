from datetime import datetime
import re
from typing import Optional, Any


# Use ISO format for all timestamps
def format_datetime(dt: datetime) -> str:
    """Format datetime in ISO format with timezone."""
    return dt.isoformat()


# Human-readable format with time precision
READABLE_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# For parsing text dates (like "January 15, 2023" or "JAN 15")
DATE_PATTERN = r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{1,2})(?:,\s+(\d{4}))?"

MONTH_MAP = {
    "JAN": "JANUARY",
    "FEB": "FEBRUARY",
    "MAR": "MARCH",
    "APR": "APRIL",
    "MAY": "MAY",
    "JUN": "JUNE",
    "JUL": "JULY",
    "AUG": "AUGUST",
    "SEP": "SEPTEMBER",
    "OCT": "OCTOBER",
    "NOV": "NOVEMBER",
    "DEC": "DECEMBER",
}


def _parse_iso_date(date_string: str) -> Optional[datetime]:
    """Parse ISO format dates (like those from Twitter)."""
    if not date_string:
        return None

    try:
        # Handle Twitter-style ISO dates
        if "T" in date_string:
            return datetime.fromisoformat(date_string.replace("Z", "+00:00"))
        return None
    except (ValueError, TypeError):
        return None


def _parse_text_date(text: str) -> Optional[datetime]:
    """Parse date from text format (like Substack dates)."""
    if not text:
        return None

    match = re.search(DATE_PATTERN, text, re.IGNORECASE)
    if not match:
        return None

    month, day, year = match.groups()
    current_year = datetime.now().year
    year = int(year) if year else current_year
    month = MONTH_MAP.get(month.upper(), month.upper())

    try:
        return datetime.strptime(f"{month} {day} {year}", "%B %d %Y")
    except ValueError:
        return None


def parse_and_format_date(date_input: Any) -> str:
    """Parse a date from various formats and return it formatted consistently in ISO format.

    Args:
        date_input: The input date (string, datetime, etc)

    Returns:
        A formatted date string or empty string if parsing fails
    """
    # If it's already a datetime
    if isinstance(date_input, datetime):
        return format_datetime(date_input)

    # If it's not a string, try to convert it
    if not isinstance(date_input, str):
        date_input = str(date_input)

    # Skip empty inputs
    if not date_input:
        return ""

    # Clean the input string
    date_string = date_input.strip()

    # Try ISO format first (Twitter)
    dt = _parse_iso_date(date_string)
    if dt:
        return format_datetime(dt)

    # Try text format (Substack)
    dt = _parse_text_date(date_string)
    if dt:
        return format_datetime(dt)

    # Return empty string for unparseable inputs
    return ""


def parse_timestamp(raw_timestamp: Any) -> str:
    """Parse a timestamp for use in schema transform functions.

    This is designed to be used directly in the SchemaField transform parameter
    to standardize timestamp parsing at the schema extraction layer.

    Args:
        raw_timestamp: The raw timestamp string from scraping

    Returns:
        A formatted date string or empty string if parsing fails
    """
    return parse_and_format_date(raw_timestamp)
