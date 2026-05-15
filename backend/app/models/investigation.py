"""ORM models for iterative investigation sessions."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InvestigationSession(Base):
    __tablename__ = "investigation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    device_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    device_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)
    server_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    integration_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    agent_type: Mapped[str] = mapped_column(String(20), nullable=False)
    problem_description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planning")
    current_phase: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    synthesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    cross_domain_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cross_domain_hint: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    phases: Mapped[list[InvestigationPhase]] = relationship(
        "InvestigationPhase", back_populates="session",
        cascade="all, delete-orphan", order_by="InvestigationPhase.phase_number",
    )
    messages: Mapped[list[InvestigationMessage]] = relationship(
        "InvestigationMessage", back_populates="session",
        cascade="all, delete-orphan", order_by="InvestigationMessage.created_at",
    )


class InvestigationPhase(Base):
    __tablename__ = "investigation_phases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("investigation_sessions.id", ondelete="CASCADE"), nullable=False)
    phase_number: Mapped[int] = mapped_column(Integer, nullable=False)
    phase_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phase_purpose: Mapped[str | None] = mapped_column(Text, nullable=True)

    commands: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    command_states: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True, default=list)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings: Mapped[list[str]] = mapped_column(JSONB, nullable=True, default=list)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[InvestigationSession] = relationship("InvestigationSession", back_populates="phases")


class InvestigationMessage(Base):
    __tablename__ = "investigation_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("investigation_sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    phase_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[InvestigationSession] = relationship("InvestigationSession", back_populates="messages")
