"""Modelos ORM para o AI Assistant — sessões, mensagens e pastas."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class AssistantFolder(Base):
    __tablename__ = "assistant_folders"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#6366f1")
    is_team: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    min_role: Mapped[str] = mapped_column(String(20), nullable=False, default="analyst_n1")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    sessions: Mapped[list["AssistantSession"]] = relationship(
        "AssistantSession", back_populates="folder", lazy="select"
    )


class AssistantSession(Base):
    __tablename__ = "assistant_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    folder_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assistant_folders.id", ondelete="SET NULL"),
        nullable=True
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False, default="claude-sonnet-4-6")
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    shared_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # GLPI bridge — populated when session is opened from a GLPI ticket
    glpi_ticket_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    glpi_integration_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    glpi_itemtype: Mapped[str | None] = mapped_column(String(50), nullable=True)
    glpi_ticket_title: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    folder: Mapped["AssistantFolder | None"] = relationship(
        "AssistantFolder", back_populates="sessions", lazy="select"
    )
    messages: Mapped[list["AssistantMessage"]] = relationship(
        "AssistantMessage", back_populates="session", lazy="select",
        order_by="AssistantMessage.created_at"
    )


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assistant_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rag_context_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    message_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped["AssistantSession"] = relationship("AssistantSession", back_populates="messages")
