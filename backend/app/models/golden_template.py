"""ORM models for Fase 17 — Golden Config Templates."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class GoldenTemplate(Base):
    __tablename__ = "golden_templates"

    id:            Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id:     Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    name:          Mapped[str] = mapped_column(String(200), nullable=False)
    description:   Mapped[str | None] = mapped_column(Text, nullable=True)
    vendor:        Mapped[str] = mapped_column(String(50), nullable=False, default="any")
    category:      Mapped[str] = mapped_column(String(50), nullable=False)
    variables:     Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    content:       Mapped[str] = mapped_column(Text, nullable=False, default="")
    version:       Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active:     Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_system:     Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at:    Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at:    Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class GoldenTemplateVersion(Base):
    __tablename__ = "golden_template_versions"

    id:            Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    template_id:   Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("golden_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    version:       Mapped[int] = mapped_column(Integer, nullable=False)
    content:       Mapped[str] = mapped_column(Text, nullable=False)
    variables:     Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    change_note:   Mapped[str | None] = mapped_column(String(500), nullable=True)
    changed_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at:    Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
