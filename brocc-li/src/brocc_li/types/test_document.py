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
        "content": "This is a test tweet",
        "metadata": {
            "replies": "10",
            "retweets": "20",
            "likes": "30",
        },
    }

    source_location = "https://x.com/i/bookmarks"
    source_location_name = "Twitter Bookmarks"

    # Create document from the data
    doc = Document.from_extracted_data(
        data=twitter_data,
        source=Source.TWITTER,
        source_location_identifier=source_location,
        source_location_name=source_location_name,
    )

    # Verify core fields
    assert doc.id == Document.generate_id()
    assert doc.url == twitter_data["url"]
    assert doc.author_name == twitter_data["author_name"]
    assert doc.author_identifier == twitter_data["author_identifier"]
    assert doc.created_at == twitter_data["created_at"]
    assert doc.text_content == twitter_data["content"]
    assert doc.metadata == twitter_data["metadata"]

    # Verify source information
    assert doc.source == Source.TWITTER
    assert doc.source_location_identifier == source_location
    assert doc.source_location_name == source_location_name
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
    source_location_name = "Substack Inbox"
    # Create document from the data
    doc = Document.from_extracted_data(
        data=substack_data,
        source=Source.SUBSTACK,
        source_location_identifier=source_location,
        source_location_name=source_location_name,
    )

    # Verify core fields
    assert doc.id == Document.generate_id(substack_data["url"])
    assert doc.url == substack_data["url"]
    assert doc.title == substack_data["title"]
    assert doc.description == substack_data["description"]
    assert doc.author_name == substack_data["author_name"]
    assert doc.created_at == substack_data["created_at"]
    assert doc.text_content == substack_data["content"]
    assert doc.metadata == substack_data["metadata"]

    # Verify source information
    assert doc.source == Source.SUBSTACK
    assert doc.source_location_identifier == source_location
    assert doc.source_location_name == source_location_name
    assert doc.ingested_at != ""  # Should have a timestamp


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
        source_location_identifier="https://example.com",
    )

    # Verify required fields
    assert doc.id == Document.generate_id()
    assert doc.url == minimal_data["url"]
    assert doc.source == Source.TWITTER
    assert doc.source_location_identifier == "https://example.com"

    # Verify optional fields have default values
    assert doc.title is None
    assert doc.description is None
    assert doc.text_content is None
    assert doc.author_name is None
    assert doc.author_identifier is None
    assert doc.created_at is None
    assert doc.metadata == {}
    assert doc.ingested_at != ""
    assert doc.source_location_name is None
