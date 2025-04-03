import uuid
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional, Union

from lancedb.pydantic import LanceModel
from pydantic import BaseModel, Field

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


# Base model with common fields shared between Doc and ChunkModel
class BaseDocFields(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    contact_name: Optional[str] = None
    contact_identifier: Optional[str] = None
    contact_metadata: Dict[str, Any] = Field(default_factory=dict)
    participant_names: Optional[List[str]] = None
    participant_identifiers: Optional[List[str]] = None
    participant_metadatas: Optional[List[Dict[str, Any]]] = None
    # location stored as (longitude, latitude)
    location: Optional[tuple[float, float]] = None
    keywords: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source: Union[Source, str, None] = None
    source_type: Union[SourceType, str, None] = None
    source_location_identifier: Optional[str] = None
    source_location_name: Optional[str] = None
    created_at: Optional[str] = None
    ingested_at: Optional[str] = None

    @classmethod
    def extract_base_fields(cls, data: dict[str, Any]) -> dict[str, Any]:
        """
        Extract all fields that belong to BaseDocFields from a dictionary.
        Uses the model definition as the source of truth.

        Args:
            data: A dictionary containing document data

        Returns:
            A dictionary containing only the base document fields
        """
        # Get all field names from the model
        base_fields = set(cls.model_fields.keys())

        # Extract matching fields from the data
        return {k: v for k, v in data.items() if k in base_fields}


class Chunk(BaseModel):
    """Model for document chunks that contain the actual text content."""

    id: str
    doc_id: str  # Reference to parent document
    chunk_index: int  # Position of this chunk
    chunk_total: int  # Total number of chunks in this document
    content: list[dict[str, Any]]  # The interleaved text/image list as returned by chunk_markdown


class Doc(BaseDocFields):
    id: str
    # text_content is used for temporary storage during document processing
    # It holds the raw content before chunking and is NOT directly persisted in the database
    # Instead, it's processed by store_document and stored separately in the chunks table
    text_content: Optional[str] = None

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


# ChunkModel inherits from Chunk, BaseDocFields and LanceModel
class ChunkModel(Chunk, BaseDocFields, LanceModel):
    """
    Model for chunks stored in LanceDB with embeddings.
    Inherits from:
    - Chunk (for chunk structure)
    - BaseDocFields (for doc metadata)
    - LanceModel (for vector DB storage)

    In doc_db.py, a subclass with embedding fields is created:

    class ChunkModelWithEmbedding(ChunkModel):
        text: str = embedding_func.SourceField()
        vector: Any = embedding_func.VectorField()

    This approach keeps ChunkModel reusable while allowing
    specific embedding functions to be used at runtime.
    """

    # Shared fields with Doc are inherited from BaseDocFields
    # The embedding fields will be added in doc_db.py:
    # text: str - SourceField for the embedding function
    # vector: Any - VectorField produced by the embedding function
