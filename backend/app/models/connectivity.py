"""ORM model for Fase 18 — Network Connectivity Analysis."""
from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ConnectivityStatus(str, enum.Enum):
    pending   = "pending"
    running   = "running"
    completed = "completed"
    failed    = "failed"


class ConnectivityAnalysis(Base):
    __tablename__ = "connectivity_analyses"

    id:        Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    device_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(
        Enum(ConnectivityStatus, name="connectivity_status"),
        nullable=False, default=ConnectivityStatus.pending,
    )

    routes:          Mapped[list | None]  = mapped_column(JSONB, nullable=True)
    bgp_peers:       Mapped[list | None]  = mapped_column(JSONB, nullable=True)
    ospf_neighbors:  Mapped[list | None]  = mapped_column(JSONB, nullable=True)
    sdwan_services:  Mapped[list | None]  = mapped_column(JSONB, nullable=True)
    anomalies:       Mapped[list | None]  = mapped_column(JSONB, nullable=True)
    ai_summary:      Mapped[str | None]   = mapped_column(Text,  nullable=True)
    ai_recommendations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    error:           Mapped[str | None]   = mapped_column(Text,  nullable=True)

    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
