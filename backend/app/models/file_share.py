"""ORM models — F36.ext File Share Governance."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class FileShareConfig(Base):
    __tablename__ = "file_share_configs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    server_hostname: Mapped[str] = mapped_column(String(200), nullable=False)
    unc_root: Mapped[str] = mapped_column(String(500), nullable=False)
    edge_agent_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("edge_agents.id", ondelete="SET NULL"), nullable=True)
    config_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    scan_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_scan_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_scan_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    shares: Mapped[list["FileShareShare"]] = relationship("FileShareShare", back_populates="config", cascade="all, delete-orphan")


class FileShareShare(Base):
    __tablename__ = "file_share_shares"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    config_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("file_share_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    share_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unc_path: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    abe_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    health_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    health_issues: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    acl_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scanned_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    config: Mapped["FileShareConfig"] = relationship("FileShareConfig", back_populates="shares")
    acl_entries: Mapped[list["FileShareAclEntry"]] = relationship("FileShareAclEntry", back_populates="share", cascade="all, delete-orphan")


class FileShareAclEntry(Base):
    __tablename__ = "file_share_acl_entries"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    share_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("file_share_shares.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    folder_path: Mapped[str] = mapped_column(Text, nullable=False)
    principal_name: Mapped[str] = mapped_column(String(300), nullable=False)
    principal_type: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    permission_type: Mapped[str] = mapped_column(String(50), nullable=False)
    inherited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_deny: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scanned_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    share: Mapped["FileShareShare"] = relationship("FileShareShare", back_populates="acl_entries")
