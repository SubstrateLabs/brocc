import logging
import os
from io import BytesIO
from typing import Any, Dict, List, Optional

from unstructured.chunking.title import chunk_by_title
from unstructured.documents.elements import Image
from unstructured.partition.md import partition_md

# Set up logger
logger = logging.getLogger(__name__)


def chunk_markdown(
    markdown_text: str,
    max_characters: Optional[int] = 3000,
    new_after_n_chars: Optional[int] = 2000,
    combine_text_under_n_chars: Optional[int] = None,
    base_path: Optional[str] = None,
) -> List[List[Dict[str, Any]]]:
    """
    Chunks markdown content using unstructured's by_title strategy, then formats each chunk
    with text and image segments for voyage.py embedding.

    Parameters
    ----------
    markdown_text : str
        The markdown text to chunk
    max_characters : Optional[int]
        Maximum number of characters per chunk (None for no limit)
        Default is 3000 (~1000 tokens), approximately one page of text or ~600 words
        This is the hard maximum - no chunk will exceed this size
    new_after_n_chars : Optional[int]
        Create a new chunk after this many characters (None for no limit)
        Default is 2000 (~2/3 of a page or ~400 words), a soft limit below max_characters
        This implements the principle: "I prefer chunks of around 2/3 page, but I'd rather
        have a chunk of 1 full page than resort to text-splitting"
    combine_text_under_n_chars : Optional[int]
        Combine chunks under this character count with adjacent chunks (None for default)
        If None, it will be set to min(max_characters, 1500)
        Size reference: ~half a page of text or ~300 words
    base_path : Optional[str]
        Base directory path to resolve relative image paths against.
        If None, local image paths will be kept as-is.

    Returns
    -------
    List[List[Dict[str, Any]]]
        A list of chunks, where each chunk is a list containing:
        - Text items: {"type": "text", "text": "content"}
        - Image items: {"type": "image_url", "image_url": "url"}
        - If a chunk has no images, it will be a single-item list with just text
        - If a chunk has images, it will be a multi-item list with text and images
    """
    # Skip empty markdown
    if not markdown_text.strip():
        return []

    # Set combine_text_under_n_chars to a valid value if None
    if combine_text_under_n_chars is None:
        if max_characters is None:
            combine_text_under_n_chars = 1500
        else:
            combine_text_under_n_chars = min(max_characters, 1500)
    else:
        # Ensure combine_text_under_n_chars doesn't exceed max_characters
        if max_characters is not None and combine_text_under_n_chars > max_characters:
            combine_text_under_n_chars = max_characters

    # Convert text to a file-like object for unstructured
    text_bytes = markdown_text.encode("utf-8")
    text_file = BytesIO(text_bytes)

    # Use unstructured to partition the markdown into elements
    elements = partition_md(file=text_file)

    # Always use unstructured's chunk_by_title function
    chunks = chunk_by_title(
        elements=elements,
        max_characters=max_characters,
        new_after_n_chars=new_after_n_chars,
        combine_text_under_n_chars=combine_text_under_n_chars,
    )

    # Final list of results to return
    result_chunks = []

    # Process each chunk from unstructured
    for chunk in chunks:
        # Check if this chunk contains any image elements in the original elements
        orig_elements = []
        if (
            hasattr(chunk, "metadata")
            and hasattr(chunk.metadata, "orig_elements")
            and chunk.metadata.orig_elements
        ):
            orig_elements = chunk.metadata.orig_elements
            chunk_has_images = any(isinstance(element, Image) for element in orig_elements)
        else:
            chunk_has_images = False

        if chunk_has_images and orig_elements:
            # Process this chunk to handle both text and image elements
            voyage_items = []
            current_text = ""

            for element in orig_elements:
                if isinstance(element, Image):
                    # If we have accumulated text, add it first
                    if current_text:
                        voyage_items.append({"type": "text", "text": current_text.strip()})
                        current_text = ""

                    # Add image element - safely extracting URL
                    image_url = None
                    if hasattr(element, "metadata") and element.metadata:
                        if hasattr(element.metadata, "image_url"):
                            image_url = element.metadata.image_url
                        elif isinstance(element.metadata, dict) and "image_url" in element.metadata:
                            image_url = element.metadata["image_url"]

                        # Resolve local paths if base_path is provided
                        if base_path and isinstance(image_url, str):
                            if image_url.startswith("/"):
                                # Absolute path from root, join with base_path
                                resolved_path = os.path.join(base_path, image_url.lstrip("/"))
                                logger.debug(f"Resolved local path: {image_url} -> {resolved_path}")
                                image_url = resolved_path
                            elif image_url.startswith("./"):
                                # Relative path, join with base_path
                                resolved_path = os.path.join(base_path, image_url[2:])
                                logger.debug(
                                    f"Resolved relative path: {image_url} -> {resolved_path}"
                                )
                                image_url = resolved_path
                            # Skip other URLs (e.g., http://, https://)

                        voyage_items.append({"type": "image_url", "image_url": image_url})
                else:
                    # Accumulate text
                    if hasattr(element, "text"):
                        current_text += element.text + "\n\n"

            # Add any remaining text
            if current_text:
                voyage_items.append({"type": "text", "text": current_text.strip()})

            # Add this chunk's items to the result if it has content
            if voyage_items:
                result_chunks.append(voyage_items)
        else:
            # No images, just add as a single text item
            result_chunks.append([{"type": "text", "text": chunk.text}])

    return result_chunks
