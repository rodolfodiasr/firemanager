"""ORM model for Fase 16 — Firewall Rule Migration."""
from __future__ import annotations

import enum
from uuid import uuid4

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class FirewallMigrationStatus(str, enum.Enum):
    pending   = "pending"
    analyzing = "analyzing"
    ready     = "ready"
    applying  = "applying"
    completed = "completed"
    failed    = "failed"


class FirewallMigration(Base):
    __tablename__ = "firewall_migrations"

    id:               Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id:        Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    source_device_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
    target_device_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
    source_vendor:    Mapped[str]  = mapped_column(String(50), nullable=False)
    target_vendor:    Mapped[str]  = mapped_column(String(50), nullable=False)
    status:           Mapped[str]  = mapped_column(
        Enum(FirewallMigrationStatus, name="firewall_migration_status"),
        nullable=False, default=FirewallMigrationStatus.pending,
    )
    source_rules_raw:  Mapped[str | None] = mapped_column(Text, nullable=True)
    migration_plan:    Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    commands_preview:  Mapped[str | None]  = mapped_column(Text, nullable=True)
    warnings:          Mapped[list | None] = mapped_column(JSONB, nullable=True)
    error_message:     Mapped[str | None]  = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
