"""
Tests for the chunk storage utility functions.
"""

import json

from brocc_li.embed.voyage import ContentType
from brocc_li.types.doc import Chunk, Source, SourceType
from brocc_li.utils.prepare_storage import (
    prepare_chunk_for_storage,
    prepare_document_for_storage,
    prepare_lance_chunk_row,
    prepare_structured_content_for_lance,
)


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


def test_prepare_structured_content_for_lance():
    """Test preparing structured content for LanceDB storage."""
    # Create a test chunk
    chunk = Chunk(
        id="test-id",
        doc_id="doc-id",
        chunk_index=0,
        chunk_total=1,
        content=[
            {"type": "text", "text": "Test content"},
            {"type": "image_url", "image_url": "https://example.com/image.jpg"},
        ],
    )

    # Create a test document
    doc = {
        "id": "doc-id",
        "url": "https://example.com",
        "title": "Test Document",
        "description": "A test document",
        "source": Source.TWITTER,
        "source_type": SourceType.DOCUMENT,
        "source_location_identifier": "test-location",
        "participant_names": ["User1", "User2"],
        "participant_identifiers": ["@user1", "@user2"],
        "keywords": ["test", "document"],
        "metadata": {"key": "value"},
        "contact_metadata": {"email": "test@example.com"},
        "participant_metadatas": [{"role": "author"}, {"role": "editor"}],
    }

    # Prepare the structured content
    structured_content = prepare_structured_content_for_lance(chunk, doc)

    # Check that the content has the correct structure
    assert "content" in structured_content
    assert len(structured_content["content"]) == 3  # Header + 2 content items

    # Check that the first item is the header
    assert structured_content["content"][0]["type"] == ContentType.TEXT
    assert "Title: Test Document" in structured_content["content"][0]["text"]
    assert "Source: twitter" in structured_content["content"][0]["text"]

    # Check that the second item is the text content
    assert structured_content["content"][1]["type"] == ContentType.TEXT
    assert structured_content["content"][1]["text"] == "Test content"

    # Check that the third item is the image URL
    assert structured_content["content"][2]["type"] == ContentType.IMAGE_URL
    assert structured_content["content"][2]["image_url"] == "https://example.com/image.jpg"


def test_prepare_structured_content_for_lance_empty_content():
    """Test preparing structured content for LanceDB with empty chunk content."""
    # Create a test chunk with empty content
    chunk = Chunk(
        id="test-id",
        doc_id="doc-id",
        chunk_index=0,
        chunk_total=1,
        content=[],
    )

    # Create a test document
    doc = {
        "id": "doc-id",
        "url": "https://example.com",
        "title": "Test Document",
        "source": Source.TWITTER,
        "source_type": SourceType.DOCUMENT,
    }

    # Prepare the structured content
    structured_content = prepare_structured_content_for_lance(chunk, doc)

    # Check that the content has the correct structure
    assert "content" in structured_content
    assert len(structured_content["content"]) == 1  # Only the header

    # Check that the first item is the header
    assert structured_content["content"][0]["type"] == ContentType.TEXT
    assert "Title: Test Document" in structured_content["content"][0]["text"]
    assert "Source: twitter" in structured_content["content"][0]["text"]


def test_prepare_lance_chunk_row():
    """Test preparing a complete LanceDB chunk row."""
    # Create a test chunk
    chunk = Chunk(
        id="test-id",
        doc_id="doc-id",
        chunk_index=0,
        chunk_total=1,
        content=[
            {"type": "text", "text": "Test content"},
            {"type": "image_url", "image_url": "https://example.com/image.jpg"},
        ],
    )

    # Create a test document
    doc = {
        "id": "doc-id",
        "url": "https://example.com",
        "title": "Test Document",
        "description": "A test document",
        "source": Source.TWITTER,
        "source_type": SourceType.DOCUMENT,
        "source_location_identifier": "test-location",
        "participant_names": ["User1", "User2"],
        "participant_identifiers": ["@user1", "@user2"],
        "keywords": ["test", "document"],
        "metadata": {"key": "value"},
        "contact_metadata": {"email": "test@example.com"},
        "participant_metadatas": [{"role": "author"}, {"role": "editor"}],
    }

    # Prepare the LanceDB chunk row
    row = prepare_lance_chunk_row(chunk, doc)

    # Check that the row contains all expected fields
    assert row["id"] == "test-id"
    assert row["doc_id"] == "doc-id"
    assert row["chunk_index"] == 0
    assert row["chunk_total"] == 1

    # Check that document fields are included
    assert row["url"] == "https://example.com"
    assert row["title"] == "Test Document"
    assert row["description"] == "A test document"
    assert row["source"] == "twitter"  # Enum converted to string
    assert row["source_type"] == "document"  # Enum converted to string
    assert row["source_location_identifier"] == "test-location"

    # Check that content is JSON serialized
    assert isinstance(row["content"], str)
    content_dict = json.loads(row["content"])
    assert "content" in content_dict
    assert len(content_dict["content"]) == 3  # Header + 2 content items

    # Check that the first item is the header
    assert content_dict["content"][0]["type"] == ContentType.TEXT
    assert "Title: Test Document" in content_dict["content"][0]["text"]
    assert "Source: twitter" in content_dict["content"][0]["text"]

    # Check that the second item is the text content
    assert content_dict["content"][1]["type"] == ContentType.TEXT
    assert content_dict["content"][1]["text"] == "Test content"

    # Check that the third item is the image URL
    assert content_dict["content"][2]["type"] == ContentType.IMAGE_URL
    assert content_dict["content"][2]["image_url"] == "https://example.com/image.jpg"


def test_prepare_document_for_storage():
    """Test preparing a document for storage."""
    # Create a test document
    doc_data = {
        "id": "test-id",
        "url": "https://example.com",
        "title": "Test Document",
        "description": "A test document",
        "source": Source.TWITTER,
        "source_type": SourceType.DOCUMENT,
        "source_location_identifier": "test-location",
        "participant_names": ["User1", "User2"],
        "participant_identifiers": ["@user1", "@user2"],
        "keywords": ["test", "document"],
        "metadata": {"key": "value"},
        "contact_metadata": {"email": "test@example.com"},
        "participant_metadatas": [{"role": "author"}, {"role": "editor"}],
        "geolocation": (37.7749, -122.4194),
        "text_content": "This is the text content",
    }

    # Prepare the document for storage
    prepared = prepare_document_for_storage(doc_data)

    # Check that the document was prepared correctly
    assert prepared["id"] == "test-id"
    assert prepared["url"] == "https://example.com"
    assert prepared["title"] == "Test Document"
    assert prepared["description"] == "A test document"
    assert prepared["source"] == "twitter"  # Enum converted to string
    assert prepared["source_type"] == "document"  # Enum converted to string
    assert prepared["source_location_identifier"] == "test-location"
    assert prepared["participant_names"] == ["User1", "User2"]
    assert prepared["participant_identifiers"] == ["@user1", "@user2"]
    assert prepared["keywords"] == ["test", "document"]

    # Check that metadata fields are JSON serialized
    assert isinstance(prepared["metadata"], str)
    assert json.loads(prepared["metadata"]) == {"key": "value"}

    assert isinstance(prepared["contact_metadata"], str)
    assert json.loads(prepared["contact_metadata"]) == {"email": "test@example.com"}

    assert isinstance(prepared["participant_metadatas"], str)
    assert json.loads(prepared["participant_metadatas"]) == [{"role": "author"}, {"role": "editor"}]

    # Check that location is formatted as WKT
    assert prepared["geolocation"] == "POINT (37.7749 -122.4194)"

    # Check that text_content is preserved
    assert prepared["text_content"] == "This is the text content"

    # Check that timestamps are set
    assert "ingested_at" in prepared
    assert "last_updated" in prepared


def test_prepare_document_for_storage_empty_fields():
    """Test preparing a document with empty fields for storage."""
    # Create a test document with empty fields
    doc_data = {
        "id": "test-id",
        "url": "https://example.com",
        "title": "Test Document",
        "source": Source.TWITTER,
        "source_type": SourceType.DOCUMENT,
        "source_location_identifier": "test-location",
        "participant_names": [],
        "participant_identifiers": [],
        "keywords": [],
        "metadata": {},
        "contact_metadata": {},
        "participant_metadatas": [],
    }

    # Prepare the document for storage
    prepared = prepare_document_for_storage(doc_data)

    # Check that empty array fields are set to None
    assert prepared["participant_names"] is None
    assert prepared["participant_identifiers"] is None
    assert prepared["keywords"] is None

    # Check that empty metadata fields are JSON serialized
    assert isinstance(prepared["metadata"], str)
    assert json.loads(prepared["metadata"]) == {}

    assert isinstance(prepared["contact_metadata"], str)
    assert json.loads(prepared["contact_metadata"]) == {}

    assert isinstance(prepared["participant_metadatas"], str)
    assert json.loads(prepared["participant_metadatas"]) == []


def test_prepare_document_for_storage_missing_fields():
    """Test preparing a document with missing fields for storage."""
    # Create a test document with missing fields
    doc_data = {
        "id": "test-id",
        "url": "https://example.com",
        "title": "Test Document",
        "source": Source.TWITTER,
        "source_type": SourceType.DOCUMENT,
        "source_location_identifier": "test-location",
    }

    # Prepare the document for storage
    prepared = prepare_document_for_storage(doc_data)

    # Check that missing fields are handled correctly
    assert "keywords" in prepared
    assert prepared["keywords"] is None

    # Check that missing metadata fields are JSON serialized with default values
    assert isinstance(prepared["metadata"], str)
    assert json.loads(prepared["metadata"]) == {}

    assert isinstance(prepared["contact_metadata"], str)
    assert json.loads(prepared["contact_metadata"]) == {}

    assert isinstance(prepared["participant_metadatas"], str)
    assert json.loads(prepared["participant_metadatas"]) == []

    # Check that location is set to None
    assert prepared["geolocation"] is None
