"""ORM models for Fase 19 — AI Knowledge Base."""
from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base

_EMBEDDING_DIM = 1536  # text-embedding-3-small


class KnowledgeDocumentStatus(str, enum.Enum):
    pending  = "pending"
    indexing = "indexing"
    indexed  = "indexed"
    failed   = "failed"


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id:          Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id:   Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name:        Mapped[str]  = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_type:   Mapped[str]  = mapped_column(String(20), nullable=False)   # pdf, docx, md, txt
    file_size:   Mapped[int | None]  = mapped_column(Integer, nullable=True)
    content:     Mapped[str | None]  = mapped_column(Text, nullable=True)   # extracted text
    status:      Mapped[str]  = mapped_column(String(20), nullable=False, server_default="pending")
    chunk_count: Mapped[int]  = mapped_column(Integer, nullable=False, server_default="0")
    is_active:   Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    error:       Mapped[str | None]  = mapped_column(Text, nullable=True)
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_knowledge_chunk"),
    )

    id:          Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id:   Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int]  = mapped_column(Integer, nullable=False)
    chunk_text:  Mapped[str]  = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding:   Mapped[list] = mapped_column(Vector(_EMBEDDING_DIM), nullable=False)
    indexed_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
