import os
import pytest
import tempfile
from datetime import datetime
from brocc_li.types.document import Source, Document
from brocc_li.utils.storage import DocumentStorage


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
    return DocumentStorage(db_path=temp_db_path)


@pytest.fixture
def sample_document():
    """Create a sample document for testing."""
    now = datetime.now()
    return {
        "id": "test123",
        "url": "https://example.com/test",
        "title": "Test Document",
        "description": "A document for testing",
        "content": "This is the content of the test document.",
        "author_name": "Test Author",
        "author_identifier": "author123",
        "created_at": Document.format_date(now),
        "metadata": {"key": "value"},
        "source": Source.TWITTER,
        "source_location": "https://example.com/test",
        "ingested_at": Document.format_date(now),
    }


def test_initialize_db(storage, temp_db_path):
    """Test database initialization."""
    assert os.path.exists(temp_db_path)

    # Store and retrieve a document to verify the table exists
    doc = {
        "id": "test_init",
        "url": "https://example.com/init",
        "source": Source.TWITTER,
        "source_location": "https://example.com/init",
    }
    storage.store_document(doc)
    assert storage.url_exists("https://example.com/init")


def test_store_and_retrieve_document(storage, sample_document):
    """Test storing and retrieving a document."""
    # Store the document
    result = storage.store_document(sample_document)
    assert result is True

    # Retrieve the document
    retrieved = storage.get_document_by_url(sample_document["url"])
    assert retrieved is not None
    assert retrieved["id"] == sample_document["id"]
    assert retrieved["title"] == sample_document["title"]
    assert retrieved["metadata"]["key"] == "value"  # Test JSON conversion


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

    # Retrieve and verify the update
    retrieved = storage.get_document_by_url(sample_document["url"])
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
            "source_location": "location1",
        },
        {
            "id": "doc2",
            "url": "https://example.com/2",
            "source": Source.TWITTER,
            "source_location": "location2",
        },
        {
            "id": "doc3",
            "url": "https://example.com/3",
            "source": Source.SUBSTACK,
            "source_location": "location1",
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
            "source_location": "location1",
            "ingested_at": "2024-01-01T00:00:01+00:00",  # Oldest
        },
        {
            "id": "doc2",
            "url": "https://example.com/2",
            "source": Source.TWITTER,
            "source_location": "location2",
            "ingested_at": "2024-01-01T00:00:02+00:00",  # Middle
        },
        {
            "id": "doc3",
            "url": "https://example.com/3",
            "source": Source.SUBSTACK,
            "source_location": "location1",
            "ingested_at": "2024-01-01T00:00:03+00:00",  # Newest
        },
    ]

    for doc in docs:
        storage.store_document(doc)

    # Get all documents
    all_docs = storage.get_documents()
    assert len(all_docs) == 3

    # Filter by source
    source1_docs = storage.get_documents(source="twitter")
    assert len(source1_docs) == 2
    assert any(doc["id"] == "doc1" for doc in source1_docs)
    assert any(doc["id"] == "doc2" for doc in source1_docs)
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
    assert limited_docs[0]["id"] == "doc3"  # Newest first
    assert limited_docs[1]["id"] == "doc2"  # Second newest

    offset_docs = storage.get_documents(limit=2, offset=1)
    assert len(offset_docs) == 2
    assert offset_docs[0]["id"] == "doc2"  # Second newest
    assert offset_docs[1]["id"] == "doc1"  # Oldest


def test_json_conversion(storage):
    """Test JSON conversion for metadata and content."""
    # Test with nested dict metadata
    doc_with_dict = {
        "id": "json_test1",
        "url": "https://example.com/json1",
        "metadata": {"key": "value", "nested": {"inner": "data"}},
        "content": "plain text",
        "source": Source.TWITTER,
        "source_location": "https://example.com/json1",
    }
    storage.store_document(doc_with_dict)
    retrieved = storage.get_document_by_url(doc_with_dict["url"])
    assert isinstance(retrieved["metadata"], dict)
    assert retrieved["metadata"]["key"] == "value"
    assert retrieved["metadata"]["nested"]["inner"] == "data"

    # Test with simple dict metadata
    doc_with_simple_dict = {
        "id": "json_test2",
        "url": "https://example.com/json2",
        "metadata": {"key": "value"},
        "content": "plain text",
        "source": Source.TWITTER,
        "source_location": "https://example.com/json2",
    }
    storage.store_document(doc_with_simple_dict)
    retrieved = storage.get_document_by_url(doc_with_simple_dict["url"])
    assert isinstance(retrieved["metadata"], dict)
    assert retrieved["metadata"]["key"] == "value"
