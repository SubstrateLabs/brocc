from datetime import datetime

from brocc_li.embed.chunk_header import chunk_header
from brocc_li.types.doc import Doc, Source


def test_chunk_header_complete():
    """Test chunk_header with a complete doc."""
    # Create a test document with all fields populated
    doc = Doc(
        id="test-id-123",
        ingested_at=Doc.format_date(datetime.now()),
        url="https://example.com/test",
        title="Test Document",
        description="This is a test document",
        source=Source.CHROME,
        source_location_identifier="test-location",
        created_at="2023-01-01T12:00:00Z",
    )

    expected_header = (
        "Title: Test Document\n"
        "Description: This is a test document\n"
        "Source: chrome\n"
        "URL: https://example.com/test"
    )

    assert chunk_header(doc) == expected_header


def test_chunk_header_minimal():
    """Test chunk_header with minimal fields."""
    # Create a test document with only required fields
    doc = Doc(
        id="test-id-456",
        ingested_at=Doc.format_date(datetime.now()),
        source=Source.CHROME,
        source_location_identifier="test-location",
    )

    expected_header = "Source: chrome"

    assert chunk_header(doc) == expected_header


def test_chunk_header_all_fields():
    """Test chunk_header with all possible fields populated."""
    # Create a test document with all possible fields
    doc = Doc(
        id="test-id-789",
        ingested_at=Doc.format_date(datetime.now()),
        url="https://example.com/comprehensive",
        title="Comprehensive Test",
        description="Testing all Doc fields",
        contact_name="John Doe",
        contact_identifier="johndoe123",
        contact_metadata={"verified": True, "status": "active"},
        participant_names=["John", "Jane", "Bob"],
        participant_identifiers=["john123", "jane456", "bob789"],
        participant_metadatas=[{"role": "admin"}, {"role": "user"}, {"role": "guest"}],
        keywords=["test", "comprehensive", "all-fields"],
        metadata={"priority": "high", "category": "test"},
        source=Source.CHROME,
        source_location_identifier="comprehensive-test",
        source_location_name="Comprehensive Test Channel",
        created_at="2023-05-15T09:30:00Z",
    )

    expected_header = (
        "Title: Comprehensive Test\n"
        "Description: Testing all Doc fields\n"
        "Source: chrome\n"
        "URL: https://example.com/comprehensive\n"
        "Contact: John Doe\n"
        "Contact ID: johndoe123\n"
        "Participants: John, Jane, Bob\n"
        "Source Location: Comprehensive Test Channel\n"
        "Keywords: test, comprehensive, all-fields\n"
        "Metadata: priority: high, category: test"
    )

    assert chunk_header(doc) == expected_header


def test_chunk_header_with_location_name():
    """Test chunk_header with source location name."""
    # Create a test document with source location name
    doc = Doc(
        id="test-id-loc",
        ingested_at=Doc.format_date(datetime.now()),
        source=Source.CHROME,
        source_location_identifier="test-id",
        source_location_name="Test Location",
    )

    expected_header = "Source: chrome\nSource Location: Test Location"

    assert chunk_header(doc) == expected_header


def test_chunk_header_with_metadata():
    """Test chunk_header with metadata."""
    # Create a test document with metadata
    doc = Doc(
        id="test-id-meta",
        ingested_at=Doc.format_date(datetime.now()),
        source=Source.CHROME,
        source_location_identifier="test-id",
        metadata={"author": "Jane Smith", "views": 1234, "likes": 42},
    )

    expected_header = "Source: chrome\nMetadata: author: Jane Smith, views: 1234, likes: 42"

    assert chunk_header(doc) == expected_header
