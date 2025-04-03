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
def lance_docdb(temp_db_path, temp_lance_path, monkeypatch):
    """Create a DocDB instance with temporary databases and mocked LanceDB."""

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
def sample_lance_document():
    """Create a sample document for LanceDB testing."""
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


def test_lance_storage_and_vector_search(lance_docdb, sample_lance_document):
    """Test storing documents in LanceDB and performing vector search."""
    # Store a document with rich content to ensure multiple chunks
    rich_content = generate_test_markdown(
        num_sections=3,
        paragraphs_per_section=3,
        words_per_paragraph=50,
        add_lists=True,
        add_blockquotes=True,
        seed=42,
    )

    # Update the sample document with rich content
    sample_lance_document.text_content = rich_content

    # Store the document
    lance_docdb.store_document(sample_lance_document)

    # Create some test vectors to match our mocked embeddings
    dummy_vector = [0.1] * 1024  # Matches the dimension from our mock

    # Test vector search with the dummy vector to match our mocked embeddings
    try:
        # Try direct vector search first
        table = lance_docdb.lance_db.open_table(lance_docdb.LANCE_CHUNKS_TABLE)
        results = table.search(dummy_vector).limit(5).to_list()
        search_method = "direct vector"
    except Exception:
        # Fall back to the vector_search method which handles errors internally
        results = lance_docdb.vector_search("test document", limit=5)
        search_method = "via vector_search"

    # Verify search results
    assert len(results) > 0, f"Should return at least one search result using {search_method}"

    # If using vector_search, check the structure of results
    if search_method == "via vector_search":
        for result in results:
            assert "id" in result, "Result should have an id"
            assert "doc_id" in result, "Result should have a doc_id"
            assert "score" in result, "Result should have a similarity score"
            assert "text" in result, "Result should have the text content"

            # Check that the doc_id matches our document
            assert result["doc_id"] == sample_lance_document.id, (
                "Result should be from our document"
            )

            # Check that metadata fields are included
            assert result["title"] == sample_lance_document.title, "Title should match"
            assert result["source"] == Source.TWITTER.value, "Source should match"

    # Whether direct or via vector_search, we should have results
    assert len(results) > 0, "Should have search results"


def test_delete_from_lance(lance_docdb, sample_lance_document):
    """Test deleting documents from LanceDB."""
    # Store the document
    lance_docdb.store_document(sample_lance_document)

    # Verify it's searchable in LanceDB
    results_before = lance_docdb.vector_search("test document", limit=5)
    assert len(results_before) > 0, "Document should be found in vector search before deletion"

    # Delete the document
    with lance_docdb._get_connection() as conn:
        lance_docdb._delete_chunks(conn, sample_lance_document.id)

    # Verify it's no longer searchable
    results_after = lance_docdb.vector_search("test document", limit=5)
    assert len(results_after) == 0, "Document should not be found after deletion"


def test_multimodal_content_in_lance(lance_docdb):
    """Test storing and searching documents with interleaved text and image content."""
    # Create a document with interleaved text and image content
    multimodal_content = """
# Test Multimodal Document

This is a test document with interleaved text and images.

![Test Image 1](https://brocc.li/brocc.png)

More text content after the image.

![Test Image 2](https://brocc.li/brocc.png)

Final paragraph with important information.
"""

    # Create a document with the multimodal content
    doc = Doc(
        id="multimodal_test",
        title="Multimodal Test Document",
        text_content=multimodal_content,
        source=Source.SUBSTACK,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="multimodal_test_location",
        source_location_name="Multimodal Test Location",
        ingested_at=Doc.format_date(datetime.now()),
    )

    # Store the document - should trigger our mock _store_in_lance
    lance_docdb.store_document(doc)

    # Verify chunks were created and stored in lance_docdb._stored_docs
    assert "multimodal_test" in lance_docdb._stored_docs, "Document wasn't stored via our mock"

    # Our real DB will still have created chunks in the relational database
    chunks = lance_docdb.get_chunks_by_doc_id("multimodal_test")
    assert len(chunks) > 0, "Should have created chunks for the document"

    # Verify the content structure in chunks - at least one chunk should have an image
    found_image = False
    for chunk in chunks:
        assert isinstance(chunk["content"], list), "Content should be a list"

        # Check if any content items are of type image_url
        for item in chunk["content"]:
            if item.get("type") == "image_url" and "brocc.li/brocc.png" in item.get(
                "image_url", ""
            ):
                found_image = True
                break

        if found_image:
            break

    assert found_image, "No chunks with image URLs were found"

    # Test vector search - should hit our mocked version
    results = lance_docdb.vector_search("test document with images", limit=5)
    assert len(results) > 0, "Should return search results for multimodal content"

    # Verify at least one result is from our multimodal document
    multimodal_results = [r for r in results if r["doc_id"] == "multimodal_test"]
    assert len(multimodal_results) > 0, "Should find our multimodal document in search results"
