import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Column, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR

from app.core.database import Base


class ContextChunk(Base):
    """
    Grounding knowledge chunk for Hybrid RAG.
    Stores dense vector embeddings (768-dim from text-embedding-004)
    and full-text search tsvector tokens for hybrid retrieval.
    """
    __tablename__ = "context_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_title = Column(String(255), nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)
    content = Column(Text, nullable=False)
    chunk_index = Column(String(20), default="0")
    source_url = Column(String(500), nullable=True)
    metadata_json = Column(JSON, nullable=True)

    # Hybrid Search columns
    embedding = Column(Vector(768), nullable=True)
    search_vector = Column(TSVECTOR, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_context_chunks_search_vector", search_vector, postgresql_using="gin"),
        Index(
            "ix_context_chunks_embedding",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
