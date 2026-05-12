"""Model ORM para rascunhos de documentação gerados a partir de sessões do AI Assistant."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class AssistantDocDraft(Base):
    __tablename__ = "assistant_doc_drafts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assistant_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # draft | approved | published | rejected
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    review_deadline: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # [{pattern, excerpt, field}]
    sanitizer_warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # [{bs_page_id, title, url, similarity}]
    similar_docs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    bookstack_page_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bookstack_page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    session: Mapped["AssistantSession"] = relationship(  # type: ignore[name-defined]
        "AssistantSession", lazy="select"
    )
