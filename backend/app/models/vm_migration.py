"""Fase 27 — VM Migration Planner models."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class HypervisorType(str, enum.Enum):
    vmware_vcenter = "vmware_vcenter"
    proxmox = "proxmox"
    hyper_v = "hyper_v"


class VmHypervisor(Base):
    __tablename__ = "vm_hypervisors"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    hypervisor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    host: Mapped[str] = mapped_column(String(500), nullable=False)
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_vm_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class VmInventory(Base):
    __tablename__ = "vm_inventory"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    hypervisor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("vm_hypervisors.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    vm_id: Mapped[str] = mapped_column(String(200), nullable=False)
    vm_name: Mapped[str] = mapped_column(String(500), nullable=False)
    power_state: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    os_type: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    cpu_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ram_mb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    disk_gb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ip_addresses: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    extra: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MigrationRunbook(Base):
    __tablename__ = "migration_runbooks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    vm_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    ai_runbook: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_hypervisor_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("vm_hypervisors.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_hypervisor_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("vm_hypervisors.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    bookstack_page_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
