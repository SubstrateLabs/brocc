import os
import shutil
import tempfile
from datetime import datetime

import pytest

from brocc_li.doc_db import DUCKDB_CHUNKS_TABLE, DocDB
from brocc_li.tests.generate_test_markdown import generate_test_markdown
from brocc_li.types.doc import Doc, Source, SourceType
from brocc_li.utils.logger import logger


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

    # Mock _delete_chunks to simulate deletion and actual DB delete
    def mock_delete_chunks(self, conn, doc_id):
        # Simulate LanceDB deletion (using internal mock state)
        if hasattr(self, "_stored_docs") and doc_id in self._stored_docs:
            del self._stored_docs[doc_id]
            # Reset last_doc_id if it matched the deleted one
            if hasattr(self, "_last_doc_id") and self._last_doc_id == doc_id:
                self._last_doc_id = ""

        # Perform ACTUAL deletion from the test DuckDB
        try:
            conn.execute(f"DELETE FROM {DUCKDB_CHUNKS_TABLE} WHERE doc_id = ?", [doc_id])
            logger.debug(f"[Mock] Actually deleted DuckDB chunks for doc_id {doc_id}")
        except Exception as e:
            logger.error(f"[Mock] Error deleting DuckDB chunks for {doc_id}: {e}")
            # Optionally re-raise or handle as needed for test stability
            raise

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
    monkeypatch.setattr(DocDB, "_initialize_lancedb", mock_initialize_lance)
    monkeypatch.setattr(DocDB, "_store_lance_chunks", mock_store_in_lance)
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
        geolocation=None,
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
    assert retrieved["geolocation"] is None  # Verify location is None


def test_store_and_retrieve_document_with_location(docdb):
    """Test storing and retrieving a document with geolocation data."""
    location_data = (10.0, 20.0)
    doc = Doc(
        id="loc_test_1",
        url="http://example.com/loc1",
        title="Doc with location 1",
        text_content="Document content 1",
        geolocation=location_data,  # Use the correct field name
    )
    docdb.store_document(doc)

    retrieved_doc = docdb.get_document_by_id("loc_test_1")
    assert retrieved_doc is not None
    # Check the correct field name
    assert retrieved_doc.get("geolocation") is not None
    # Use approx for float comparison
    assert retrieved_doc["geolocation"] == pytest.approx(location_data)


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
        geolocation=None,
    )

    result = docdb.store_document(doc)
    assert result is True

    retrieved = docdb.get_document_by_id(doc.id)
    assert retrieved is not None
    assert retrieved["id"] == doc.id
    assert retrieved["url"] is None
    assert retrieved["geolocation"] is None


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
    chunks = docdb.get_duckdb_chunks("doc_with_chunks")

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


def test_get_duckdb_chunks(docdb):
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
    chunks = docdb.get_duckdb_chunks("chunks_doc")

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
    chunks = docdb.get_duckdb_chunks("rich_markdown_doc")

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


def test_store_document_with_no_location(docdb):
    """Test storing and retrieving a document without location data."""
    doc = Doc(
        id="loc_test_2",
        url="http://example.com/loc2",
        title="Doc with no location",
        text_content="Document content 2",
        geolocation=None,  # Explicitly set to None
    )
    docdb.store_document(doc)

    retrieved_doc = docdb.get_document_by_id("loc_test_2")
    assert retrieved_doc is not None
    # Check the correct field name
    assert retrieved_doc.get("geolocation") is None


def test_location_operations(docdb):
    """Test storing different location formats and retrieving them."""
    doc1 = Doc(
        id="loc_op_1",
        url="http://example.com/loc_op1",
        title="Location Op 1",
        text_content="Content Op 1",
        geolocation=(1.23, 4.56),
    )
    doc2 = Doc(
        id="loc_op_2",
        url="http://example.com/loc_op2",
        title="Location Op 2",
        text_content="Content Op 2",
        geolocation=None,
    )
    docdb.store_document(doc1)
    docdb.store_document(doc2)

    retrieved_doc1 = docdb.get_document_by_id("loc_op_1")
    assert retrieved_doc1 is not None
    # Check the correct field name
    assert retrieved_doc1.get("geolocation") == pytest.approx((1.23, 4.56))

    retrieved_doc2 = docdb.get_document_by_id("loc_op_2")
    assert retrieved_doc2 is not None
    # Check the correct field name
    assert retrieved_doc2.get("geolocation") is None


def test_get_documents_with_location(docdb):
    """Test retrieving multiple documents, including those with location."""
    doc1 = Doc(
        id="get_loc_1",
        url="http://example.com/get_loc1",
        title="Get Location 1",
        text_content="Get Content 1",
        geolocation=(0.0, 0.0),
    )
    doc2 = Doc(
        id="get_loc_2",
        url="http://example.com/get_loc2",
        title="Get Location 2",
        text_content="Get Content 2",
        geolocation=None,
    )
    docdb.store_document(doc1)
    docdb.store_document(doc2)

    docs = docdb.get_documents(limit=2)
    assert len(docs) == 2

    # Find the documents (order might vary)
    doc1_retrieved = next((d for d in docs if d["id"] == "get_loc_1"), None)
    doc2_retrieved = next((d for d in docs if d["id"] == "get_loc_2"), None)

    assert doc1_retrieved is not None
    # Check the correct field name
    assert doc1_retrieved.get("geolocation") == pytest.approx((0.0, 0.0))

    assert doc2_retrieved is not None
    # Check the correct field name
    assert doc2_retrieved.get("geolocation") is None


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
        geolocation=(10.0, 20.0),  # Add a location to previously None
    )

    # Should update the existing document
    docdb.store_document(updated_doc)

    # Check it updated the existing document (same ID)
    doc = docdb.get_document_by_id(original_id)
    assert doc is not None
    assert doc["id"] == original_id
    assert doc["title"] == "Updated Title - Same Content"
    assert doc["geolocation"] == pytest.approx((10.0, 20.0))  # Location should be updated

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
        geolocation=(30.0, 40.0),  # Different location too
    )

    # Should create a new document
    docdb.store_document(new_content_doc)

    # Check the original document still exists and wasn't changed
    original_doc = docdb.get_document_by_id(original_id)
    assert original_doc is not None
    assert original_doc["title"] == "Updated Title - Same Content"  # From the first update
    assert original_doc["geolocation"] == pytest.approx((10.0, 20.0))  # Should be unchanged

    # Get documents by URL - should have two now
    docs_by_url = docdb.get_documents_by_url(sample_document.url)
    assert len(docs_by_url) == 2

    # Find the new document (not original_id)
    new_doc = next((doc for doc in docs_by_url if doc["id"] != original_id), None)
    assert new_doc is not None
    assert new_doc["title"] == "New Content Document"
    assert new_doc["geolocation"] == pytest.approx((30.0, 40.0))  # New document has new location

    # Get chunks for both documents to verify they're different
    original_chunks = docdb.get_duckdb_chunks(original_id)
    new_chunks = docdb.get_duckdb_chunks(new_doc["id"])

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


def test_merge_update(docdb):
    """Test updating a document where content is mergeable."""
    # Initial content
    initial_text = (
        "Section 1\n\nThis is the first paragraph.\n\nSection 2\n\nThis is the second paragraph."
    )
    doc1 = Doc(
        id="merge_test_1",
        url="https://example.com/merge",
        title="Merge Test Initial",
        text_content=initial_text,
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="merge_source",
        ingested_at=Doc.format_date(datetime.now()),
    )
    docdb.store_document(doc1)

    # Updated content (adds a paragraph to section 1)
    updated_text = "Section 1\n\nThis is the first paragraph.\n\nThis is an added paragraph.\n\nSection 2\n\nThis is the second paragraph."
    doc2 = Doc(
        id="merge_test_1",  # Same ID
        url="https://example.com/merge",  # Same URL
        title="Merge Test Updated",
        text_content=updated_text,
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="merge_source",
        ingested_at=Doc.format_date(datetime.now()),
    )
    docdb.store_document(doc2)

    # Should have updated the original document
    docs_by_url = docdb.get_documents_by_url("https://example.com/merge")
    assert len(docs_by_url) == 1
    updated_doc = docs_by_url[0]
    assert updated_doc["id"] == "merge_test_1"
    assert updated_doc["title"] == "Merge Test Updated"

    # Verify merged content in chunks
    updated_chunks = docdb.get_duckdb_chunks("merge_test_1")
    reconstructed_text = docdb._reconstruct_text_from_chunks(updated_chunks)

    # Expected merged content (based on merge_md logic)
    expected_merged_text = "Section 1\n\nThis is the first paragraph.\n\nThis is an added paragraph.\n\nSection 2\n\nThis is the second paragraph."
    assert reconstructed_text == expected_merged_text


def test_no_merge_creates_new(docdb):
    """Test updating a document where content is too different for merging, creating a new doc."""
    initial_text = "Completely original content here."
    doc1 = Doc(
        id="no_merge_test_1",
        url="https://example.com/no_merge",
        title="No Merge Initial",
        text_content=initial_text,
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="no_merge_source",
        ingested_at=Doc.format_date(datetime.now()),
    )
    docdb.store_document(doc1)

    # Completely different content
    updated_text = "Totally different information goes here now."
    doc2 = Doc(
        id="no_merge_test_1",  # Same ID initially
        url="https://example.com/no_merge",  # Same URL
        title="No Merge New Content",
        text_content=updated_text,
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="no_merge_source",
        ingested_at=Doc.format_date(datetime.now()),
    )
    docdb.store_document(doc2)

    # Should have two documents now
    docs_by_url = docdb.get_documents_by_url("https://example.com/no_merge")
    assert len(docs_by_url) == 2

    # Original document should be unchanged
    original_doc = next((d for d in docs_by_url if d["id"] == "no_merge_test_1"), None)
    assert original_doc is not None
    assert original_doc["title"] == "No Merge Initial"
    original_chunks = docdb.get_duckdb_chunks("no_merge_test_1")
    reconstructed_original = docdb._reconstruct_text_from_chunks(original_chunks)
    assert reconstructed_original == initial_text

    # New document should exist with the new content
    new_doc = next((d for d in docs_by_url if d["id"] != "no_merge_test_1"), None)
    assert new_doc is not None
    assert new_doc["title"] == "No Merge New Content"
    new_chunks = docdb.get_duckdb_chunks(new_doc["id"])
    reconstructed_new = docdb._reconstruct_text_from_chunks(new_chunks)
    assert reconstructed_new == updated_text


def test_merge_modification(docdb):
    """Test merging where content within a block is modified."""
    initial_text = "Block A\n\nContent that will be modified.\n\nBlock C"
    doc1 = Doc(
        id="merge_mod_1",
        url="https://example.com/merge_mod",
        title="Merge Mod Initial",
        text_content=initial_text,
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        ingested_at=Doc.format_date(datetime.now()),
    )
    docdb.store_document(doc1)

    updated_text = "Block A\n\nModified content is now here.\n\nBlock C"
    doc2 = Doc(
        id="merge_mod_1",
        url="https://example.com/merge_mod",
        title="Merge Mod Updated",
        text_content=updated_text,
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        ingested_at=Doc.format_date(datetime.now()),
    )
    docdb.store_document(doc2)

    docs_by_url = docdb.get_documents_by_url("https://example.com/merge_mod")
    assert len(docs_by_url) == 1
    updated_doc = docs_by_url[0]
    assert updated_doc["title"] == "Merge Mod Updated"
    updated_chunks = docdb.get_duckdb_chunks(updated_doc["id"])
    reconstructed = docdb._reconstruct_text_from_chunks(updated_chunks)
    # Opcode merge prioritizes new content in replacements
    assert reconstructed == updated_text


def test_merge_deletion(docdb):
    """Test merging where a block is deleted."""
    initial_text = "Block A\n\nBlock B to be deleted\n\nBlock C"
    doc1 = Doc(
        id="merge_del_1",
        url="https://example.com/merge_del",
        title="Merge Del Initial",
        text_content=initial_text,
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        ingested_at=Doc.format_date(datetime.now()),
    )
    docdb.store_document(doc1)

    updated_text = "Block A\n\nBlock C"
    doc2 = Doc(
        id="merge_del_1",
        url="https://example.com/merge_del",
        title="Merge Del Updated",
        text_content=updated_text,
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        ingested_at=Doc.format_date(datetime.now()),
    )
    docdb.store_document(doc2)

    docs_by_url = docdb.get_documents_by_url("https://example.com/merge_del")
    assert len(docs_by_url) == 1
    updated_doc = docs_by_url[0]
    assert updated_doc["title"] == "Merge Del Updated"
    updated_chunks = docdb.get_duckdb_chunks(updated_doc["id"])
    reconstructed = docdb._reconstruct_text_from_chunks(updated_chunks)
    # Opcode merge handles deletion correctly
    assert reconstructed == updated_text


def test_merge_mixed_operations(docdb):
    """Test merging with addition, modification, and deletion."""
    initial_text = "Intro\n\nSection A (keep)\n\nSection B (modify)\n\nSection C (delete)\n\nOutro"
    doc1 = Doc(
        id="merge_mix_1",
        url="https://example.com/merge_mix",
        title="Merge Mix Initial",
        text_content=initial_text,
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        ingested_at=Doc.format_date(datetime.now()),
    )
    docdb.store_document(doc1)

    # Add D, Modify B, Delete C
    updated_text = (
        "Intro\n\nSection A (keep)\n\nSection B (MODIFIED!)\n\nSection D (added)\n\nOutro"
    )
    doc2 = Doc(
        id="merge_mix_1",
        url="https://example.com/merge_mix",
        title="Merge Mix Updated",
        text_content=updated_text,
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        ingested_at=Doc.format_date(datetime.now()),
    )
    docdb.store_document(doc2)

    docs_by_url = docdb.get_documents_by_url("https://example.com/merge_mix")
    assert len(docs_by_url) == 1
    updated_doc = docs_by_url[0]
    assert updated_doc["title"] == "Merge Mix Updated"
    updated_chunks = docdb.get_duckdb_chunks(updated_doc["id"])
    reconstructed = docdb._reconstruct_text_from_chunks(updated_chunks)
    assert reconstructed == updated_text


def test_merge_at_boundaries(docdb):
    """Test merging content added at the beginning and end."""
    initial_text = "Middle Content"
    doc1 = Doc(
        id="merge_bound_1",
        url="https://example.com/merge_bound",
        title="Merge Bound Initial",
        text_content=initial_text,
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        ingested_at=Doc.format_date(datetime.now()),
    )
    docdb.store_document(doc1)

    updated_text = "Start Content\n\nMiddle Content\n\nEnd Content"
    doc2 = Doc(
        id="merge_bound_1",
        url="https://example.com/merge_bound",
        title="Merge Bound Updated",
        text_content=updated_text,
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        ingested_at=Doc.format_date(datetime.now()),
    )
    docdb.store_document(doc2)

    docs_by_url = docdb.get_documents_by_url("https://example.com/merge_bound")
    assert len(docs_by_url) == 1
    updated_doc = docs_by_url[0]
    assert updated_doc["title"] == "Merge Bound Updated"
    updated_chunks = docdb.get_duckdb_chunks(updated_doc["id"])
    reconstructed = docdb._reconstruct_text_from_chunks(updated_chunks)
    assert reconstructed == updated_text
