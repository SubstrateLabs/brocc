import os
import shutil
import tempfile
from datetime import datetime

import pytest

from brocc_li.doc_db import DocDB
from brocc_li.tests.generate_test_markdown import generate_test_markdown
from brocc_li.types.doc import Doc, Source, SourceType


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
def temp_lance_path():
    """Create a temporary directory for LanceDB."""
    temp_dir = tempfile.mkdtemp(prefix="lancedb_test_")
    yield temp_dir
    # Clean up the temporary directory after tests
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def docdb(temp_db_path, temp_lance_path, monkeypatch):
    """Create a DocDB instance with temporary databases and working LanceDB."""

    # Create a basic mock table that supports the methods we need
    class MockTable:
        def __init__(self):
            pass

        def search(self, query, **kwargs):
            return MockSearchResult(
                [
                    {
                        "id": "test123",
                        "doc_id": "test_doc",
                        "chunk_index": 0,
                        "chunk_total": 1,
                        "title": "Test Document",
                        "url": "https://example.com",
                        "source": "twitter",
                        "_distance": 0.1,
                    }
                ]
            )

        def add(self, data):
            return True

        def delete(self, filter_string):
            return True

    class MockSearchResult:
        def __init__(self, items):
            self.items = items

        def limit(self, n):
            return self

        def where(self, condition):
            return self

        def to_list(self):
            return self.items

    class MockLanceDB:
        def __init__(self):
            self._tables = {"chunks": MockTable()}

        def table_names(self):
            return ["chunks"]

        def open_table(self, name):
            return self._tables.get(name, MockTable())

        def create_table(self, name, **kwargs):
            self._tables[name] = MockTable()
            return self._tables[name]

    # Mock the initialize_lance method
    def mock_initialize_lance(self):
        self.lance_db = MockLanceDB()
        # State tracker for tests
        self._stored_docs = {}

    # Mock _store_in_lance to track what's been stored
    def mock_store_in_lance(self, chunks, doc):
        # Track doc_id for vector search filtering
        self._last_doc_id = doc.get("id", "")
        # Store chunk content for each doc
        self._stored_docs[doc.get("id", "")] = {"chunks": chunks, "doc": doc}
        # Return without doing anything real
        return

    # Mock _delete_chunks to simulate deletion
    def mock_delete_chunks(self, conn, doc_id):
        if doc_id in self._stored_docs:
            del self._stored_docs[doc_id]
            self._last_doc_id = ""

    # Mock vector_search to return results based on stored docs
    def mock_vector_search(self, query, limit=10, filter_str=None):
        # Basic mock results
        results = []

        # For the multimodal test
        if "multimodal_test" in getattr(self, "_last_doc_id", "") and "multimodal_test" in getattr(
            self, "_stored_docs", {}
        ):
            results.append(
                {
                    "id": "chunk1",
                    "doc_id": "multimodal_test",
                    "chunk_index": 0,
                    "chunk_total": 1,
                    "title": "Multimodal Test Document",
                    "url": "https://example.com",
                    "text": "Test multimodal content",
                    "source": "substack",
                    "score": 0.9,
                    "has_images": True,
                    "image_urls": ["https://brocc.li/brocc.png"],
                }
            )

        # For general search tests - but only if the document is in _stored_docs
        doc_id = "test123"
        if (
            doc_id in getattr(self, "_stored_docs", {}) or "test document" in query.lower()
        ) and doc_id in getattr(self, "_stored_docs", {}):
            results.append(
                {
                    "id": "chunk1",
                    "doc_id": doc_id,
                    "chunk_index": 0,
                    "chunk_total": 1,
                    "title": "Test Document",
                    "url": "https://example.com/test",
                    "text": "This is the content of the test document.",
                    "source": "twitter",
                    "score": 0.95,
                }
            )

        return results[:limit]

    # Apply the mocks
    monkeypatch.setattr(DocDB, "_initialize_lance", mock_initialize_lance)
    monkeypatch.setattr(DocDB, "_store_in_lance", mock_store_in_lance)
    monkeypatch.setattr(DocDB, "_delete_chunks", mock_delete_chunks)
    monkeypatch.setattr(DocDB, "vector_search", mock_vector_search)

    # Create the DocDB instance
    db = DocDB(db_path=temp_db_path, lance_path=temp_lance_path)

    # Make sure mocking worked
    assert db.lance_db is not None

    return db


@pytest.fixture
def sample_document():
    """Create a sample document for testing."""
    now = datetime.now()
    return Doc(
        id="test123",
        url="https://example.com/test",
        title="Test Document",
        description="A document for testing",
        text_content="This is the content of the test document.",
        contact_name="Test Author",
        contact_identifier="author123",
        participant_names=["Participant 1", "Participant 2"],
        participant_identifiers=["p1", "p2"],
        created_at=Doc.format_date(now),
        metadata={"key": "value"},
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="https://example.com/test",
        source_location_name="Test Source Location",
        ingested_at=Doc.format_date(now),
        location=None,
    )


def test_initialize_db(docdb, temp_db_path):
    """Test database initialization."""
    assert os.path.exists(temp_db_path)

    # Store and retrieve a document to verify the table exists
    doc = Doc(
        id="test_init",
        url="https://example.com/init",
        text_content="Test content for initialization",
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="https://example.com/init",
        source_location_name="Test Source Location",
        ingested_at=Doc.format_date(datetime.now()),
    )
    docdb.store_document(doc)
    assert docdb.url_exists("https://example.com/init")


def test_store_and_retrieve_document(docdb, sample_document):
    """Test storing and retrieving a document."""
    # Store the document
    result = docdb.store_document(sample_document)
    assert result is True

    # Retrieve the document by ID
    retrieved = docdb.get_document_by_id(sample_document.id)
    assert retrieved is not None
    assert retrieved["id"] == sample_document.id
    assert retrieved["title"] == sample_document.title
    assert retrieved["metadata"]["key"] == "value"  # Test JSON conversion
    assert retrieved["participant_names"] == ["Participant 1", "Participant 2"]
    assert retrieved["participant_identifiers"] == ["p1", "p2"]
    assert retrieved["location"] is None  # Verify location is None


def test_store_and_retrieve_document_with_location(docdb):
    """Test storing and retrieving a document with a location."""
    now = datetime.now()
    location_tuple = (-74.0060, 40.7128)  # Example: New York City
    doc_with_location = Doc(
        id="loc_test_1",
        url="https://example.com/location",
        title="Document with Location",
        text_content="This document has coordinates.",
        location=location_tuple,
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="location_source",
        ingested_at=Doc.format_date(now),
    )

    # Store the document
    result = docdb.store_document(doc_with_location)
    assert result is True

    # Retrieve the document by ID
    retrieved = docdb.get_document_by_id(doc_with_location.id)
    assert retrieved is not None
    assert retrieved["id"] == doc_with_location.id
    assert retrieved["title"] == doc_with_location.title

    # Verify the location tuple
    assert retrieved["location"] is not None
    # Compare floats using pytest.approx for tolerance
    assert retrieved["location"] == pytest.approx(location_tuple)


def test_store_document_without_url(docdb):
    """Test storing and retrieving a document without a URL."""
    doc = Doc(
        id="no_url_doc",
        title="No URL Document",
        text_content="Document with no URL",
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="location1",
        source_location_name="Test Source Location",
        ingested_at=Doc.format_date(datetime.now()),
        location=None,
    )

    result = docdb.store_document(doc)
    assert result is True

    retrieved = docdb.get_document_by_id(doc.id)
    assert retrieved is not None
    assert retrieved["id"] == doc.id
    assert retrieved["url"] is None
    assert retrieved["location"] is None


def test_update_document(docdb, sample_document):
    """Test updating an existing document with different content creates a new document."""
    # Store the initial document
    docdb.store_document(sample_document)
    original_id = sample_document.id

    # Update the document with different content (should create new doc)
    updated_doc = Doc(
        id=original_id,
        url=sample_document.url,
        title="Updated Title",
        description="Updated description",
        text_content="Updated content",  # Different content than original
        contact_name=sample_document.contact_name,
        contact_identifier=sample_document.contact_identifier,
        participant_names=sample_document.participant_names,
        participant_identifiers=sample_document.participant_identifiers,
        created_at=sample_document.created_at,
        metadata=sample_document.metadata,
        source=sample_document.source,
        source_type=sample_document.source_type,
        source_location_identifier=sample_document.source_location_identifier,
        source_location_name=sample_document.source_location_name,
        ingested_at=sample_document.ingested_at,
    )

    result = docdb.store_document(updated_doc)
    assert result is True

    # Original document should still exist with original title
    original_doc = docdb.get_document_by_id(original_id)
    assert original_doc["title"] == "Test Document"

    # Find the new document (which should have a different ID)
    docs_by_url = docdb.get_documents_by_url(sample_document.url)
    assert len(docs_by_url) == 2

    # Find the new document (not original_id)
    new_doc = next((doc for doc in docs_by_url if doc["id"] != original_id), None)
    assert new_doc is not None
    assert new_doc["title"] == "Updated Title"
    assert new_doc["description"] == "Updated description"


def test_url_exists(docdb, sample_document):
    """Test checking if a URL exists."""
    # Initially the URL should not exist
    assert not docdb.url_exists(sample_document.url)

    # After storing the document, the URL should exist
    docdb.store_document(sample_document)
    assert docdb.url_exists(sample_document.url)

    # Test with empty URL
    assert not docdb.url_exists("")


def test_get_seen_urls(docdb):
    """Test getting a set of seen URLs."""
    # Store multiple documents
    docs = [
        Doc(
            id="doc1",
            url="https://example.com/1",
            text_content="Content for doc1",
            source=Source.TWITTER,
            source_type=SourceType.DOCUMENT,
            source_location_identifier="location1",
            source_location_name="Test Source Location",
            ingested_at=Doc.format_date(datetime.now()),
        ),
        Doc(
            id="doc2",
            url="https://example.com/2",
            text_content="Content for doc2",
            source=Source.TWITTER,
            source_type=SourceType.DOCUMENT,
            source_location_identifier="location2",
            source_location_name="Test Source Location",
            ingested_at=Doc.format_date(datetime.now()),
        ),
        Doc(
            id="doc3",
            url="https://example.com/3",
            text_content="Content for doc3",
            source=Source.SUBSTACK,
            source_type=SourceType.DOCUMENT,
            source_location_identifier="location1",
            source_location_name="Test Source Location",
            ingested_at=Doc.format_date(datetime.now()),
        ),
        Doc(
            id="doc4",
            text_content="Content for doc4 without URL",
            source=Source.TWITTER,  # Document without URL
            source_type=SourceType.DOCUMENT,
            source_location_identifier="location3",
            source_location_name="Test Source Location",
            ingested_at=Doc.format_date(datetime.now()),
        ),
    ]

    for doc in docs:
        docdb.store_document(doc)

    # Get all seen URLs
    all_urls = docdb.get_seen_urls()
    assert len(all_urls) == 3
    assert "https://example.com/1" in all_urls
    assert "https://example.com/2" in all_urls
    assert "https://example.com/3" in all_urls

    # Filter by source
    source1_urls = docdb.get_seen_urls(source="twitter")
    assert len(source1_urls) == 2
    assert "https://example.com/1" in source1_urls
    assert "https://example.com/2" in source1_urls
    assert "https://example.com/3" not in source1_urls


def test_get_documents(docdb):
    """Test retrieving multiple documents with filtering."""
    # Store multiple documents with different timestamps
    docs = [
        Doc(
            id="doc1",
            url="https://example.com/1",
            text_content="Content for doc1",
            source=Source.TWITTER,
            source_type=SourceType.DOCUMENT,
            source_location_identifier="location1",
            source_location_name="Test Source Location",
            ingested_at="2024-01-01T00:00:01+00:00",  # Oldest
        ),
        Doc(
            id="doc2",
            url="https://example.com/2",
            text_content="Content for doc2",
            source=Source.TWITTER,
            source_type=SourceType.DOCUMENT,
            source_location_identifier="location2",
            source_location_name="Test Source Location",
            ingested_at="2024-01-01T00:00:02+00:00",  # Middle
        ),
        Doc(
            id="doc3",
            url="https://example.com/3",
            text_content="Content for doc3",
            source=Source.SUBSTACK,
            source_type=SourceType.DOCUMENT,
            source_location_identifier="location1",
            source_location_name="Test Source Location",
            ingested_at="2024-01-01T00:00:03+00:00",  # Newest
        ),
        Doc(
            id="doc4",
            text_content="Content for doc4 without URL",
            source=Source.TWITTER,  # Document without URL
            source_type=SourceType.DOCUMENT,
            source_location_identifier="location3",
            source_location_name="Test Source Location",
            ingested_at="2024-01-01T00:00:04+00:00",  # Newest
        ),
    ]

    for doc in docs:
        docdb.store_document(doc)

    # Get all documents
    all_docs = docdb.get_documents()
    assert len(all_docs) == 4

    # Filter by source
    source1_docs = docdb.get_documents(source="twitter")
    assert len(source1_docs) == 3
    assert any(doc["id"] == "doc1" for doc in source1_docs)
    assert any(doc["id"] == "doc2" for doc in source1_docs)
    assert any(doc["id"] == "doc4" for doc in source1_docs)
    assert not any(doc["id"] == "doc3" for doc in source1_docs)

    # Filter by source location
    location1_docs = docdb.get_documents(source_location="location1")
    assert len(location1_docs) == 2
    assert any(doc["id"] == "doc1" for doc in location1_docs)
    assert not any(doc["id"] == "doc2" for doc in location1_docs)
    assert any(doc["id"] == "doc3" for doc in location1_docs)

    # Test limit and offset with known order
    limited_docs = docdb.get_documents(limit=2)
    assert len(limited_docs) == 2
    assert limited_docs[0]["id"] == "doc4"  # Newest first
    assert limited_docs[1]["id"] == "doc3"  # Second newest

    offset_docs = docdb.get_documents(limit=2, offset=1)
    assert len(offset_docs) == 2
    assert offset_docs[0]["id"] == "doc3"  # Second newest
    assert offset_docs[1]["id"] == "doc2"  # Third newest


def test_json_conversion(docdb):
    """Test JSON conversion for metadata and content."""
    # Test with nested dict metadata
    doc_with_dict = Doc(
        id="json_test1",
        url="https://example.com/json1",
        metadata={"key": "value", "nested": {"inner": "data"}},
        text_content="plain text",
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="https://example.com/json1",
        source_location_name="Test Source Location",
        ingested_at=Doc.format_date(datetime.now()),
    )
    docdb.store_document(doc_with_dict)
    retrieved = docdb.get_document_by_id(doc_with_dict.id)
    assert isinstance(retrieved["metadata"], dict)
    assert retrieved["metadata"]["key"] == "value"
    assert retrieved["metadata"]["nested"]["inner"] == "data"

    # Test with simple dict metadata
    doc_with_simple_dict = Doc(
        id="json_test2",
        url="https://example.com/json2",
        metadata={"key": "value"},
        text_content="plain text",
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="https://example.com/json2",
        source_location_name="Test Source Location",
        ingested_at=Doc.format_date(datetime.now()),
    )
    docdb.store_document(doc_with_simple_dict)
    retrieved = docdb.get_document_by_id(doc_with_simple_dict.id)
    assert isinstance(retrieved["metadata"], dict)
    assert retrieved["metadata"]["key"] == "value"


def test_store_document_with_chunks(docdb):
    """Test basic document storage with simple content chunking."""
    # Create a document with basic content
    doc = Doc(
        id="doc_with_chunks",
        title="Document with Chunks",
        text_content="This is paragraph 1.\n\nThis is paragraph 2.\n\nThis is paragraph 3.",
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="location_chunks",
        source_location_name="Test Location",
        ingested_at=Doc.format_date(datetime.now()),
    )

    # Store the document (should create chunks automatically)
    docdb.store_document(doc)

    # Retrieve the document
    retrieved_doc = docdb.get_document_by_id("doc_with_chunks")
    assert retrieved_doc is not None

    # Get chunks separately (since we no longer auto-load them)
    chunks = docdb.get_chunks_by_doc_id("doc_with_chunks")

    # Verify chunks were created
    assert len(chunks) > 0

    # Verify relationship between chunks and document
    for chunk in chunks:
        assert chunk["doc_id"] == "doc_with_chunks"

    # Verify the document's chunks contain the original content
    all_text = []
    for chunk in chunks:
        # Get text directly from content
        chunk_text = "\n\n".join(
            item["text"] for item in chunk["content"] if item.get("type") == "text"
        )
        all_text.append(chunk_text)
    combined_text = "\n\n".join(all_text)

    assert "paragraph 1" in combined_text
    assert "paragraph 2" in combined_text
    assert "paragraph 3" in combined_text


def test_get_chunks_by_doc_id(docdb):
    """Test retrieving chunks for a document with multiple paragraphs."""
    # Create a document with multiple paragraphs
    long_text = "\n\n".join([f"This is paragraph {i}." for i in range(1, 10)])

    doc = Doc(
        id="chunks_doc",
        title="Chunks Document",
        text_content=long_text,
        source=Source.SUBSTACK,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="chunks_location",
        ingested_at=Doc.format_date(datetime.now()),
    )

    # Store the document with chunks
    docdb.store_document(doc)

    # Get chunks
    chunks = docdb.get_chunks_by_doc_id("chunks_doc")

    # Verify chunks
    assert len(chunks) > 0

    # Check chunk properties
    for chunk in chunks:
        assert chunk["doc_id"] == "chunks_doc"
        # Handle both str and int types for backward compatibility during schema transition
        assert isinstance(chunk["chunk_index"], (int, str))
        if isinstance(chunk["chunk_index"], str):
            assert chunk["chunk_index"].isdigit()  # Ensure it's a numeric string
        assert isinstance(chunk["chunk_total"], (int, str))
        # Ensure content is a list
        assert isinstance(chunk["content"], list)
        # Verify we can extract text from content
        text = "\n\n".join(item["text"] for item in chunk["content"] if item.get("type") == "text")
        assert isinstance(text, str)

    # Verify chunks are ordered by index
    # Convert to int if string for sorting comparison
    ordered_chunks = sorted(
        chunks,
        key=lambda c: int(c["chunk_index"])
        if isinstance(c["chunk_index"], str)
        else c["chunk_index"],
    )
    for i, chunk in enumerate(ordered_chunks):
        chunk_idx = (
            int(chunk["chunk_index"])
            if isinstance(chunk["chunk_index"], str)
            else chunk["chunk_index"]
        )
        assert chunk_idx == i


def test_store_document_with_rich_markdown_content(docdb):
    """Test storing a document with rich markdown content that will be chunked."""
    # Generate rich markdown content with multiple sections, paragraphs, and elements
    # This should be large enough to force chunking into multiple chunks
    rich_content = generate_test_markdown(
        num_sections=5,
        paragraphs_per_section=5,
        words_per_paragraph=100,
        add_images=True,
        add_lists=True,
        add_tables=True,
        add_code_blocks=True,
        add_blockquotes=True,
        seed=42,  # Explicitly set seed for deterministic content generation
    )

    # Verify the generated content is substantial
    assert len(rich_content) > 2000, "Generated markdown should be large enough to force chunking"

    # Create a document with the rich content
    doc = Doc(
        id="rich_markdown_doc",
        title="Rich Markdown Document",
        text_content=rich_content,
        source=Source.SUBSTACK,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="rich_markdown_location",
        source_location_name="Rich Markdown Test",
        ingested_at=Doc.format_date(datetime.now()),
    )

    # Store the document with chunks
    docdb.store_document(doc)

    # Retrieve the document
    retrieved_doc = docdb.get_document_by_id("rich_markdown_doc")
    assert retrieved_doc is not None
    assert retrieved_doc["title"] == "Rich Markdown Document"

    # Get chunks separately (since we no longer auto-load them)
    chunks = docdb.get_chunks_by_doc_id("rich_markdown_doc")

    # Verify chunks were created and there's more than one (ensuring chunking happened)
    assert len(chunks) > 1, "Content should be split into multiple chunks"

    # Verify each chunk has the right properties
    for chunk in chunks:
        assert chunk["doc_id"] == "rich_markdown_doc"
        # Handle both str and int types for backward compatibility during schema transition
        assert isinstance(chunk["chunk_index"], (int, str))
        if isinstance(chunk["chunk_index"], str):
            assert chunk["chunk_index"].isdigit()  # Ensure it's a numeric string
        assert isinstance(chunk["chunk_total"], (int, str))
        assert isinstance(chunk["content"], list)
        # Ensure we can extract text content
        text = "\n\n".join(item["text"] for item in chunk["content"] if item.get("type") == "text")
        assert isinstance(text, str)

    # Verify chunks are ordered by index
    # Convert to int if string for sorting comparison
    ordered_chunks = sorted(
        chunks,
        key=lambda c: int(c["chunk_index"])
        if isinstance(c["chunk_index"], str)
        else c["chunk_index"],
    )
    for i, chunk in enumerate(ordered_chunks):
        chunk_idx = (
            int(chunk["chunk_index"])
            if isinstance(chunk["chunk_index"], str)
            else chunk["chunk_index"]
        )
        assert chunk_idx == i

    # Verify the chunks contain key elements from the original content
    # First gather all the text from all chunks
    all_text = []
    for chunk in chunks:
        # Get text directly from content
        chunk_text = "\n\n".join(
            item["text"] for item in chunk["content"] if item.get("type") == "text"
        )
        all_text.append(chunk_text)
    combined_text = "\n\n".join(all_text)

    # Now check for content
    assert "Section 1" in combined_text
    assert "Section 5" in combined_text  # Test first and last sections

    # Instead of checking for specific markdown elements that might be randomly omitted,
    # verify the overall structure is preserved by checking section headings
    for i in range(1, 6):
        assert f"Section {i}" in combined_text, f"Section {i} should be in chunks' content"

    # Check for multimodal chunks (chunks with images)
    multimodal_chunks = []
    for chunk in chunks:
        # Get image URLs directly from content
        image_urls = [
            item["image_url"] for item in chunk["content"] if item.get("type") == "image_url"
        ]
        if image_urls:
            multimodal_chunks.append({"chunk": chunk, "image_urls": image_urls})

    assert len(multimodal_chunks) > 0, "Should have at least one multimodal chunk with images"

    # Verify image URLs exist
    for chunk_data in multimodal_chunks:
        image_urls = chunk_data["image_urls"]
        assert len(image_urls) > 0, "Image URLs should be present"
        assert all(url.startswith("http") for url in image_urls), "Image URLs should be valid URLs"


def test_location_operations(docdb):
    """Test various location operations including storage, retrieval, and updates."""
    # Create document with no location first
    doc_without_location = Doc(
        id="loc_test_no_loc",
        url="https://example.com/no_loc",
        title="No Location Document",
        text_content="This document has no location.",
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="test_source",
        ingested_at=Doc.format_date(datetime.now()),
        location=None,  # Explicitly None
    )

    # Store the document
    docdb.store_document(doc_without_location)

    # Verify stored with None location
    retrieved = docdb.get_document_by_id(doc_without_location.id)
    assert retrieved["location"] is None

    # Now update with a location (same content)
    same_content_with_location = Doc(
        id=doc_without_location.id,
        url="https://example.com/no_loc",
        title="No Location Document - Updated With Location",
        text_content="This document has no location.",  # Same content
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="test_source",
        ingested_at=Doc.format_date(datetime.now()),
        location=(-122.4194, 37.7749),  # San Francisco coordinates
    )

    # Store the updated document
    docdb.store_document(same_content_with_location)

    # Since content is same, it should update the existing document
    updated = docdb.get_document_by_id(doc_without_location.id)
    assert updated["title"] == "No Location Document - Updated With Location"
    assert updated["location"] is not None
    assert updated["location"] == pytest.approx((-122.4194, 37.7749))

    # Create a document with a location
    doc_with_location = Doc(
        id="loc_test_with_loc",
        url="https://example.com/with_loc",
        title="Location Document",
        text_content="This document has a location.",
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="test_source",
        ingested_at=Doc.format_date(datetime.now()),
        location=(-74.0060, 40.7128),  # New York City
    )

    # Store the document
    docdb.store_document(doc_with_location)

    # Verify location was stored correctly
    retrieved = docdb.get_document_by_id(doc_with_location.id)
    assert retrieved["location"] == pytest.approx((-74.0060, 40.7128))

    # Update with a different location (same content)
    updated_location_doc = Doc(
        id=doc_with_location.id,
        url="https://example.com/with_loc",
        title="Updated Location Document",
        text_content="This document has a location.",  # Same content
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="test_source",
        ingested_at=Doc.format_date(datetime.now()),
        location=(-87.6298, 41.8781),  # Chicago
    )

    # Store the updated document
    docdb.store_document(updated_location_doc)

    # Should update existing document
    updated = docdb.get_document_by_id(doc_with_location.id)
    assert updated["title"] == "Updated Location Document"
    assert updated["location"] == pytest.approx((-87.6298, 41.8781))

    # Update with null location (same content)
    remove_location_doc = Doc(
        id=doc_with_location.id,
        url="https://example.com/with_loc",
        title="Removed Location Document",
        text_content="This document has a location.",  # Same content
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="test_source",
        ingested_at=Doc.format_date(datetime.now()),
        location=None,  # Remove location
    )

    # Store the updated document
    docdb.store_document(remove_location_doc)

    # Should update existing document with null location
    updated = docdb.get_document_by_id(doc_with_location.id)
    assert updated["title"] == "Removed Location Document"
    assert updated["location"] is None

    # Different content should create new doc even if location is same
    diff_content_doc = Doc(
        id=doc_with_location.id,
        url="https://example.com/with_loc",
        title="Different Content Document",
        text_content="This document has DIFFERENT content.",  # Different content
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="test_source",
        ingested_at=Doc.format_date(datetime.now()),
        location=(-87.6298, 41.8781),  # Chicago again
    )

    # Store document with different content
    docdb.store_document(diff_content_doc)

    # Original document should be unchanged
    original = docdb.get_document_by_id(doc_with_location.id)
    assert original["title"] == "Removed Location Document"
    assert original["location"] is None

    # New document should have been created with the location
    docs_by_url = docdb.get_documents_by_url("https://example.com/with_loc")
    assert len(docs_by_url) == 2

    # Find the new document (not the original ID)
    new_doc = next((doc for doc in docs_by_url if doc["id"] != doc_with_location.id), None)
    assert new_doc is not None
    assert new_doc["title"] == "Different Content Document"
    assert new_doc["location"] == pytest.approx((-87.6298, 41.8781))


def test_content_based_update(docdb, sample_document):
    """Test that documents are only updated when content is identical."""
    # Store the initial document
    docdb.store_document(sample_document)
    original_id = sample_document.id

    # Case 1: Update with identical content but different metadata
    updated_doc = Doc(
        id=original_id,
        url=sample_document.url,
        title="Updated Title - Same Content",
        description="Updated description, but identical content",
        text_content=sample_document.text_content,  # Same content
        source=sample_document.source,
        source_type=sample_document.source_type,
        source_location_identifier=sample_document.source_location_identifier,
        source_location_name=sample_document.source_location_name,
        ingested_at=sample_document.ingested_at,
        location=(10.0, 20.0),  # Add a location to previously None
    )

    # Should update the existing document
    docdb.store_document(updated_doc)

    # Check it updated the existing document (same ID)
    doc = docdb.get_document_by_id(original_id)
    assert doc is not None
    assert doc["id"] == original_id
    assert doc["title"] == "Updated Title - Same Content"
    assert doc["location"] == pytest.approx((10.0, 20.0))  # Location should be updated

    # Case 2: Update with different content
    new_content_doc = Doc(
        id=original_id,  # Same ID
        url=sample_document.url,  # Same URL
        title="New Content Document",
        description="This has different content",
        text_content="This is completely different content that should create a new document.",  # Different content
        source=sample_document.source,
        source_type=sample_document.source_type,
        source_location_identifier=sample_document.source_location_identifier,
        source_location_name=sample_document.source_location_name,
        ingested_at=sample_document.ingested_at,
        location=(30.0, 40.0),  # Different location too
    )

    # Should create a new document
    docdb.store_document(new_content_doc)

    # Check the original document still exists and wasn't changed
    original_doc = docdb.get_document_by_id(original_id)
    assert original_doc is not None
    assert original_doc["title"] == "Updated Title - Same Content"  # From the first update
    assert original_doc["location"] == pytest.approx((10.0, 20.0))  # Should be unchanged

    # Get documents by URL - should have two now
    docs_by_url = docdb.get_documents_by_url(sample_document.url)
    assert len(docs_by_url) == 2

    # Find the new document (not original_id)
    new_doc = next((doc for doc in docs_by_url if doc["id"] != original_id), None)
    assert new_doc is not None
    assert new_doc["title"] == "New Content Document"
    assert new_doc["location"] == pytest.approx((30.0, 40.0))  # New document has new location

    # Get chunks for both documents to verify they're different
    original_chunks = docdb.get_chunks_by_doc_id(original_id)
    new_chunks = docdb.get_chunks_by_doc_id(new_doc["id"])

    # Both should have chunks
    assert len(original_chunks) > 0
    assert len(new_chunks) > 0

    # Content should be different
    original_text = "\n\n".join(
        [
            "\n\n".join(item["text"] for item in chunk["content"] if item.get("type") == "text")
            for chunk in original_chunks
        ]
    )
    new_text = "\n\n".join(
        [
            "\n\n".join(item["text"] for item in chunk["content"] if item.get("type") == "text")
            for chunk in new_chunks
        ]
    )

    assert original_text != new_text
    assert "This is completely different content" in new_text


def test_get_documents_with_location(docdb):
    """Test retrieving multiple documents with and without locations."""
    # Create documents with different locations
    doc1 = Doc(
        id="loc_get_1",
        url="https://example.com/loc_get/1",
        title="Location Document 1",
        text_content="Document with location 1",
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="loc_get_source",
        ingested_at=Doc.format_date(datetime.now()),
        location=(0.0, 0.0),  # Null Island
    )

    doc2 = Doc(
        id="loc_get_2",
        url="https://example.com/loc_get/2",
        title="Location Document 2",
        text_content="Document with location 2",
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="loc_get_source",
        ingested_at=Doc.format_date(datetime.now()),
        location=(1.0, 1.0),  # Another location
    )

    doc3 = Doc(
        id="loc_get_3",
        url="https://example.com/loc_get/3",
        title="Document without location",
        text_content="Document with no location",
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="loc_get_source",
        ingested_at=Doc.format_date(datetime.now()),
        location=None,  # No location
    )

    # Store all documents
    for doc in [doc1, doc2, doc3]:
        docdb.store_document(doc)

    # Get all documents from the same source
    docs = docdb.get_documents(source_location="loc_get_source")
    assert len(docs) == 3

    # Verify each document has correct location
    doc1_retrieved = next((d for d in docs if d["id"] == "loc_get_1"), None)
    assert doc1_retrieved is not None
    assert doc1_retrieved["location"] == pytest.approx((0.0, 0.0))

    doc2_retrieved = next((d for d in docs if d["id"] == "loc_get_2"), None)
    assert doc2_retrieved is not None
    assert doc2_retrieved["location"] == pytest.approx((1.0, 1.0))

    doc3_retrieved = next((d for d in docs if d["id"] == "loc_get_3"), None)
    assert doc3_retrieved is not None
    assert doc3_retrieved["location"] is None
