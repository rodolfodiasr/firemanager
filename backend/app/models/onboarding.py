"""Fase 22 — Onboarding profiles and external system connectors."""
from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class ExternalConnectorType(str, enum.Enum):
    guacamole = "guacamole"
    tactical_rmm = "tactical_rmm"
    unifi = "unifi"


class ExternalConnector(Base):
    __tablename__ = "external_connectors"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(30), nullable=False)
    encrypted_config: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class OnboardingProfile(Base):
    __tablename__ = "onboarding_profiles"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ad_groups: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    systems: Mapped[list["OnboardingProfileSystem"]] = relationship(
        "OnboardingProfileSystem", back_populates="profile", cascade="all, delete-orphan", lazy="selectin"
    )


class OnboardingProfileSystem(Base):
    __tablename__ = "onboarding_profile_systems"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("onboarding_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    system_type: Mapped[str] = mapped_column(String(30), nullable=False)
    system_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    system_name: Mapped[str] = mapped_column(String(256), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    profile: Mapped["OnboardingProfile"] = relationship("OnboardingProfile", back_populates="systems")
