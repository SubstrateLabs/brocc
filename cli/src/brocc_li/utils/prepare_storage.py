"""
Utility functions for storing document chunks.
"""

import json
from datetime import datetime
from typing import Any, Dict

from brocc_li.embed.chunk_header import chunk_header
from brocc_li.embed.voyage import ContentType
from brocc_li.types.doc import Chunk, Doc
from brocc_li.utils.geolocation import geolocation_tuple_to_wkt
from brocc_li.utils.logger import logger


def prepare_chunk_for_storage(chunk: Chunk) -> Dict[str, Any]:
    """
    Prepare a Chunk object for DuckDB storage.

    This function handles the DuckDB-specific preparation of chunks, which differs from
    LanceDB preparation in that it:
    1. Stores the content field directly as a JSON string
    2. Does not include document metadata
    3. Does not add a header to the content

    Args:
        chunk: The Chunk object to prepare

    Returns:
        Dict[str, Any]: The prepared chunk as a dictionary
    """
    # Convert to dictionary
    prepared_chunk = chunk.model_dump()

    # Convert content to JSON string if it's not already
    if prepared_chunk.get("content"):
        prepared_chunk["content"] = json.dumps(prepared_chunk["content"])
    else:
        prepared_chunk["content"] = "[]"

    return prepared_chunk


def prepare_structured_content_for_lance(chunk: Chunk, doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare structured content for LanceDB storage with document metadata.

    This function creates a structured content object that includes:
    1. A header with document metadata
    2. The chunk content with proper content type annotations

    Args:
        chunk: The Chunk object to prepare
        doc: The document dictionary containing metadata

    Returns:
        Dict[str, Any]: A structured content dictionary for LanceDB
    """
    # Create Doc object from dictionary
    doc_obj = Doc(**doc)
    header = chunk_header(doc_obj)

    # Initialize multimodal content structure
    structured_content = {"content": []}

    # Add header as text type
    structured_content["content"].append({"type": ContentType.TEXT, "text": header})

    # Process each content item from the chunk
    for item in chunk.content:
        content_type = item.get("type")
        if content_type == "text" and "text" in item:
            structured_content["content"].append({"type": ContentType.TEXT, "text": item["text"]})
        elif content_type == "image_url" and "image_url" in item:
            structured_content["content"].append(
                {"type": ContentType.IMAGE_URL, "image_url": item["image_url"]}
            )

    return structured_content


def prepare_lance_chunk_row(chunk: Chunk, doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare a complete chunk row for LanceDB storage.

    This function combines chunk data with document metadata and structured content
    to create a complete row for LanceDB storage. It:
    1. Extracts base document fields for filtering
    2. Prepares structured content with header
    3. Combines chunk fields with document fields

    Args:
        chunk: The Chunk object to prepare
        doc: The document dictionary containing metadata

    Returns:
        Dict[str, Any]: A complete row dictionary for LanceDB storage
    """
    from brocc_li.types.doc import BaseDocFields

    # Prepare structured content with header
    structured_content = prepare_structured_content_for_lance(chunk, doc)

    # Get chunk fields
    chunk_dict = chunk.model_dump()

    # Extract base document fields for filtering
    doc_fields = BaseDocFields.extract_base_fields(doc)

    # Combine all fields
    row = {
        **chunk_dict,  # Basic chunk fields (id, doc_id, chunk_index, etc.)
        **doc_fields,  # Document metadata fields
        "content": json.dumps(structured_content),  # Store content as a serialized string
    }

    return row


# Constants for document preparation
ARRAY_FIELDS = ["participant_names", "participant_identifiers", "keywords"]
JSON_FIELDS = {"metadata": {}, "contact_metadata": {}, "participant_metadatas": []}
EXCLUDED_FIELDS = {"text_content"}  # text_content gets split into chunks
SPECIAL_HANDLING_FIELDS = {"geolocation"}


def prepare_document_for_storage(document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate, format, and prepare a document dictionary for database storage.

    Args:
        document: The document dictionary to prepare

    Returns:
        Dict[str, Any]: The prepared document as a dictionary
    """
    # Create a copy to avoid modifying the original input dict
    doc_data = document.copy()

    # Ensure ingested_at is set *before* validation if not provided
    if "ingested_at" not in doc_data or not doc_data["ingested_at"]:
        doc_data["ingested_at"] = Doc.format_date(datetime.now())

    # text_content will be handled separately in store_document, no need to validate it here
    text_content = doc_data.pop("text_content", None)
    location_tuple = doc_data.pop("geolocation", None)  # Extract location tuple

    # Validate against the Pydantic model
    try:
        # Create a new doc without text_content for validation
        doc = Doc(**doc_data)
        prepared_doc = doc.model_dump()
    except Exception as e:
        # Consider logging the actual error and invalid data here
        logger.warning(f"Validation Error: {e}\nData: {doc_data}")  # Temp print
        raise ValueError(f"Invalid document structure: {str(e)}") from e

    # Add/Update timestamps *after* validation
    prepared_doc["last_updated"] = Doc.format_date(datetime.now())

    # Add back text_content if it was provided (will be removed later during insert/update)
    if text_content is not None:
        prepared_doc["text_content"] = text_content

    # Convert enum values to strings
    for key, value in prepared_doc.items():
        # Check if it has a 'value' attribute common to Enums
        if hasattr(value, "value") and isinstance(value.value, (str, int, float)):
            prepared_doc[key] = value.value

    # Ensure array fields are None for empty lists if the column type is ARRAY
    # This helps DuckDB store them properly as VARCHAR[] types
    for field in ARRAY_FIELDS:
        if prepared_doc.get(field) == []:
            prepared_doc[field] = None  # For VARCHAR[]

    # Initialize keywords if it doesn't exist
    if "keywords" not in prepared_doc:
        prepared_doc["keywords"] = None

    # Convert metadata fields to JSON strings
    for field in JSON_FIELDS:
        prepared_doc[field] = json.dumps(prepared_doc.get(field) or JSON_FIELDS[field])

    # Format location for DuckDB ST_Point using utility function
    prepared_doc["geolocation"] = geolocation_tuple_to_wkt(location_tuple)

    # Remove fields from prepared_doc that are not actual table columns
    # Get table columns dynamically (excluding computed fields if any, though Doc doesn't have them)
    # For now, use model_fields + last_updated + location
    valid_db_keys = set(Doc.model_fields.keys()) | {"last_updated"} | SPECIAL_HANDLING_FIELDS
    final_db_doc = {k: v for k, v in prepared_doc.items() if k in valid_db_keys}

    return final_db_doc
