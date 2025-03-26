from datetime import datetime
from brocc_li.types.document import Document, Source


def test_document_from_twitter_data():
    """Test creating Document from Twitter extracted data."""
    # Sample data that would be extracted from Twitter
    twitter_data = {
        "url": "https://x.com/username/status/123456789",
        "author_name": "Test Author",
        "author_identifier": "username",
        "created_at": "2023-05-01T12:34:56Z",
        "content": {"content": "This is a test tweet", "raw_html": "<div>HTML</div>"},
        "metadata": {
            "replies": "10",
            "retweets": "20",
            "likes": "30",
        },
    }

    source_location = "https://x.com/i/bookmarks"

    # Create document from the data
    doc = Document.from_extracted_data(
        data=twitter_data, source=Source.TWITTER, source_location=source_location
    )

    # Verify core fields
    assert doc.id == Document.generate_id(twitter_data["url"])
    assert doc.url == twitter_data["url"]
    assert doc.author_name == twitter_data["author_name"]
    assert doc.author_identifier == twitter_data["author_identifier"]
    assert doc.created_at == twitter_data["created_at"]
    assert doc.content == twitter_data["content"]
    assert doc.metadata == twitter_data["metadata"]

    # Verify source information
    assert doc.source == Source.TWITTER
    assert doc.source_location == source_location
    assert doc.ingested_at != ""  # Should have a timestamp


def test_document_from_substack_data():
    """Test creating Document from Substack extracted data."""
    # Sample data that would be extracted from Substack
    substack_data = {
        "url": "https://example.substack.com/p/article-title",
        "title": "Test Article Title",
        "description": "This is a test article description",
        "author_name": "Substack Author",
        "created_at": "2023-06-15T10:20:30Z",
        "content": "Article content in markdown format",
        "metadata": {
            "publication": "Test Publication",
        },
    }

    source_location = "https://substack.com/inbox"

    # Create document from the data
    doc = Document.from_extracted_data(
        data=substack_data, source=Source.SUBSTACK, source_location=source_location
    )

    # Verify core fields
    assert doc.id == Document.generate_id(substack_data["url"])
    assert doc.url == substack_data["url"]
    assert doc.title == substack_data["title"]
    assert doc.description == substack_data["description"]
    assert doc.author_name == substack_data["author_name"]
    assert doc.created_at == substack_data["created_at"]
    assert doc.content == substack_data["content"]
    assert doc.metadata == substack_data["metadata"]

    # Verify source information
    assert doc.source == Source.SUBSTACK
    assert doc.source_location == source_location
    assert doc.ingested_at != ""  # Should have a timestamp


def test_document_id_generation():
    """Test document ID generation from URLs."""
    # Test with a valid URL
    url = "https://example.com/article/12345"
    doc_id = Document.generate_id(url)
    assert len(doc_id) == 16
    assert isinstance(doc_id, str)

    # Test with the same URL - should produce the same ID
    doc_id2 = Document.generate_id(url)
    assert doc_id == doc_id2

    # Test with different URL - should produce different ID
    different_url = "https://example.com/article/67890"
    different_id = Document.generate_id(different_url)
    assert doc_id != different_id

    # Test with empty URL - should generate a UUID
    empty_url_id = Document.generate_id("")
    assert len(empty_url_id) > 0  # UUID has more than 0 chars
    assert empty_url_id != doc_id


def test_document_date_formatting():
    """Test document date formatting."""
    # Create a specific datetime
    dt = datetime(2023, 7, 15, 14, 30, 45)

    # Format it using the Document's method
    formatted = Document.format_date(dt)

    # Verify format matches expectations
    assert "2023" in formatted
    assert "7" in formatted or "07" in formatted
    assert "15" in formatted
    assert "14" in formatted or "2" in formatted
    assert "30" in formatted
    assert "45" in formatted


def test_document_with_missing_fields():
    """Test creating Document with missing optional fields."""
    # Minimal required data
    minimal_data = {
        "url": "https://example.com/article",
    }

    # Create document with minimal data
    doc = Document.from_extracted_data(
        data=minimal_data,
        source=Source.TWITTER,  # Source enum value required
        source_location="https://example.com",
    )

    # Verify required fields
    assert doc.id == Document.generate_id(minimal_data["url"])
    assert doc.url == minimal_data["url"]
    assert doc.source == Source.TWITTER
    assert doc.source_location == "https://example.com"

    # Verify optional fields have default values
    assert doc.title is None
    assert doc.description is None
    assert doc.content is None
    assert doc.author_name is None
    assert doc.author_identifier is None
    assert doc.created_at is None
    assert doc.metadata == {}
    assert doc.ingested_at != ""
