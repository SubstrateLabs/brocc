import re  # Import regex
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from unstructured.documents.elements import Element, Image, Text

from brocc_li.utils.logger import logger


def is_timestamp(element: Element, debug: bool = False) -> bool:
    """
    Check if an element's text matches common Threads time patterns (e.g., 5m, 1h, 2d).

    Args:
        element: The element to check
        debug: Whether to output debug logs

    Returns:
        True if the element appears to be a timestamp
    """
    if not isinstance(element, Text):
        return False
    text = str(element).strip()
    # Regex: digits followed by s, m, h, or d (case-insensitive)
    # Or common phrases like 'now', 'X minutes/hours/days ago'
    # Allow optional space before unit, handle plurals
    pattern = r"^(?:\d+\s?[smhd]|now|\d+\s+(?:second|minute|hour|day)s?\s+ago)$"
    match = re.match(pattern, text, re.IGNORECASE)
    if match and debug:
        logger.debug(f"is_timestamp: Matched '{text}'")
    return bool(match)


def clean_element_text(text: str, max_length: Optional[int] = None) -> str:
    """Clean element text of common noise patterns found in Threads HTML."""
    if not text:
        return ""

    # Remove common noise characters
    cleaned = text.replace("·", "").strip()

    # Truncate if needed
    if max_length and len(cleaned) > max_length:
        return cleaned[:max_length] + "..."

    return cleaned


def is_profile_picture(element: Element) -> bool:
    """Check if an element is a Threads profile picture."""
    return isinstance(element, Image) and (
        "profile picture" in str(element).lower() or "User avatar" in str(element)
    )


def format_timestamp(text: str) -> str:
    """Format a Threads timestamp string consistently."""
    if not text:
        return ""

    # Strip and add parentheses if not already present
    formatted = text.strip()
    if not (formatted.startswith("(") and formatted.endswith(")")):
        formatted = f"({formatted})"

    return formatted


# URL and link detection
def extract_urls(text: str) -> List[str]:
    """Extract URLs from text using regex."""
    # Much stricter URL regex pattern that requires http/https or www prefixes
    url_pattern = r'https?://[^\s\'"<>()]+|www\.[^\s\'"<>().]+'

    # Find all matches
    matches = re.findall(url_pattern, text)

    # Clean up trailing punctuation that might have been included
    cleaned_urls = []
    for match in matches:
        # Remove trailing punctuation that shouldn't be part of the URL
        if match[-1] in ".,;:!?\"'":
            match = match[:-1]
        cleaned_urls.append(match)

    return cleaned_urls


def is_same_url(url1: str, url2: str) -> bool:
    """Check if two URLs point to the same resource, ignoring minor differences."""
    try:
        # Parse both URLs
        parsed1 = urlparse(url1)
        parsed2 = urlparse(url2)

        # Compare netloc and path which are the core parts of the URL
        return parsed1.netloc == parsed2.netloc and parsed1.path == parsed2.path
    except Exception:
        # Fall back to simple string comparison if parsing fails
        return url1 == url2


def normalize_text(text: str) -> str:
    """Normalize text by removing extra whitespace and standardizing formatting."""
    # Replace newlines with spaces and collapse multiple whitespace
    normalized = re.sub(r"\s+", " ", text)
    return normalized.strip()


def clean_username(username: str) -> str:
    """Clean up username text, removing 'profile picture' and similar suffixes."""
    # Remove common suffixes
    for suffix in ["'s profile picture", "'s profile picture'"]:
        if username.endswith(suffix):
            username = username[: -len(suffix)].strip()

    # Remove leading/trailing whitespace and quotes
    username = username.strip("'\"").strip()

    return username


def extract_profile_url(profile_pic_element: Element) -> Optional[str]:
    """Extract profile URL from a profile picture element."""
    if not isinstance(profile_pic_element, Image):
        return None

    # Get the image URL from the metadata
    img_url = getattr(profile_pic_element.metadata, "image_url", None)
    if not img_url:
        return None

    # Parse the URL to extract the username and construct a profile URL
    try:
        # For Instagram CDN URLs, extract username from the element text
        element_text = str(profile_pic_element).strip()
        if "'s profile picture" in element_text:
            username = element_text.replace("'s profile picture", "").strip()
            # Construct a Threads profile URL (format: threads.net/@username)
            return f"https://threads.net/@{username}"
    except Exception:
        pass

    # If we couldn't extract a profile URL, return None (don't use image URL as fallback)
    return None


def format_markdown_links(text: str) -> str:
    """Convert plaintext URLs to Markdown links."""
    urls = extract_urls(text)

    # No URLs found, return original text
    if not urls:
        return text

    # Sort URLs by length (longest first) to avoid replacing substrings of longer URLs
    urls.sort(key=len, reverse=True)

    # Replace each URL with a proper Markdown link
    result = text
    for url in urls:
        # Don't link URLs that are already part of markdown image tags
        if f"![]({url})" in text or "![" in text and f"]({url})" in text:
            continue

        # Create a display text - use the domain name as display text
        domain = urlparse(url).netloc
        display_text = domain if domain else url
        if not display_text:
            display_text = url

        # Truncate display text if too long
        if len(display_text) > 30:
            display_text = display_text[:27] + "..."

        # Replace the plaintext URL with a Markdown link - only if it's actually a URL
        # Use word boundaries to avoid replacing parts of words
        if url.startswith(("http://", "https://", "www.")):
            # Use regex with word boundaries for replacement to avoid partial matches
            pattern = re.escape(url)
            result = re.sub(f"(?<![\"'])({pattern})(?![\"'])", f"[{display_text}]({url})", result)

    return result


def deduplicate_text_blocks(text_candidates: List[str], debug: bool = False) -> List[str]:
    """Deduplicate text blocks, removing smaller subsets of larger text blocks."""
    if not text_candidates:
        return []

    # First normalize all texts and sort by length (longest first)
    normalized_texts = [
        (normalize_text(text), text, len(normalize_text(text)))
        for text in text_candidates
        if text.strip()
    ]
    normalized_texts.sort(key=lambda x: x[2], reverse=True)

    # Only keep texts that aren't substrings of longer texts
    deduplicated = []
    seen_content = set()

    for normalized, original, _ in normalized_texts:
        if normalized in seen_content:
            continue

        # Check if this text is a subset of any already included text
        is_subset = any(normalized in longer for longer in seen_content)

        if not is_subset:
            deduplicated.append(original)
            seen_content.add(normalized)

    return deduplicated


def deduplicate_image_urls(
    image_urls: List[Tuple[str, str]], debug: bool = False
) -> List[Tuple[str, str]]:
    """Deduplicate image URLs based on their core components."""
    if not image_urls:
        return []

    deduplicated = []
    seen_urls = set()

    for alt_text, url in image_urls:
        # Check if this URL points to the same resource as any we've seen
        is_duplicate = any(is_same_url(url, seen_url) for seen_url in seen_urls)

        if not is_duplicate:
            deduplicated.append((alt_text, url))
            seen_urls.add(url)

    return deduplicated


def extract_links_from_metadata(element: Element) -> Optional[str]:
    """
    Extract links from the element's metadata if present.

    Unstructured may preserve link information in element metadata
    (e.g., from original <a href="..."> tags).
    """
    if not hasattr(element, "metadata"):
        return None

    # Check for common link metadata fields
    for field in ["link", "url", "href", "hyperlink"]:
        if hasattr(element.metadata, field):
            url = getattr(element.metadata, field)
            if url and isinstance(url, str):
                return url

    # Some parsers might store metadata as a dict
    if hasattr(element.metadata, "__dict__"):
        metadata_dict = element.metadata.__dict__
        for field in ["link", "url", "href", "hyperlink"]:
            if field in metadata_dict and metadata_dict[field]:
                return metadata_dict[field]

    return None
