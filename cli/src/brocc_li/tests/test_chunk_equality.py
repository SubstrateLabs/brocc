"""
Tests for the chunk equality utility functions.
"""

import json

from brocc_li.types.doc import Chunk
from brocc_li.utils.chunk_equality import chunks_are_identical
from brocc_li.utils.prepare_storage import prepare_chunk_for_storage


def test_prepare_chunk_for_storage():
    """Test preparing a chunk for storage."""
    # Create a test chunk
    chunk = Chunk(
        id="test-id",
        doc_id="doc-id",
        chunk_index=0,
        chunk_total=1,
        content=[{"type": "text", "text": "Test content"}],
    )

    # Prepare the chunk for storage
    prepared = prepare_chunk_for_storage(chunk)

    # Check that the content is JSON serialized
    assert isinstance(prepared["content"], str)
    assert json.loads(prepared["content"]) == [{"type": "text", "text": "Test content"}]

    # Check that other fields are preserved
    assert prepared["id"] == "test-id"
    assert prepared["doc_id"] == "doc-id"
    assert prepared["chunk_index"] == 0
    assert prepared["chunk_total"] == 1


def test_prepare_chunk_for_storage_empty_content():
    """Test preparing a chunk with empty content for storage."""
    # Create a test chunk with empty content
    chunk = Chunk(
        id="test-id",
        doc_id="doc-id",
        chunk_index=0,
        chunk_total=1,
        content=[],
    )

    # Prepare the chunk for storage
    prepared = prepare_chunk_for_storage(chunk)

    # Check that the content is an empty JSON array string
    assert prepared["content"] == "[]"


def test_chunks_are_identical_same_chunks():
    """Test that identical chunks are correctly identified."""
    # Create test chunks
    chunk1 = Chunk(
        id="chunk1",
        doc_id="doc-id",
        chunk_index=0,
        chunk_total=2,
        content=[{"type": "text", "text": "First chunk"}],
    )
    chunk2 = Chunk(
        id="chunk2",
        doc_id="doc-id",
        chunk_index=1,
        chunk_total=2,
        content=[{"type": "text", "text": "Second chunk"}],
    )
    new_chunks = [chunk1, chunk2]

    # Create existing chunks (as they would be stored in the database)
    existing_chunks = [
        {
            "id": "existing-chunk1",
            "doc_id": "doc-id",
            "chunk_index": 0,
            "chunk_total": 2,
            "content": json.dumps([{"type": "text", "text": "First chunk"}]),
        },
        {
            "id": "existing-chunk2",
            "doc_id": "doc-id",
            "chunk_index": 1,
            "chunk_total": 2,
            "content": json.dumps([{"type": "text", "text": "Second chunk"}]),
        },
    ]

    # Check that the chunks are identified as identical
    assert chunks_are_identical(existing_chunks, new_chunks) is True


def test_chunks_are_identical_different_content():
    """Test that chunks with different content are correctly identified as different."""
    # Create test chunks
    chunk1 = Chunk(
        id="chunk1",
        doc_id="doc-id",
        chunk_index=0,
        chunk_total=2,
        content=[{"type": "text", "text": "First chunk"}],
    )
    chunk2 = Chunk(
        id="chunk2",
        doc_id="doc-id",
        chunk_index=1,
        chunk_total=2,
        content=[{"type": "text", "text": "Second chunk"}],
    )
    new_chunks = [chunk1, chunk2]

    # Create existing chunks with different content
    existing_chunks = [
        {
            "id": "existing-chunk1",
            "doc_id": "doc-id",
            "chunk_index": 0,
            "chunk_total": 2,
            "content": json.dumps([{"type": "text", "text": "Different first chunk"}]),
        },
        {
            "id": "existing-chunk2",
            "doc_id": "doc-id",
            "chunk_index": 1,
            "chunk_total": 2,
            "content": json.dumps([{"type": "text", "text": "Second chunk"}]),
        },
    ]

    # Check that the chunks are identified as different
    assert chunks_are_identical(existing_chunks, new_chunks) is False


def test_chunks_are_identical_different_count():
    """Test that chunks with different counts are correctly identified as different."""
    # Create test chunks
    chunk1 = Chunk(
        id="chunk1",
        doc_id="doc-id",
        chunk_index=0,
        chunk_total=1,
        content=[{"type": "text", "text": "First chunk"}],
    )
    new_chunks = [chunk1]

    # Create existing chunks with different count
    existing_chunks = [
        {
            "id": "existing-chunk1",
            "doc_id": "doc-id",
            "chunk_index": 0,
            "chunk_total": 2,
            "content": json.dumps([{"type": "text", "text": "First chunk"}]),
        },
        {
            "id": "existing-chunk2",
            "doc_id": "doc-id",
            "chunk_index": 1,
            "chunk_total": 2,
            "content": json.dumps([{"type": "text", "text": "Second chunk"}]),
        },
    ]

    # Check that the chunks are identified as different
    assert chunks_are_identical(existing_chunks, new_chunks) is False


def test_chunks_are_identical_different_index():
    """Test that chunks with different indices are correctly identified as different."""
    # Create test chunks
    chunk1 = Chunk(
        id="chunk1",
        doc_id="doc-id",
        chunk_index=0,
        chunk_total=2,
        content=[{"type": "text", "text": "First chunk"}],
    )
    chunk2 = Chunk(
        id="chunk2",
        doc_id="doc-id",
        chunk_index=1,
        chunk_total=2,
        content=[{"type": "text", "text": "Second chunk"}],
    )
    new_chunks = [chunk1, chunk2]

    # Create existing chunks with different indices
    existing_chunks = [
        {
            "id": "existing-chunk1",
            "doc_id": "doc-id",
            "chunk_index": 0,
            "chunk_total": 2,
            "content": json.dumps([{"type": "text", "text": "First chunk"}]),
        },
        {
            "id": "existing-chunk2",
            "doc_id": "doc-id",
            "chunk_index": 2,  # Different index
            "chunk_total": 2,
            "content": json.dumps([{"type": "text", "text": "Second chunk"}]),
        },
    ]

    # Check that the chunks are identified as different
    assert chunks_are_identical(existing_chunks, new_chunks) is False


def test_chunks_are_identical_string_index():
    """Test that chunks with string indices are handled correctly."""
    # Create test chunks
    chunk1 = Chunk(
        id="chunk1",
        doc_id="doc-id",
        chunk_index=0,
        chunk_total=2,
        content=[{"type": "text", "text": "First chunk"}],
    )
    chunk2 = Chunk(
        id="chunk2",
        doc_id="doc-id",
        chunk_index=1,
        chunk_total=2,
        content=[{"type": "text", "text": "Second chunk"}],
    )
    new_chunks = [chunk1, chunk2]

    # Create existing chunks with string indices
    existing_chunks = [
        {
            "id": "existing-chunk1",
            "doc_id": "doc-id",
            "chunk_index": "0",  # String index
            "chunk_total": 2,
            "content": json.dumps([{"type": "text", "text": "First chunk"}]),
        },
        {
            "id": "existing-chunk2",
            "doc_id": "doc-id",
            "chunk_index": "1",  # String index
            "chunk_total": 2,
            "content": json.dumps([{"type": "text", "text": "Second chunk"}]),
        },
    ]

    # Check that the chunks are identified as identical
    assert chunks_are_identical(existing_chunks, new_chunks) is True


def test_chunks_are_identical_invalid_json():
    """Test that chunks with invalid JSON content are handled correctly."""
    # Create test chunks
    chunk1 = Chunk(
        id="chunk1",
        doc_id="doc-id",
        chunk_index=0,
        chunk_total=1,
        content=[{"type": "text", "text": "First chunk"}],
    )
    new_chunks = [chunk1]

    # Create existing chunks with invalid JSON content
    existing_chunks = [
        {
            "id": "existing-chunk1",
            "doc_id": "doc-id",
            "chunk_index": 0,
            "chunk_total": 1,
            "content": "invalid json",  # Invalid JSON
        },
    ]

    # Check that the chunks are identified as different
    assert chunks_are_identical(existing_chunks, new_chunks) is False
