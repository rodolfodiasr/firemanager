from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, ForeignKey, Integer, Float, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base


class WebAuditConfig(Base):
    __tablename__ = "web_audit_configs"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    collection_method: Mapped[str] = mapped_column(String(30), nullable=False, server_default="agent")
    gpo_share_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    poll_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    alert_on_malicious: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    alert_on_shadow_it: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class WebAuditEntry(Base):
    __tablename__ = "web_audit_entries"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    config_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("web_audit_configs.id", ondelete="CASCADE"), nullable=False)
    workstation: Mapped[str] = mapped_column(String(255), nullable=False)
    ad_user: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    browser: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    category: Mapped[str] = mapped_column(String(30), nullable=False, server_default="unknown")
    ai_analyzed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WebAuditFinding(Base):
    __tablename__ = "web_audit_findings"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("web_audit_entries.id", ondelete="SET NULL"), nullable=True)
    workstation: Mapped[str] = mapped_column(String(255), nullable=False)
    ad_user: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    finding_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    soar_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    soar_execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
