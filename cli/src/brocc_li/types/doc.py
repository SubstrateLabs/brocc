import uuid
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel

from brocc_li.types.extract_field import ExtractField
from brocc_li.utils.timestamp import format_datetime


class Source(Enum):
    TWITTER = "twitter"
    SUBSTACK = "substack"


class SourceType(Enum):
    DOCUMENT = "document"
    CONTACT = "contact"
    CONVERSATION = "conversation"


class DocExtractor(BaseModel):
    # Container selector
    container: ClassVar[ExtractField]

    # Fields that may be extracted directly from the item
    # (Other fields may be filled from surrounding context)
    url: ClassVar[ExtractField]
    title: ClassVar[ExtractField]
    description: ClassVar[ExtractField]
    text_content: ClassVar[ExtractField]  # should be markdown
    contact_name: ClassVar[ExtractField]
    contact_identifier: ClassVar[ExtractField]  # e.g. handle, phone, email
    contact_metadata: ClassVar[ExtractField]
    participant_names: ClassVar[ExtractField]
    participant_identifiers: ClassVar[ExtractField]
    participant_metadatas: ClassVar[ExtractField]
    metadata: ClassVar[ExtractField]
    keywords: ClassVar[ExtractField]
    created_at: ClassVar[ExtractField]

    # Selector for markdown content of navigated pages
    navigate_content_selector: ClassVar[str | None] = None


class Chunk(BaseModel):
    """Model for document chunks that contain the actual text content."""

    id: str
    doc_id: str  # Reference to parent document
    chunk_index: int  # Position of this chunk
    chunk_total: int  # Total number of chunks in this document
    content: list[dict[str, Any]]  # The interleaved text/image list as returned by chunk_markdown


class Doc(BaseModel):
    id: str
    ingested_at: str
    # extractable fields
    url: str | None = None
    title: str | None = None
    description: str | None = None
    # text_content is used for temporary storage during document processing
    # It holds the raw content before chunking and is NOT directly persisted in the database
    # Instead, it's processed by store_document and stored separately in the chunks table
    text_content: str | None = None
    contact_name: str | None = None
    contact_identifier: str | None = None
    contact_metadata: dict[str, Any] | None = None
    participant_names: list[str] | None = None
    participant_identifiers: list[str] | None = None
    participant_metadatas: list[dict[str, Any]] | None = None
    keywords: list[str] | None = None
    metadata: dict[str, Any] | None = None
    # metadata fields
    source: Source
    source_type: SourceType
    source_location_identifier: str
    source_location_name: str | None = None
    created_at: str | None = None
    # location stored as (longitude, latitude)
    location: tuple[float, float] | None = None

    @staticmethod
    def generate_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def format_date(dt: datetime) -> str:
        return format_datetime(dt)

    @classmethod
    def from_extracted_data(
        cls,
        data: dict[str, Any],
        source: Source,
        source_type: SourceType,
        source_location_identifier: str,
        source_location_name: str | None = None,
    ) -> "Doc":
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

    @classmethod
    def create_chunks_for_doc(
        cls,
        doc: "Doc",
        chunked_content: list[list[dict[str, Any]]],
    ) -> list[Chunk]:
        chunks = []
        chunk_total = len(chunked_content)

        for i, chunk_content in enumerate(chunked_content):
            # Create the chunk
            chunk = Chunk(
                id=cls.generate_id(),
                doc_id=doc.id,
                chunk_index=i,
                chunk_total=chunk_total,
                content=chunk_content,
            )
            chunks.append(chunk)

        return chunks
