from typing import ClassVar, Optional, Dict, Any
from pydantic import BaseModel
import hashlib
import uuid
from enum import Enum
from datetime import datetime
from brocc_li.utils.timestamp import READABLE_DATETIME_FORMAT
from brocc_li.types.extract_field import ExtractField


class Source(Enum):
    """Enum defining allowed document sources."""

    TWITTER = "twitter"
    SUBSTACK = "substack"


class DocumentExtractor(BaseModel):
    """Base schema defining how to extract document data.

    This class defines selectors and extraction methods for scraping.
    Individual platform extractors should inherit from this class.
    """

    # Container selector
    container: ClassVar[ExtractField]

    # Fields that must be extracted directly from the item
    url: ClassVar[ExtractField]
    title: ClassVar[ExtractField]
    description: ClassVar[ExtractField]
    content: ClassVar[ExtractField]
    author_name: ClassVar[ExtractField]
    author_identifier: ClassVar[ExtractField]
    created_at: ClassVar[ExtractField]
    metadata: ClassVar[ExtractField]  # Source-specific metadata


class Document(BaseModel):
    """Data model for a document.

    This class represents the actual document data after extraction.
    All platforms will produce this common document structure.
    """

    # Document identifier
    id: str

    # Core document fields
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    content: Any = None
    author_name: Optional[str] = None
    author_identifier: Optional[str] = None
    created_at: Optional[str] = None
    metadata: Dict[str, Any] = {}

    # Document source information
    source: Source
    source_location: str
    ingested_at: str = ""

    @staticmethod
    def generate_id(url: str) -> str:
        """Generate a unique ID from a URL."""
        if not url:
            return str(uuid.uuid4())
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    @staticmethod
    def format_date(dt: datetime) -> str:
        """Format a datetime consistently for all document dates."""
        return dt.strftime(READABLE_DATETIME_FORMAT)

    @classmethod
    def from_extracted_data(
        cls, data: Dict[str, Any], source: Source, source_location: str
    ) -> "Document":
        """Create a document from extracted data."""
        doc_id = cls.generate_id(data.get("url", ""))

        # Format ingestion timestamp consistently with our format
        ingested_at = cls.format_date(datetime.now())

        # Create a copy of data to avoid modifying the original
        processed_data = data.copy()

        return cls(
            id=doc_id,
            source=source,
            source_location=source_location,
            ingested_at=ingested_at,
            **processed_data,
        )
