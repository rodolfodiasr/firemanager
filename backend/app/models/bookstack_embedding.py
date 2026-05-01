from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, TIMESTAMP, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base

_EMBEDDING_DIM = 1536  # text-embedding-3-small


class BookstackEmbedding(Base):
    __tablename__ = "bookstack_embeddings"
    __table_args__ = (
        UniqueConstraint("integration_id", "bs_page_id", "chunk_index", name="uq_bs_chunk"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    integration_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bs_page_id: Mapped[int] = mapped_column(Integer, nullable=False)
    bs_page_name: Mapped[str] = mapped_column(String(500), nullable=False)
    bs_page_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list] = mapped_column(Vector(_EMBEDDING_DIM), nullable=False)
    indexed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
