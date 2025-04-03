"""
Utility functions for comparing document chunks.
"""

import json
from typing import Any, Dict, List

from brocc_li.types.doc import Chunk
from brocc_li.utils.prepare_storage import prepare_chunk_for_storage


def chunks_are_identical(existing_chunks: List[Dict[str, Any]], new_chunks: List[Chunk]) -> bool:
    """
    Check if the new chunks are identical to the existing DuckDB chunks.

    This function compares new chunks with existing chunks from DuckDB to determine
    if a document update is needed. It does not compare with LanceDB chunks.

    Args:
        existing_chunks: List of existing chunk dictionaries from DuckDB
        new_chunks: List of new Chunk objects to compare

    Returns:
        bool: True if the chunks are identical, False otherwise
    """
    # Quick check - if the number of chunks differs, they're not identical
    if len(existing_chunks) != len(new_chunks):
        return False

    # Create dictionaries of processed chunks for comparison
    existing_processed = {}
    for chunk in existing_chunks:
        idx = (
            int(chunk["chunk_index"])
            if isinstance(chunk["chunk_index"], str)
            else chunk["chunk_index"]
        )
        existing_processed[idx] = chunk["content"]

    # Compare chunks by content
    for chunk in new_chunks:
        chunk_dict = prepare_chunk_for_storage(chunk)
        idx = chunk.chunk_index

        # If the chunk index doesn't exist in existing chunks, they're not identical
        if idx not in existing_processed:
            return False

        # Parse existing content back into a list if it's a string
        existing_content = existing_processed[idx]
        if isinstance(existing_content, str):
            try:
                existing_content = json.loads(existing_content)
            except json.JSONDecodeError:
                existing_content = []

        # Parse new content back into a list if it's a string
        new_content = chunk_dict["content"]
        if isinstance(new_content, str):
            try:
                new_content = json.loads(new_content)
            except json.JSONDecodeError:
                new_content = []

        # Compare the content - if not equal, chunks aren't identical
        if existing_content != new_content:
            return False

    # All checks passed, chunks are identical
    return True
