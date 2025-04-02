from datetime import datetime

from brocc_li.embed.embed_inputs import embed_header, split_markdown
from brocc_li.types.doc import Doc, Source, SourceType


def test_embed_header_complete():
    """Test embed_header with a complete doc."""
    # Create a test document with all fields populated
    doc = Doc(
        id="test-id-123",
        ingested_at=Doc.format_date(datetime.now()),
        url="https://example.com/test",
        title="Test Document",
        description="This is a test document",
        text_content="This should not appear in the header.",
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="test-location",
        created_at="2023-01-01T12:00:00Z",
    )

    expected_header = (
        "Title: Test Document\n"
        "Description: This is a test document\n"
        "Source: twitter\n"
        "Source Type: document\n"
        "URL: https://example.com/test"
    )

    assert embed_header(doc) == expected_header


def test_embed_header_minimal():
    """Test embed_header with minimal fields."""
    # Create a test document with only required fields
    doc = Doc(
        id="test-id-456",
        ingested_at=Doc.format_date(datetime.now()),
        source=Source.SUBSTACK,
        source_type=SourceType.CONVERSATION,
        source_location_identifier="test-location",
    )

    expected_header = "Source: substack\nSource Type: conversation"

    assert embed_header(doc) == expected_header


def test_embed_header_all_fields():
    """Test embed_header with all possible fields populated."""
    # Create a test document with all possible fields
    doc = Doc(
        id="test-id-789",
        ingested_at=Doc.format_date(datetime.now()),
        url="https://example.com/comprehensive",
        title="Comprehensive Test",
        description="Testing all Doc fields",
        text_content="This should not appear in the header.",
        contact_name="John Doe",
        contact_identifier="johndoe123",
        contact_metadata={"verified": True, "status": "active"},
        participant_names=["John", "Jane", "Bob"],
        participant_identifiers=["john123", "jane456", "bob789"],
        participant_metadatas=[{"role": "admin"}, {"role": "user"}, {"role": "guest"}],
        keywords=["test", "comprehensive", "all-fields"],
        metadata={"priority": "high", "category": "test"},
        source=Source.TWITTER,
        source_type=SourceType.CONVERSATION,
        source_location_identifier="comprehensive-test",
        source_location_name="Comprehensive Test Channel",
        created_at="2023-05-15T09:30:00Z",
        embedded_at="2023-05-15T10:00:00Z",
    )

    expected_header = (
        "Title: Comprehensive Test\n"
        "Description: Testing all Doc fields\n"
        "Source: twitter\n"
        "Source Type: conversation\n"
        "URL: https://example.com/comprehensive\n"
        "Contact: John Doe\n"
        "Contact ID: johndoe123\n"
        "Participants: John, Jane, Bob\n"
        "Source Location: Comprehensive Test Channel\n"
        "Keywords: test, comprehensive, all-fields\n"
        "Metadata: priority: high, category: test"
    )

    assert embed_header(doc) == expected_header


def test_embed_header_with_location_name():
    """Test embed_header with source location name."""
    # Create a test document with source location name
    doc = Doc(
        id="test-id-loc",
        ingested_at=Doc.format_date(datetime.now()),
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="test-id",
        source_location_name="Test Location",
    )

    expected_header = "Source: twitter\nSource Type: document\nSource Location: Test Location"

    assert embed_header(doc) == expected_header


def test_embed_header_with_metadata():
    """Test embed_header with metadata."""
    # Create a test document with metadata
    doc = Doc(
        id="test-id-meta",
        ingested_at=Doc.format_date(datetime.now()),
        source=Source.TWITTER,
        source_type=SourceType.DOCUMENT,
        source_location_identifier="test-id",
        metadata={"author": "Jane Smith", "views": 1234, "likes": 42},
    )

    expected_header = (
        "Source: twitter\n"
        "Source Type: document\n"
        "Metadata: author: Jane Smith, views: 1234, likes: 42"
    )

    assert embed_header(doc) == expected_header


def test_split_markdown_text_only():
    """Test splitting markdown content with text only."""
    markdown = "This is a simple text paragraph.\n\nThis is a second paragraph."

    segments = split_markdown(markdown)

    assert len(segments) == 1
    assert segments[0]["type"] == "text"
    assert segments[0]["text"] == markdown


def test_split_markdown_with_images():
    """Test splitting markdown content with images."""
    markdown = (
        "# Header\n\n"
        "This is a paragraph with an image below:\n\n"
        "![Image 1](https://example.com/image1.jpg)\n\n"
        "This is text between images.\n\n"
        "![Image 2](https://example.com/image2.png)\n\n"
        "This is the final paragraph."
    )

    segments = split_markdown(markdown)

    assert len(segments) == 5
    assert segments[0]["type"] == "text"
    assert segments[0]["text"].startswith("# Header")

    assert segments[1]["type"] == "image_url"
    assert segments[1]["image_url"] == "https://example.com/image1.jpg"

    assert segments[2]["type"] == "text"
    assert segments[2]["text"] == "This is text between images."

    assert segments[3]["type"] == "image_url"
    assert segments[3]["image_url"] == "https://example.com/image2.png"

    assert segments[4]["type"] == "text"
    assert segments[4]["text"] == "This is the final paragraph."


def test_split_markdown_with_consecutive_images():
    """Test splitting markdown content with consecutive images."""
    markdown = (
        "Start text\n\n"
        "![Image 1](https://example.com/image1.jpg)\n"
        "![Image 2](https://example.com/image2.png)\n\n"
        "End text"
    )

    segments = split_markdown(markdown)

    assert len(segments) == 4
    assert segments[0]["type"] == "text"
    assert segments[0]["text"] == "Start text"

    assert segments[1]["type"] == "image_url"
    assert segments[1]["image_url"] == "https://example.com/image1.jpg"

    assert segments[2]["type"] == "image_url"
    assert segments[2]["image_url"] == "https://example.com/image2.png"

    assert segments[3]["type"] == "text"
    assert segments[3]["text"] == "End text"


def test_split_markdown_with_image_only():
    """Test splitting markdown content with only an image."""
    markdown = "![Solo Image](https://example.com/solo.jpg)"

    segments = split_markdown(markdown)

    assert len(segments) == 1
    assert segments[0]["type"] == "image_url"
    assert segments[0]["image_url"] == "https://example.com/solo.jpg"
