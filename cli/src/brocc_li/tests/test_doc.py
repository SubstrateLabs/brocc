from datetime import datetime

from brocc_li.types.doc import BaseDocFields, Chunk, Doc, Source, SourceType


def test_doc_from_twitter_data():
    """Test creating Document from Twitter extracted data."""
    # Sample data that would be extracted from Twitter
    twitter_data = {
        "url": "https://x.com/username/status/123456789",
        "contact_name": "Test Author",
        "contact_identifier": "username",
        "created_at": "2023-05-01T12:34:56Z",
        "metadata": {
            "replies": "10",
            "retweets": "20",
            "likes": "30",
        },
    }

    source_location = "https://x.com/i/bookmarks"
    source_location_name = "Twitter Bookmarks"

    # Create document from the data
    doc = Doc.from_extracted_data(
        data=twitter_data,
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier=source_location,
        source_location_name=source_location_name,
    )

    # Verify core fields
    assert isinstance(doc.id, str)
    assert len(doc.id) == 36  # UUID length
    assert doc.url == twitter_data["url"]
    assert doc.contact_name == twitter_data["contact_name"]
    assert doc.contact_identifier == twitter_data["contact_identifier"]
    assert doc.created_at == twitter_data["created_at"]
    assert doc.metadata == twitter_data["metadata"]

    # Verify source information
    assert doc.source == Source.TWITTER
    assert doc.source_location_identifier == source_location
    assert doc.source_location_name == source_location_name
    assert doc.ingested_at != ""  # Should have a timestamp


def test_doc_from_substack_data():
    """Test creating Document from Substack extracted data."""
    # Sample data that would be extracted from Substack
    substack_data = {
        "url": "https://example.substack.com/p/article-title",
        "title": "Test Article Title",
        "description": "This is a test article description",
        "contact_name": "Substack Author",
        "created_at": "2023-06-15T10:20:30Z",
        "metadata": {
            "publication": "Test Publication",
        },
    }

    source_location = "https://substack.com/inbox"
    source_location_name = "Substack Inbox"
    # Create document from the data
    doc = Doc.from_extracted_data(
        data=substack_data,
        source=Source.SUBSTACK,
        source_type=SourceType.DOCUMENT,
        source_location_identifier=source_location,
        source_location_name=source_location_name,
    )

    # Verify core fields
    assert isinstance(doc.id, str)
    assert len(doc.id) == 36  # UUID length
    assert doc.url == substack_data["url"]
    assert doc.title == substack_data["title"]
    assert doc.description == substack_data["description"]
    assert doc.contact_name == substack_data["contact_name"]
    assert doc.created_at == substack_data["created_at"]
    assert doc.metadata == substack_data["metadata"]

    # Verify source information
    assert doc.source == Source.SUBSTACK
    assert doc.source_location_identifier == source_location
    assert doc.source_location_name == source_location_name
    assert doc.ingested_at != ""  # Should have a timestamp


def test_doc_date_formatting():
    """Test document date formatting."""
    # Create a specific datetime
    dt = datetime(2023, 7, 15, 14, 30, 45)

    # Format it using the Document's method
    formatted = Doc.format_date(dt)

    # Verify format matches expectations
    assert "2023" in formatted
    assert "7" in formatted or "07" in formatted
    assert "15" in formatted
    assert "14" in formatted or "2" in formatted
    assert "30" in formatted
    assert "45" in formatted


def test_doc_with_missing_fields():
    """Test creating Document with missing optional fields."""
    # Minimal required data
    minimal_data = {
        "url": "https://example.com/article",
    }

    # Create document with minimal data
    doc = Doc.from_extracted_data(
        data=minimal_data,
        source=Source.TWITTER,  # Source enum value required
        source_type=SourceType.DOCUMENT,
        source_location_identifier="https://example.com",
    )

    # Verify required fields
    assert isinstance(doc.id, str)
    assert len(doc.id) == 36  # UUID length
    assert doc.url == minimal_data["url"]
    assert doc.source == Source.TWITTER
    assert doc.source_location_identifier == "https://example.com"

    # Verify optional fields have default values
    assert doc.title is None
    assert doc.description is None
    assert doc.contact_name is None
    assert doc.contact_identifier is None
    assert doc.created_at is None
    assert doc.metadata == {}
    assert doc.source_location_name is None
    assert doc.ingested_at is not None


def test_chunk_creation():
    """Test creating Chunk objects."""
    content = [{"type": "text", "text": "This is chunk content"}]

    chunk = Chunk(
        id="chunk123",
        doc_id="doc456",
        chunk_index=1,
        chunk_total=3,
        content=content,
    )

    # Verify fields
    assert chunk.id == "chunk123"
    assert chunk.doc_id == "doc456"
    assert chunk.chunk_index == 1
    assert chunk.chunk_total == 3
    assert chunk.content == content
    # Verify content directly instead of using properties
    assert (
        "\n\n".join(item["text"] for item in chunk.content if item.get("type") == "text")
        == "This is chunk content"
    )
    assert [item["image_url"] for item in chunk.content if item.get("type") == "image_url"] == []


def test_doc_create_chunks_for_doc():
    """Test creating Chunk objects from a document."""
    # Create a document
    doc = Doc(
        id="test_doc",
        ingested_at=Doc.format_date(datetime.now()),
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="test_location",
    )

    # Create chunked content (similar to what chunk_markdown would return)
    chunked_content = [
        [{"type": "text", "text": "Chunk 1 content"}],
        [{"type": "text", "text": "Chunk 2 content"}],
        [{"type": "text", "text": "Chunk 3 content"}],
    ]

    # Create chunks
    chunks = Doc.create_chunks_for_doc(doc, chunked_content)

    # Verify chunks
    assert len(chunks) == 3

    # Check each chunk
    for i, chunk in enumerate(chunks):
        assert chunk.doc_id == "test_doc"
        assert chunk.chunk_index == i
        assert chunk.chunk_total == 3
        # Verify content directly
        text_content = "\n\n".join(
            item["text"] for item in chunk.content if item.get("type") == "text"
        )
        assert text_content == f"Chunk {i + 1} content"
        assert [
            item["image_url"] for item in chunk.content if item.get("type") == "image_url"
        ] == []

    # Test with multimodal content
    multimodal_content = [
        [
            {"type": "text", "text": "Text with image"},
            {"type": "image_url", "image_url": "https://example.com/image.jpg"},
        ]
    ]

    multimodal_chunks = Doc.create_chunks_for_doc(doc, multimodal_content)
    assert len(multimodal_chunks) == 1
    # Verify content directly
    assert (
        "\n\n".join(
            item["text"] for item in multimodal_chunks[0].content if item.get("type") == "text"
        )
        == "Text with image"
    )
    assert [
        item["image_url"]
        for item in multimodal_chunks[0].content
        if item.get("type") == "image_url"
    ] == ["https://example.com/image.jpg"]


def test_extract_base_fields():
    """Test that BaseDocFields.extract_base_fields correctly extracts fields."""
    # Create a dictionary with both base fields and extra fields
    test_data = {
        "id": "test123",  # Not in BaseDocFields
        "url": "https://example.com",  # In BaseDocFields
        "title": "Test Document",  # In BaseDocFields
        "description": "A test document",  # In BaseDocFields
        "text_content": "This is test content",  # Not in BaseDocFields
        "participant_names": ["Person 1", "Person 2"],  # Not in BaseDocFields
        "source": "twitter",  # In BaseDocFields
        "random_field": "random value",  # Not in BaseDocFields
    }

    # Extract base fields
    base_fields = BaseDocFields.extract_base_fields(test_data)

    # Check that only the base fields are included
    assert "id" not in base_fields, "id is not a BaseDocFields field"
    assert "random_field" not in base_fields, "random_field is not a BaseDocFields field"
    assert "text_content" not in base_fields, "text_content is not a BaseDocFields field"
    assert "participant_names" not in base_fields, "participant_names is not a BaseDocFields field"

    # Check that all base fields are included
    assert base_fields["url"] == "https://example.com"
    assert base_fields["title"] == "Test Document"
    assert base_fields["description"] == "A test document"
    assert base_fields["source"] == "twitter"

    # Check total count of fields
    extracted_field_count = len(base_fields)

    # Only fields present in the original data should be extracted
    # The number of extracted fields should equal the number of fields in the original
    # data that match BaseDocFields fields
    matching_field_count = len([f for f in test_data if f in BaseDocFields.model_fields])
    assert extracted_field_count == matching_field_count, "Should only extract matching fields"
