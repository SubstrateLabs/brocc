from typing import ClassVar, Optional, Dict, Any, List
from pydantic import BaseModel
import uuid
from enum import Enum
from datetime import datetime
from brocc_li.utils.timestamp import format_datetime
from brocc_li.types.extract_field import ExtractField


class Source(Enum):
    """High level source providers"""

    TWITTER = "twitter"
    SUBSTACK = "substack"


class SourceType(Enum):
    """High level source types"""

    DOCUMENT = "document"
    CONTACT = "contact"
    CONVERSATION = "conversation"


class DocExtractor(BaseModel):
    """Base schema defining how to extract document data.

    This class defines selectors and extraction methods for scraping.
    Individual platform extractors should inherit from this class.
    """

    # Container selector
    container: ClassVar[ExtractField]

    # Fields that may be extracted directly from the item
    # (Other fields may be filled from surrounding context)
    url: ClassVar[ExtractField]
    title: ClassVar[ExtractField]
    description: ClassVar[ExtractField]
    text_content: ClassVar[ExtractField]
    contact_name: ClassVar[ExtractField]
    contact_identifier: ClassVar[ExtractField]
    contact_metadata: ClassVar[ExtractField]
    participant_names: ClassVar[ExtractField]
    participant_identifiers: ClassVar[ExtractField]
    participant_metadatas: ClassVar[ExtractField]
    metadata: ClassVar[ExtractField]
    keywords: ClassVar[ExtractField]
    created_at: ClassVar[ExtractField]

    # Selector for markdown content of navigated pages
    navigate_content_selector: ClassVar[Optional[str]] = None


class Doc(BaseModel):
    """
    document writ large
    """

    id: str
    ingested_at: str
    # extractable fields
    url: Optional[str] = None
    title: Optional[str] = None  # title
    description: Optional[str] = None
    text_content: Optional[str] = None  # markdown or plaintext
    contact_name: Optional[str] = None
    contact_identifier: Optional[str] = None  # e.g. handle, user id, email, phone
    contact_metadata: Optional[Dict[str, Any]] = None  # source-specific metadata
    participant_names: Optional[List[str]] = None  # e.g. message participants
    participant_identifiers: Optional[List[str]] = None
    participant_metadatas: Optional[List[Dict[str, Any]]] = None
    keywords: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None  # source-specific metadata
    # metadata fields
    source: Source
    source_type: SourceType
    source_location_identifier: str  # e.g. url, channel id, etc.
    source_location_name: Optional[str] = None  # e.g. url, channel id, etc.
    created_at: Optional[str] = None
    embedded_at: Optional[str] = None

    @staticmethod
    def generate_id() -> str:
        """Generate a unique ID from a URL."""
        return str(uuid.uuid4())

    @staticmethod
    def format_date(dt: datetime) -> str:
        """Format a datetime consistently for all document dates."""
        return format_datetime(dt)

    @classmethod
    def from_extracted_data(
        cls,
        data: Dict[str, Any],
        source: Source,
        source_type: SourceType,
        source_location_identifier: str,
        source_location_name: Optional[str] = None,
    ) -> "Doc":
        """Create a document from extracted data."""
        doc_id = cls.generate_id()

        # Format ingestion timestamp consistently with our format
        ingested_at = cls.format_date(datetime.now())

        # Create a copy of data to avoid modifying the original
        processed_data = data.copy()

        return cls(
            id=doc_id,
            source=source,
            source_type=source_type,
            source_location_identifier=source_location_identifier,
            source_location_name=source_location_name,
            ingested_at=ingested_at,
            **processed_data,
        )
