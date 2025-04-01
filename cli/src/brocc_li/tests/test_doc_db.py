import os
import pytest
import tempfile
from datetime import datetime
from brocc_li.types.doc import Source, SourceType, Doc
from brocc_li.doc_db import DocDB


@pytest.fixture
def temp_db_path():
    """Create a temporary database file path for testing."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as temp_file:
        temp_db_path = temp_file.name

    # Delete the file immediately - DuckDB will create it properly
    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)

    yield temp_db_path

    # Clean up the temporary database file after tests
    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)


@pytest.fixture
def storage(temp_db_path):
    """Create a DocumentStorage instance with a temporary database."""
    return DocDB(db_path=temp_db_path)


@pytest.fixture
def sample_document():
    """Create a sample document for testing."""
    now = datetime.now()
    return {
        "id": "test123",
        "url": "https://example.com/test",
        "title": "Test Document",
        "description": "A document for testing",
        "text_content": "This is the content of the test document.",
        "contact_name": "Test Author",
        "contact_identifier": "author123",
        "participant_names": ["Participant 1", "Participant 2"],
        "participant_identifiers": ["p1", "p2"],
        "created_at": Doc.format_date(now),
        "metadata": {"key": "value"},
        "source": Source.TWITTER,
        "source_type": SourceType.DOCUMENT,
        "source_location_identifier": "https://example.com/test",
        "source_location_name": "Test Source Location",
        "ingested_at": Doc.format_date(now),
    }


def test_initialize_db(storage, temp_db_path):
    """Test database initialization."""
    assert os.path.exists(temp_db_path)

    # Store and retrieve a document to verify the table exists
    doc = {
        "id": "test_init",
        "url": "https://example.com/init",
        "source": Source.TWITTER,
        "source_type": SourceType.DOCUMENT,
        "source_location_identifier": "https://example.com/init",
        "source_location_name": "Test Source Location",
    }
    storage.store_document(doc)
    assert storage.url_exists("https://example.com/init")


def test_store_and_retrieve_document(storage, sample_document):
    """Test storing and retrieving a document."""
    # Store the document
    result = storage.store_document(sample_document)
    assert result is True

    # Retrieve the document by ID
    retrieved = storage.get_document_by_id(sample_document["id"])
    assert retrieved is not None
    assert retrieved["id"] == sample_document["id"]
    assert retrieved["title"] == sample_document["title"]
    assert retrieved["metadata"]["key"] == "value"  # Test JSON conversion
    assert retrieved["participant_names"] == ["Participant 1", "Participant 2"]
    assert retrieved["participant_identifiers"] == ["p1", "p2"]


def test_store_document_without_url(storage):
    """Test storing and retrieving a document without a URL."""
    doc = {
        "id": "no_url_doc",
        "title": "No URL Document",
        "source": Source.TWITTER,
        "source_type": SourceType.DOCUMENT,
        "source_location_identifier": "location1",
        "source_location_name": "Test Source Location",
    }

    result = storage.store_document(doc)
    assert result is True

    retrieved = storage.get_document_by_id(doc["id"])
    assert retrieved is not None
    assert retrieved["id"] == doc["id"]
    assert retrieved["url"] is None


def test_update_document(storage, sample_document):
    """Test updating an existing document."""
    # Store the initial document
    storage.store_document(sample_document)

    # Update the document
    updated_doc = sample_document.copy()
    updated_doc["title"] = "Updated Title"
    updated_doc["description"] = "Updated description"

    result = storage.store_document(updated_doc)
    assert result is True

    # Retrieve and verify the update by ID
    retrieved = storage.get_document_by_id(sample_document["id"])
    assert retrieved["title"] == "Updated Title"
    assert retrieved["description"] == "Updated description"


def test_url_exists(storage, sample_document):
    """Test checking if a URL exists."""
    # Initially the URL should not exist
    assert not storage.url_exists(sample_document["url"])

    # After storing the document, the URL should exist
    storage.store_document(sample_document)
    assert storage.url_exists(sample_document["url"])

    # Test with empty URL
    assert not storage.url_exists("")


def test_get_seen_urls(storage):
    """Test getting a set of seen URLs."""
    # Store multiple documents
    docs = [
        {
            "id": "doc1",
            "url": "https://example.com/1",
            "source": Source.TWITTER,
            "source_type": SourceType.DOCUMENT,
            "source_location_identifier": "location1",
            "source_location_name": "Test Source Location",
        },
        {
            "id": "doc2",
            "url": "https://example.com/2",
            "source": Source.TWITTER,
            "source_type": SourceType.DOCUMENT,
            "source_location_identifier": "location2",
            "source_location_name": "Test Source Location",
        },
        {
            "id": "doc3",
            "url": "https://example.com/3",
            "source": Source.SUBSTACK,
            "source_type": SourceType.DOCUMENT,
            "source_location_identifier": "location1",
            "source_location_name": "Test Source Location",
        },
        {
            "id": "doc4",
            "source": Source.TWITTER,  # Document without URL
            "source_type": SourceType.DOCUMENT,
            "source_location_identifier": "location3",
            "source_location_name": "Test Source Location",
        },
    ]

    for doc in docs:
        storage.store_document(doc)

    # Get all seen URLs
    all_urls = storage.get_seen_urls()
    assert len(all_urls) == 3
    assert "https://example.com/1" in all_urls
    assert "https://example.com/2" in all_urls
    assert "https://example.com/3" in all_urls

    # Filter by source
    source1_urls = storage.get_seen_urls(source="twitter")
    assert len(source1_urls) == 2
    assert "https://example.com/1" in source1_urls
    assert "https://example.com/2" in source1_urls
    assert "https://example.com/3" not in source1_urls


def test_get_documents(storage):
    """Test retrieving multiple documents with filtering."""
    # Store multiple documents with different timestamps
    docs = [
        {
            "id": "doc1",
            "url": "https://example.com/1",
            "source": Source.TWITTER,
            "source_type": SourceType.DOCUMENT,
            "source_location_identifier": "location1",
            "source_location_name": "Test Source Location",
            "ingested_at": "2024-01-01T00:00:01+00:00",  # Oldest
        },
        {
            "id": "doc2",
            "url": "https://example.com/2",
            "source": Source.TWITTER,
            "source_type": SourceType.DOCUMENT,
            "source_location_identifier": "location2",
            "source_location_name": "Test Source Location",
            "ingested_at": "2024-01-01T00:00:02+00:00",  # Middle
        },
        {
            "id": "doc3",
            "url": "https://example.com/3",
            "source": Source.SUBSTACK,
            "source_type": SourceType.DOCUMENT,
            "source_location_identifier": "location1",
            "source_location_name": "Test Source Location",
            "ingested_at": "2024-01-01T00:00:03+00:00",  # Newest
        },
        {
            "id": "doc4",
            "source": Source.TWITTER,  # Document without URL
            "source_type": SourceType.DOCUMENT,
            "source_location_identifier": "location3",
            "source_location_name": "Test Source Location",
            "ingested_at": "2024-01-01T00:00:04+00:00",  # Newest
        },
    ]

    for doc in docs:
        storage.store_document(doc)

    # Get all documents
    all_docs = storage.get_documents()
    assert len(all_docs) == 4

    # Filter by source
    source1_docs = storage.get_documents(source="twitter")
    assert len(source1_docs) == 3
    assert any(doc["id"] == "doc1" for doc in source1_docs)
    assert any(doc["id"] == "doc2" for doc in source1_docs)
    assert any(doc["id"] == "doc4" for doc in source1_docs)
    assert not any(doc["id"] == "doc3" for doc in source1_docs)

    # Filter by source location
    location1_docs = storage.get_documents(source_location="location1")
    assert len(location1_docs) == 2
    assert any(doc["id"] == "doc1" for doc in location1_docs)
    assert not any(doc["id"] == "doc2" for doc in location1_docs)
    assert any(doc["id"] == "doc3" for doc in location1_docs)

    # Test limit and offset with known order
    limited_docs = storage.get_documents(limit=2)
    assert len(limited_docs) == 2
    assert limited_docs[0]["id"] == "doc4"  # Newest first
    assert limited_docs[1]["id"] == "doc3"  # Second newest

    offset_docs = storage.get_documents(limit=2, offset=1)
    assert len(offset_docs) == 2
    assert offset_docs[0]["id"] == "doc3"  # Second newest
    assert offset_docs[1]["id"] == "doc2"  # Third newest


def test_json_conversion(storage):
    """Test JSON conversion for metadata and content."""
    # Test with nested dict metadata
    doc_with_dict = {
        "id": "json_test1",
        "url": "https://example.com/json1",
        "metadata": {"key": "value", "nested": {"inner": "data"}},
        "text_content": "plain text",
        "source": Source.TWITTER,
        "source_type": SourceType.DOCUMENT,
        "source_location_identifier": "https://example.com/json1",
        "source_location_name": "Test Source Location",
    }
    storage.store_document(doc_with_dict)
    retrieved = storage.get_document_by_id(doc_with_dict["id"])
    assert isinstance(retrieved["metadata"], dict)
    assert retrieved["metadata"]["key"] == "value"
    assert retrieved["metadata"]["nested"]["inner"] == "data"

    # Test with simple dict metadata
    doc_with_simple_dict = {
        "id": "json_test2",
        "url": "https://example.com/json2",
        "metadata": {"key": "value"},
        "text_content": "plain text",
        "source": Source.TWITTER,
        "source_type": SourceType.DOCUMENT,
        "source_location_identifier": "https://example.com/json2",
        "source_location_name": "Test Source Location",
    }
    storage.store_document(doc_with_simple_dict)
    retrieved = storage.get_document_by_id(doc_with_simple_dict["id"])
    assert isinstance(retrieved["metadata"], dict)
    assert retrieved["metadata"]["key"] == "value"
