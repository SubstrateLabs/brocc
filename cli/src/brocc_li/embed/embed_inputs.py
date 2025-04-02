from typing import Any, Dict, List

from markdown_it import MarkdownIt

from brocc_li.types.doc import Doc


def embed_header(doc: Doc) -> str:
    """Create a formatted header string with relevant metadata from a Doc."""
    components = []

    # Add title if available
    if doc.title:
        components.append(f"Title: {doc.title}")

    # Add description if available
    if doc.description:
        components.append(f"Description: {doc.description}")

    # Add source information
    components.append(f"Source: {doc.source.value}")
    components.append(f"Source Type: {doc.source_type.value}")

    # Add URL if available
    if doc.url:
        components.append(f"URL: {doc.url}")

    # Add contact information if available
    if doc.contact_name:
        components.append(f"Contact: {doc.contact_name}")

    if doc.contact_identifier:
        components.append(f"Contact ID: {doc.contact_identifier}")

    # Add participant information if available
    if doc.participant_names:
        components.append(f"Participants: {', '.join(doc.participant_names)}")

    # Add source location name if available
    if doc.source_location_name:
        components.append(f"Source Location: {doc.source_location_name}")

    # Add keywords if available
    if doc.keywords:
        components.append(f"Keywords: {', '.join(doc.keywords)}")

    # Add metadata if available
    if doc.metadata:
        # Format metadata as key-value pairs
        metadata_str = ", ".join(f"{k}: {v}" for k, v in doc.metadata.items())
        components.append(f"Metadata: {metadata_str}")

    # Join with newlines
    return "\n".join(components)


def extract_images_with_positions(markdown_text: str) -> List[Dict[str, Any]]:
    """
    Extract image positions from markdown text using markdown-it-py.

    Returns a list of dicts with 'start', 'end', and 'url' keys.
    """
    md = MarkdownIt()
    tokens = md.parse(markdown_text)
    images = []

    # Helper function to collect image tokens and their positions
    def process_token(token, in_text):
        # Process direct image tokens
        if token.type == "image":
            if hasattr(token, "attrs") and token.attrs and "src" in token.attrs:
                # Find the position in the original markdown
                image_markup = f"![{token.content}]({token.attrs['src']})"
                start = in_text.find(image_markup)
                if start >= 0:
                    images.append(
                        {
                            "start": start,
                            "end": start + len(image_markup),
                            "url": token.attrs["src"],
                        }
                    )

        # Process inline tokens (which might contain images)
        elif token.type == "inline" and hasattr(token, "children"):
            for child in token.children:
                if (
                    child.type == "image"
                    and hasattr(child, "attrs")
                    and child.attrs
                    and "src" in child.attrs
                ):
                    # The child token will have the image URL
                    image_markup = f"![{child.content}]({child.attrs['src']})"
                    start = in_text.find(image_markup)
                    if start >= 0:
                        images.append(
                            {
                                "start": start,
                                "end": start + len(image_markup),
                                "url": child.attrs["src"],
                            }
                        )

    # Process all tokens
    for token in tokens:
        process_token(token, markdown_text)

    # Sort the images by their position in the text
    return sorted(images, key=lambda x: x["start"])


def split_markdown(markdown_text: str) -> List[Dict[str, Any]]:
    """
    Split markdown content into text and image segments.

    Parameters
    ----------
    markdown_text : str
        Markdown text to parse

    Returns
    -------
    List[Dict[str, Any]]
        List of segments, where each segment is either:
        - {"type": "text", "text": "content"} for text segments
        - {"type": "image_url", "image_url": "url"} for image segments
    """
    # If there's no markdown image syntax, return the whole text as one segment
    if "![" not in markdown_text:
        return [{"type": "text", "text": markdown_text}]

    # Get all images with their positions in the text
    images = extract_images_with_positions(markdown_text)

    # No images found by the parser
    if not images:
        return [{"type": "text", "text": markdown_text}]

    # Split the text using the image positions
    segments = []
    last_pos = 0

    for img in images:
        # Add text segment before the image (if any)
        if img["start"] > last_pos:
            text_content = markdown_text[last_pos : img["start"]].strip()
            if text_content:
                segments.append({"type": "text", "text": text_content})

        # Add the image segment
        segments.append({"type": "image_url", "image_url": img["url"]})

        # Update last position
        last_pos = img["end"]

    # Add any remaining text after the last image
    if last_pos < len(markdown_text):
        text_content = markdown_text[last_pos:].strip()
        if text_content:
            segments.append({"type": "text", "text": text_content})

    return segments
