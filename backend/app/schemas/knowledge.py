from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class KnowledgeChunkCreate(BaseModel):
    document_title: str = Field(..., description="Title of the source document")
    category: str = Field(..., description="Document category (e.g. AUTH, BILLING, TECHNICAL)")
    content: str = Field(..., description="Text content of the knowledge chunk")
    chunk_index: str = Field(default="0", description="Sequence index of the chunk")
    source_url: str | None = Field(default=None, description="URL or documentation link")
    metadata_json: dict[str, Any] | None = Field(default=None, description="Arbitrary metadata")


class KnowledgeChunkRead(BaseModel):
    id: str
    document_title: str
    category: str
    content: str
    chunk_index: str
    source_url: str | None
    metadata_json: dict[str, Any] | None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class HybridSearchQuery(BaseModel):
    query: str = Field(..., min_length=2, description="Natural language search query")
    category: str | None = Field(default=None, description="Optional category filter")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to retrieve")
    dense_weight: float = Field(default=0.6, ge=0.0, le=1.0, description="Weight for semantic vector similarity")
    keyword_weight: float = Field(default=0.4, ge=0.0, le=1.0, description="Weight for BM25 keyword score")


class HybridSearchResult(BaseModel):
    id: str
    document_title: str
    category: str
    content: str
    combined_score: float
    vector_score: float
    keyword_score: float
    source_url: str | None = None
