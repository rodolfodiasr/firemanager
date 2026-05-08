"""ORM models for Fase 20 — Database Connectors & Audit."""
from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class DbType(str, enum.Enum):
    postgresql = "postgresql"
    mysql      = "mysql"
    mariadb    = "mariadb"
    sqlserver  = "sqlserver"
    oracle     = "oracle"


class AuditStatus(str, enum.Enum):
    running   = "running"
    completed = "completed"
    failed    = "failed"


_DEFAULT_PORTS = {
    "postgresql": 5432,
    "mysql":      3306,
    "mariadb":    3306,
    "sqlserver":  1433,
    "oracle":     1521,
}


class DatabaseConnector(Base):
    __tablename__ = "database_connectors"

    id:          Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id:   Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    server_id:   Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("servers.id", ondelete="SET NULL"), nullable=True)
    name:        Mapped[str]  = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    db_type:     Mapped[str]  = mapped_column(String(20), nullable=False)
    host:        Mapped[str]  = mapped_column(String(255), nullable=False)
    port:        Mapped[int]  = mapped_column(Integer, nullable=False)
    database_name: Mapped[str] = mapped_column(String(200), nullable=False)
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_active:   Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    last_tested_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_ok:    Mapped[bool | None]     = mapped_column(Boolean, nullable=True)
    last_test_error: Mapped[str | None]      = mapped_column(Text, nullable=True)
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class DatabaseAuditReport(Base):
    __tablename__ = "database_audit_reports"

    id:           Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id:    Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    connector_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("database_connectors.id", ondelete="CASCADE"), nullable=False, index=True)
    status:       Mapped[str]  = mapped_column(String(20), nullable=False, server_default="running")
    db_version:   Mapped[str | None] = mapped_column(String(200), nullable=True)
    user_count:   Mapped[int]  = mapped_column(Integer, nullable=False, server_default="0")
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    users:        Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    findings:     Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    ai_summary:   Mapped[str]  = mapped_column(Text, nullable=False, server_default="")
    ai_recommendations: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    error:        Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
