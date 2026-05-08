"""ORM models for Fase 26 — Golden Config Bundles REST-native."""
from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class ApplyStrategy(str, enum.Enum):
    cli_ssh = "cli_ssh"
    rest_api = "rest_api"
    manual_only = "manual_only"


class RollbackStrategy(str, enum.Enum):
    snapshot_restore = "snapshot_restore"
    delete_objects = "delete_objects"
    none = "none"


class BundleStatus(str, enum.Enum):
    draft = "draft"
    applying = "applying"
    applied = "applied"
    failed = "failed"
    rolled_back = "rolled_back"


class GoldenBundle(Base):
    __tablename__ = "golden_bundles"

    id:          Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id:   Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name:        Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    vendor:      Mapped[str] = mapped_column(String(30), nullable=False)
    variables:   Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at:  Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at:  Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    sections: Mapped[list[BundleSection]] = relationship(
        "BundleSection",
        back_populates="bundle",
        order_by="BundleSection.apply_order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class BundleSection(Base):
    __tablename__ = "bundle_sections"

    id:                   Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    bundle_id:            Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("golden_bundles.id", ondelete="CASCADE"), nullable=False)
    section_type:         Mapped[str] = mapped_column(String(50), nullable=False)
    template_id:          Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("golden_templates.id", ondelete="SET NULL"), nullable=True)
    rest_payload_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    apply_strategy:       Mapped[str] = mapped_column(String(20), nullable=False, default="rest_api")
    apply_order:          Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rollback_strategy:    Mapped[str] = mapped_column(String(30), nullable=False, default="none")

    bundle: Mapped[GoldenBundle] = relationship("GoldenBundle", back_populates="sections")


class BundleApply(Base):
    __tablename__ = "bundle_applies"

    id:              Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    bundle_id:       Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("golden_bundles.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id:       Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    status:          Mapped[str] = mapped_column(String(20), nullable=False, default="applying")
    variables_used:  Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    section_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at:      Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    completed_at:    Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    bundle: Mapped[GoldenBundle] = relationship("GoldenBundle", lazy="selectin")
