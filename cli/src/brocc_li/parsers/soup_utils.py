import re
from typing import List, Optional

import dateparser
from bs4 import BeautifulSoup, Tag
from rich.markup import escape

from brocc_li.utils.logger import logger


def extract_date_from_element(element: Tag, debug: bool = False) -> Optional[str]:
    """
    Extract date information from a BeautifulSoup element with multiple fallback strategies.
    Works with various date formats commonly found in emails and web pages.

    Args:
        element: The BeautifulSoup Tag containing date information
        debug: Whether to output debug information

    Returns:
        Extracted date as string or None if not found
    """
    if not element:
        return None

    # Strategy 1: Look for a span with title attribute (common in Gmail)
    date_span = element.select_one("span[title]")
    if date_span and date_span.get("title"):
        date_title = date_span.get("title")
        if isinstance(date_title, str) and date_title.strip():
            # Try to parse it with dateparser for normalization
            parsed_date = dateparser.parse(date_title.strip())
            if parsed_date:
                formatted_date = parsed_date.strftime("%b %d, %Y")
                if debug:
                    safe_date = escape(formatted_date)
                    logger.debug(f"Date extracted from span title and normalized: {safe_date}")
                return formatted_date
            else:
                if debug:
                    safe_date = escape(str(date_title))
                    logger.debug(f"Date extracted from span title (unparseable): {safe_date}")
                return date_title.strip()
        elif isinstance(date_title, list) and date_title and date_title[0]:
            date_str = str(date_title[0]).strip()
            # Try to parse it with dateparser
            parsed_date = dateparser.parse(date_str)
            if parsed_date:
                formatted_date = parsed_date.strftime("%b %d, %Y")
                if debug:
                    safe_date = escape(formatted_date)
                    logger.debug(f"Date extracted from span title list and normalized: {safe_date}")
                return formatted_date
            else:
                if debug:
                    safe_date = escape(date_str)
                    logger.debug(f"Date extracted from span title list (unparseable): {safe_date}")
                return date_str

    # Strategy 2: Use element text and look for date patterns with dateparser
    element_text = element.get_text(strip=True)
    if not element_text:
        return None

    # First try with regex to extract likely date portions
    # Common date patterns in various formats
    date_patterns = [
        # Month name patterns (Mar 21, March 21, etc)
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:,\s*\d{4})?",
        # Numeric date patterns (MM/DD/YY, DD/MM/YY)
        r"\b\d{1,2}/\d{1,2}/\d{2,4}",
        r"\b\d{1,2}-\d{1,2}-\d{2,4}",
        # ISO-like date patterns (YYYY-MM-DD)
        r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}",
        # Time patterns (maybe date is just a time in the UI)
        r"\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)",
        # Yesterday, Today patterns
        r"\b(?:Today|Yesterday)\b",
        # Relative time patterns
        r"\b\d+\s+(?:minute|hour|day|week|month)s?\s+ago\b",
    ]

    # Try each pattern
    date_candidates = []
    for pattern in date_patterns:
        date_match = re.search(pattern, element_text)
        if date_match:
            date_str = date_match.group(0).strip()
            date_candidates.append(date_str)
            if debug:
                safe_pattern = escape(pattern)
                safe_date = escape(date_str)
                logger.debug(f"Date candidate from pattern {safe_pattern}: {safe_date}")

    # Now try dateparser on each candidate, plus the full text
    date_candidates.append(element_text)  # Add full text as final candidate

    for candidate in date_candidates:
        parsed_date = dateparser.parse(candidate)
        if parsed_date:
            formatted_date = parsed_date.strftime("%b %d, %Y")
            if debug:
                safe_candidate = escape(candidate)
                safe_date = escape(formatted_date)
                logger.debug(
                    f"Date successfully parsed with dateparser: {safe_candidate} -> {safe_date}"
                )
            return formatted_date

    # Strategy 3: Last resort for very short text that might just be a date
    if len(element_text) < 20:
        try:
            parsed_date = dateparser.parse(element_text)
            if parsed_date:
                formatted_date = parsed_date.strftime("%b %d, %Y")
                if debug:
                    safe_text = escape(element_text)
                    safe_date = escape(formatted_date)
                    logger.debug(
                        f"Short text successfully parsed as date: {safe_text} -> {safe_date}"
                    )
                return formatted_date
            else:
                if debug:
                    safe_text = escape(element_text)
                    logger.debug(f"Using short text as date (unparseable): {safe_text}")
                return element_text
        except Exception as e:
            if debug:
                safe_text = escape(element_text)
                safe_error = escape(str(e))
                logger.debug(f"Error parsing date from short text '{safe_text}': {safe_error}")
            return element_text

    # No date pattern recognized
    if debug:
        safe_text = escape(element_text[:50])
        logger.debug(f"No date pattern found in: {safe_text}...")

    return None


def clean_soup_text(text: str, max_whitespace: int = 1) -> str:
    """
    Clean text extracted from BeautifulSoup to normalize whitespace and remove common issues.

    Args:
        text: The text to clean
        max_whitespace: Maximum number of consecutive whitespace characters to allow

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    # Replace special whitespace chars with spaces
    clean = text.replace("\t", " ").replace("\r", " ").replace("\xa0", " ")

    # Normalize line endings
    clean = clean.replace("\n\n\n+", "\n\n").strip()

    # Normalize multiple spaces
    while "  " in clean:
        clean = clean.replace("  ", " ")

    return clean.strip()


def find_largest_container(
    soup: BeautifulSoup, selector: str, fallbacks: Optional[List[str]] = None, debug: bool = False
) -> Optional[Tag]:
    """
    Find the largest container element matching a selector with fallbacks.
    Useful for finding the main content area in various HTML layouts.

    Args:
        soup: The BeautifulSoup object
        selector: CSS selector to look for
        fallbacks: List of fallback selectors if first selector doesn't match
        debug: Whether to output debug information

    Returns:
        The largest matching Tag or None if not found
    """
    selectors = [selector]
    if fallbacks:
        selectors.extend(fallbacks)

    for sel in selectors:
        elements = soup.select(sel)
        if elements:
            valid_elements = [el for el in elements if isinstance(el, Tag)]
            if valid_elements:
                largest = max(valid_elements, key=lambda x: len(str(x)))
                if debug:
                    safe_sel = escape(sel)
                    safe_name = escape(largest.name)
                    logger.debug(f"Found largest container with selector '{safe_sel}': {safe_name}")
                return largest

    if debug:
        safe_selectors = escape(str(selectors))
        logger.debug(f"No containers found with selectors: {safe_selectors}")

    return None


def extract_date_text(text: str) -> Optional[str]:
    """
    Extract and parse date patterns from raw text string using dateparser.
    Useful for cleaning up mixed text that contains date information.

    Args:
        text: Text that might contain date information

    Returns:
        Extracted normalized date as string or None if not found
    """
    if not text:
        return None

    # First try with dateparser directly
    try:
        parsed_date = dateparser.parse(text)
        if parsed_date:
            return parsed_date.strftime("%b %d, %Y")
    except Exception:
        pass

    # If direct parsing fails, try to extract date patterns first
    date_patterns = [
        # Month name patterns
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:,\s*\d{4})?",
        # Numeric dates
        r"\d{1,2}/\d{1,2}/\d{2,4}",
        # ISO-like dates
        r"\d{4}-\d{1,2}-\d{1,2}",
        # Time patterns
        r"\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)",
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            date_str = match.group(0).strip()
            try:
                parsed_date = dateparser.parse(date_str)
                if parsed_date:
                    return parsed_date.strftime("%b %d, %Y")
            except Exception:
                return date_str

    return None


def is_noise_element(element: Tag, noise_patterns: List[str]) -> bool:
    """
    Check if a BeautifulSoup element is likely noise based on patterns.

    Args:
        element: The element to check
        noise_patterns: List of text patterns indicating noise

    Returns:
        True if element is likely noise
    """
    if not element:
        return False

    # Get all text and attributes to check against patterns
    element_text = element.get_text(strip=True).lower()
    element_attrs = " ".join([str(v) for k, v in element.attrs.items()]).lower()

    # Check against noise patterns
    for pattern in noise_patterns:
        pattern_lower = pattern.lower()
        if pattern_lower in element_text or pattern_lower in element_attrs:
            return True

    # Check for common UI patterns
    ui_patterns = ["loading", "progress", "spinner", "advertisement", "cookie", "banner"]
    for ui in ui_patterns:
        if ui in element_text or ui in element_attrs:
            # Check class attribute separately with proper type handling
            if "class" in element.attrs and isinstance(element.attrs["class"], list):
                # Check if any class contains this UI pattern
                if any(ui in cls.lower() for cls in element.attrs["class"]):
                    return True

    return False
