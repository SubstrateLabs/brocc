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
# Only simple scalar fields that LanceDB can handle are included here
class BaseDocFields(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    contact_name: Optional[str] = None
    contact_identifier: Optional[str] = None
    # Use simple strings rather than Union types for LanceDB compatibility
    source: Optional[str] = None
    source_type: Optional[str] = None
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
        result = {}
        for k, v in data.items():
            if k in base_fields:
                # For source/source_type fields, convert enum objects to strings
                if k in ["source", "source_type"] and hasattr(v, "value"):
                    result[k] = v.value
                else:
                    result[k] = v

        return result


class Chunk(BaseModel):
    """
    Model for document chunks that contain the actual text content.

    This model represents the core chunk structure used throughout the application.
    It's stored in both DuckDB and LanceDB, but with different formatting:

    - In DuckDB: The content field is stored as a JSON string
    - In LanceDB: The content is wrapped in a structured format with a header and stored as a JSON string

    The content field is a list of dictionaries containing interleaved text and image items
    as returned by chunk_markdown.
    """

    id: str
    doc_id: str  # Reference to parent document
    chunk_index: int  # Position of this chunk
    chunk_total: int  # Total number of chunks in this document
    content: list[dict[str, Any]]  # The interleaved text/image list as returned by chunk_markdown


class Doc(BaseDocFields):
    id: str
    # Original enum types for source/source_type in the Doc model
    source: Union[Source, str, None] = None  # Override the string-only version from BaseDocFields
    source_type: Union[SourceType, str, None] = (
        None  # Override the string-only version from BaseDocFields
    )
    # Additional non-scalar fields that LanceDB can't handle
    participant_names: Optional[List[str]] = None
    participant_identifiers: Optional[List[str]] = None
    participant_metadatas: Optional[List[Dict[str, Any]]] = None
    geolocation: Optional[tuple[float, float]] = None
    keywords: List[str] = Field(default_factory=list)
    contact_metadata: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # NOTE: text_content is used for temporary storage during document processing
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


class LanceChunk(BaseDocFields, LanceModel):
    """
    LanceDB model for document chunks.

    This model is specifically designed for storing chunks in LanceDB, which differs from
    DuckDB storage in several ways:
    1. Content is wrapped in a structured format with a header
    2. The entire content structure is JSON serialized as a single string
    3. Document metadata is merged with chunk data
    4. The resulting data is used to generate vector embeddings

    Flow:
    1. Initial Chunking:
       - Document text_content is chunked into Chunk objects
       - Each Chunk.content is a list[dict[str, Any]] of interleaved text/image items
       - e.g. [{"type": "text", "text": "..."}, {"type": "image_url", "image_url": "..."}]
    2. LanceDB Storage Preparation:
       - For each Chunk, a metadata header is generated via chunk_header()
       - Content is wrapped in a standard structure: {"content": [...]}
       - Header is prepended as first content item
       - This entire structure is JSON serialized to a string for ChunkModel.content
    3. LanceDB Storage & Embedding:
       - JSON string is stored in LanceDB's chunks table
       - VoyageAIEmbeddingFunction picks up content field annotated as SourceField
       - During embedding:
         * JSON string is deserialized back to structured dict
         * Dict (with header + chunk content) is used to generate multimodal vector embedding
         * https://docs.voyageai.com/reference/multimodal-embeddings-api
    """

    # Fields from Chunk, but excluding 'content'
    id: str
    doc_id: str  # Reference to parent document
    chunk_index: int  # Position of this chunk
    chunk_total: int  # Total number of chunks in this document

    # JSON serialized interleaved text/image list
    content: str = ""
