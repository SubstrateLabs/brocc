from typing import Dict, List, Optional

from unstructured.documents.elements import Element, Image
from unstructured.partition.html import partition_html

from brocc_li.utils.logger import logger

# Noise patterns specific to Bluesky followers pages
BSKY_NOISE_PATTERNS = [
    "Sign in",
    "Create account",
    "Home",
    "My Network",
    "Go back",
    "Privacy",
    "Terms",
    "Help",
    "Search",
    "Trending",
    "Join the conversation",
]


def _debug_element_details(element: Element, prefix: str = "") -> None:
    """Helper to debug print element details"""
    metadata = getattr(element, "metadata", None)
    logger.debug(f"{prefix}  Type: {type(element).__name__}")
    if metadata:
        # Print link-related metadata if present
        link_texts = getattr(metadata, "link_texts", [])
        link_urls = getattr(metadata, "link_urls", [])
        if link_texts or link_urls:
            logger.debug(f"{prefix}  Links:")
            for i, (text, url) in enumerate(zip(link_texts or [], link_urls or [], strict=False)):
                logger.debug(f"{prefix}    {i + 1}. Text: {text}")
                logger.debug(f"{prefix}       URL: {url}")

        # Print other potentially useful metadata like tag
        tag = getattr(metadata, "tag", None)
        if tag:
            logger.debug(f"{prefix}  Tag: {tag}")


def is_element_noisy(element: Element, noise_patterns: List[str], debug: bool = False) -> bool:
    """Check if element should be filtered out as noise."""
    element_text = str(element).strip()

    # Apply initial filtering based on text content
    for pattern in noise_patterns:
        if pattern.lower() in element_text.lower():
            if debug:
                logger.debug(
                    f"Filtering noisy element: '{element_text[:50]}...' (matched pattern: '{pattern}')"
                )
            return True

    # Filter out very short elements with no useful content
    if len(element_text) < 3 and not extract_profile_url(element):
        if debug:
            logger.debug(f"Filtering short element: '{element_text}'")
        return True

    return False


def extract_profile_url(element: Element) -> Optional[str]:
    """
    Extract a profile URL from an element if present.
    Returns None if no URL is found or if it's not a profile URL.
    """
    # Check if the element has link metadata
    metadata = getattr(element, "metadata", None)
    if not metadata:
        return None

    # Check if there are link URLs in the metadata
    link_urls = getattr(metadata, "link_urls", [])
    if not link_urls:
        return None

    # For Bluesky, profile URLs start with /profile/
    for url in link_urls:
        if url and "/profile/" in url:
            # Full URL format: https://bsky.app/profile/username.bsky.social
            # We only need the path part
            return url

    return None


def extract_profiles_from_elements(elements: List[Element], debug: bool = False) -> List[Dict]:
    """
    Extract profile information from the list of filtered elements.
    Looks for patterns of name, handle, bio in sequence.
    Returns a list of dictionaries with name, handle, bio, and URL.
    """
    profiles = []
    i = 0

    if debug:
        logger.debug(f"Starting profile extraction from {len(elements)} filtered elements")

    # Group elements by threes (name, handle, bio) where possible
    while i < len(elements) - 1:  # Need at least name + handle
        # Get current element as potential name
        name_element = elements[i]
        name_text = str(name_element).strip()

        # Check if next element looks like a handle (starts with @ or contains @)
        if i + 1 < len(elements):
            handle_element = elements[i + 1]
            handle_text = str(handle_element).strip()

            # Check if it looks like a handle
            is_handle = (
                "‪@" in handle_text
                or "@" in handle_text
                or handle_text.endswith(".bsky.social")
                or handle_text.endswith(".com")
            )

            if is_handle:
                # Found a name+handle pair
                if debug:
                    logger.debug(f"Found name+handle pair: '{name_text}' + '{handle_text}'")

                # Extract profile URL from name element if available
                profile_url = extract_profile_url(name_element)

                # If name element doesn't have URL, try handle element
                if not profile_url:
                    profile_url = extract_profile_url(handle_element)

                # Prepare handle: strip unicode directional marks, ensure it starts with @
                clean_handle = (
                    handle_text.replace("\u202a", "")
                    .replace("\u202c", "")
                    .replace("‪", "")
                    .replace("‬", "")
                    .strip()
                )
                if not clean_handle.startswith("@") and "." in clean_handle:
                    clean_handle = f"@{clean_handle}"

                # Create profile with name and handle
                profile = {
                    "name": name_text,
                    "handle": clean_handle,
                    "bio": None,
                    "url": profile_url,
                }

                # Check for bio (element after handle)
                if i + 2 < len(elements):
                    bio_element = elements[i + 2]
                    bio_text = str(bio_element).strip()

                    # If next element isn't another name+handle pair, it's probably a bio
                    next_pair = False
                    if i + 3 < len(elements):
                        potential_handle = str(elements[i + 3]).strip()
                        if "‪@" in potential_handle or "@" in potential_handle:
                            next_pair = True

                    # Check if it looks like a bio (longer text, not a handle)
                    if (
                        len(bio_text) > 10
                        and not bio_text.startswith("@")
                        and "‪@" not in bio_text
                        and not next_pair
                    ):
                        profile["bio"] = bio_text
                        if debug:
                            logger.debug(f"Found bio for {name_text}: '{bio_text[:50]}...'")
                        i += 3  # Skip name, handle, and bio
                    else:
                        if debug:
                            logger.debug(f"No bio found for {name_text}")
                        i += 2  # Skip just name and handle
                else:
                    i += 2  # Skip just name and handle

                profiles.append(profile)
            else:
                # Not a handle, move to next element
                i += 1
        else:
            # End of list
            i += 1

    if debug:
        logger.debug(f"Extracted {len(profiles)} profiles using pattern matching")

    # Add profile URLs where missing but handle exists
    for profile in profiles:
        if not profile["url"] and profile["handle"]:
            # Extract handle without @ for URL
            handle_for_url = profile["handle"].lstrip("@")
            profile["url"] = f"/profile/{handle_for_url}"
            if debug:
                logger.debug(f"Added constructed URL for {profile['name']}: {profile['url']}")

    return profiles


def format_user_markdown_header(
    name: Optional[str],
    handle: Optional[str],
    profile_url: Optional[str] = None,
    debug: bool = False,
) -> str:
    """
    Format user name and handle into a markdown header with link if URL is provided.
    """
    if debug:
        logger.debug(f"Formatting header for Name: {name}, Handle: {handle}, URL: {profile_url}")

    parts = []
    display_name = name if name else handle
    if not display_name:
        return "### [Unknown User]"

    # Clean display name for link text (take first line, strip whitespace and Unicode control chars)
    link_text = display_name.split("\n")[0].strip()
    link_text = (
        link_text.replace("\u202a", "")
        .replace("\u202c", "")
        .replace("‪", "")
        .replace("‬", "")
        .strip()
    )

    if not link_text:
        return "### [Invalid User Profile]"

    if profile_url:
        # Full URL is constructed using the relative profile URL
        full_url = f"https://bsky.app{profile_url}" if profile_url.startswith("/") else profile_url
        parts.append(f"### [{link_text}]({full_url})")
    else:
        parts.append(f"### {link_text}")

    if handle:
        # Clean handle and ensure it starts with @
        cleaned_handle = (
            handle.replace("\u202a", "")
            .replace("\u202c", "")
            .replace("‪", "")
            .replace("‬", "")
            .strip()
        )
        if not cleaned_handle.startswith("@") and "." in cleaned_handle:
            cleaned_handle = f"@{cleaned_handle}"
        parts.append(f"({cleaned_handle})")

    return " ".join(parts)


def bsky_followers_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Convert Bluesky followers HTML to markdown using unstructured.

    Args:
        html: Raw HTML of Bluesky followers page
        debug: Enable debug output

    Returns:
        Markdown string or None if parsing failed
    """
    try:
        if debug:
            logger.debug("--- Starting Bluesky HTML to Markdown Conversion with unstructured ---")

        # Partition the HTML using unstructured
        elements: List[Element] = partition_html(text=html)

        if debug:
            logger.debug(f"unstructured found {len(elements)} raw elements")
            # Log sample of raw elements
            for i, element in enumerate(elements[:20]):  # Show first 20 for debugging
                element_text = str(element).strip()
                logger.debug(
                    f"Raw Element {i + 1}: {element_text[:70]}{'...' if len(element_text) > 70 else ''}"
                )
                _debug_element_details(element, prefix="  ")

            if len(elements) > 20:
                logger.debug(f"... and {len(elements) - 20} more raw elements")

        if not elements:
            logger.warning("unstructured.partition_html returned no elements")
            return "<!-- unstructured found no elements -->"

        # --- Filter out noise --- #
        filtered_elements = []
        seen_texts = set()  # For basic duplicate detection

        for element in elements:
            element_text = str(element).strip()
            if not element_text:
                continue

            # Skip duplicates
            if element_text in seen_texts:
                if debug:
                    logger.debug(f"Skipping duplicate: {element_text[:30]}...")
                continue

            # Skip images
            if isinstance(element, Image):
                if debug:
                    img_alt = getattr(element.metadata, "alt_text", "No alt text")
                    logger.debug(f"Skipping image element. Alt text: {img_alt}")
                continue

            # Filter out noise
            if is_element_noisy(element, BSKY_NOISE_PATTERNS, debug=debug):
                continue

            filtered_elements.append(element)
            seen_texts.add(element_text)

        if debug:
            logger.debug(f"After filtering, {len(filtered_elements)} elements remain")
            # Log sample of filtered elements
            for i, element in enumerate(filtered_elements[:20]):
                element_text = str(element).strip()
                logger.debug(
                    f"Filtered Element {i + 1}: {element_text[:70]}{'...' if len(element_text) > 70 else ''}"
                )
                _debug_element_details(element, prefix="  ")

        if not filtered_elements:
            logger.warning("No elements remaining after filtering noise")
            return "<!-- No elements remaining after filtering noise -->"

        # --- Extract profiles --- #
        profiles = extract_profiles_from_elements(filtered_elements, debug=debug)

        if not profiles:
            logger.warning("No profiles found in the filtered elements")
            return "<!-- No profiles found in filtered elements -->"

        # --- Build markdown --- #
        markdown_parts = []

        for profile in profiles:
            # Format the profile header with link
            header = format_user_markdown_header(
                name=profile["name"],
                handle=profile["handle"],
                profile_url=profile["url"],
                debug=debug,
            )
            markdown_parts.append(header)

            # Add bio if available
            if profile["bio"]:
                markdown_parts.append(profile["bio"])

            # Add empty line between profiles
            markdown_parts.append("")

        result = "\n\n".join(markdown_parts).strip()

        if debug:
            logger.debug(f"Generated markdown with {len(profiles)} profiles, {len(result)} chars")
            logger.debug("--- Finished Bluesky HTML to Markdown Conversion ---")

        return result

    except Exception as e:
        logger.error(f"Error processing Bluesky Followers HTML: {str(e)}", exc_info=True)
        return f"Error processing Bluesky Followers HTML: {str(e)}"
