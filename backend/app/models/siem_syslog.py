"""ORM models — F37.ext SIEM Syslog Forwarder."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class SiemSyslogConfig(Base):
    __tablename__ = "siem_syslog_configs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_host: Mapped[str] = mapped_column(String(300), nullable=False)
    target_port: Mapped[int] = mapped_column(Integer, nullable=False, default=514)
    protocol: Mapped[str] = mapped_column(String(10), nullable=False, default="tcp")
    tls_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tls_verify: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    facility: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    min_severity: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
    event_types: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_forward_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    events_forwarded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
