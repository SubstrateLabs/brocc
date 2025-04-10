import os
import shutil
import tempfile
from datetime import datetime

import numpy as np
import pytest

from brocc_li.doc_db import DocDB
from brocc_li.embed.voyage import VoyageAIEmbeddingFunction
from brocc_li.tests.generate_test_markdown import generate_test_markdown
from brocc_li.types.doc import Doc, Source


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
    """Create a DocDB instance with temporary databases and mocked API calls."""

    # Mock the Voyage API call directly to prevent any HTTP requests
    def mock_call_api(self, payload):
        """Directly mock the API call to prevent HTTP requests"""
        # Generate deterministic embeddings based on a hash of the input
        # Extract input text from the payload
        inputs = payload.get("inputs", [])
        embeddings = []
        for i, _inp in enumerate(inputs):
            # Create deterministic embedding based on position
            np.random.seed(42 + i)
            embeddings.append(np.random.normal(0, 0.1, 1024).astype(np.float32).tolist())
        return {"embeddings": embeddings}

    monkeypatch.setattr(VoyageAIEmbeddingFunction, "_call_api", mock_call_api)
    db = DocDB(db_path=temp_db_path, lance_path=temp_lance_path)
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
        source=Source.CHROME,
        source_location_identifier="https://example.com/test",
        source_location_name="Test Source Location",
        ingested_at=Doc.format_date(now),
        geolocation=None,
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
    sample_lance_document.text_content = rich_content
    lance_docdb.store_document(sample_lance_document)
    results = lance_docdb.vector_search("test document", limit=5)
    assert len(results) > 0, "Should return at least one search result"
    for result in results:
        assert "id" in result, "Result should have an id"
        assert "doc_id" in result, "Result should have a doc_id"
        assert "score" in result, "Result should have a similarity score"
        assert result["doc_id"] == sample_lance_document.id, "Result should be from our document"
        assert result["title"] == sample_lance_document.title, "Title should match"
        assert result["source"] == Source.CHROME.value, "Source should match"


def test_delete_from_lance(lance_docdb, sample_lance_document):
    """Test deleting documents from LanceDB."""
    lance_docdb.store_document(sample_lance_document)
    results_before = lance_docdb.vector_search("test document", limit=5)
    assert len(results_before) > 0, "Document should be found in vector search before deletion"
    with lance_docdb._get_connection() as conn:
        lance_docdb._delete_chunks(conn, sample_lance_document.id)
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
        source=Source.CHROME,
        source_location_identifier="multimodal_test_location",
        source_location_name="Multimodal Test Location",
        ingested_at=Doc.format_date(datetime.now()),
    )

    # Store the document - should trigger the real _store_in_lance
    lance_docdb.store_document(doc)

    # Verify chunks were created in the relational database
    chunks = lance_docdb.get_duckdb_chunks("multimodal_test")

    # Verify chunks contain both text and images
    assert len(chunks) > 0

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

    # Test the real vector search with a query about images
    results = lance_docdb.vector_search("document with images", limit=5)
    assert len(results) > 0, "Should return search results for multimodal content"

    # Check if any result contains the multimodal document
    found_doc = False
    for result in results:
        if result["doc_id"] == "multimodal_test":
            found_doc = True
            break

    assert found_doc, "Should find multimodal document in search results"
