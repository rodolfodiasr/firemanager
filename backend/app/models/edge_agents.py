import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class EdgeAgent(Base):
    __tablename__ = "edge_agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    device_ids: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="offline")
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SsoConfig(Base):
    __tablename__ = "sso_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False, server_default="azure_ad")
    client_id: Mapped[str] = mapped_column(String(200), nullable=False)
    client_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    discovery_url: Mapped[str] = mapped_column(String(500), nullable=False)
    group_claim: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, server_default="groups")
    group_mapping: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    extra_config: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    sso_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class MarketplacePlugin(Base):
    __tablename__ = "marketplace_plugins"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    author_tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, server_default="connector")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    package_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    signature: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    tenant_installs: Mapped[list["TenantPlugin"]] = relationship("TenantPlugin", back_populates="plugin", cascade="all, delete-orphan")


class TenantPlugin(Base):
    __tablename__ = "tenant_plugins"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plugin_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("marketplace_plugins.id", ondelete="CASCADE"), nullable=False)
    installed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    installed_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    config: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    plugin: Mapped["MarketplacePlugin"] = relationship("MarketplacePlugin", back_populates="tenant_installs")


class RbacCustomRole(Base):
    __tablename__ = "rbac_custom_roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    permissions: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    assignments: Mapped[list["RbacRoleAssignment"]] = relationship("RbacRoleAssignment", back_populates="role", cascade="all, delete-orphan")


class RbacRoleAssignment(Base):
    __tablename__ = "rbac_role_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rbac_custom_roles.id", ondelete="CASCADE"), nullable=False)
    assigned_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    role: Mapped["RbacCustomRole"] = relationship("RbacCustomRole", back_populates="assignments")


class SsoRoleMapping(Base):
    __tablename__ = "sso_role_mappings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sso_config_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sso_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    external_group: Mapped[str] = mapped_column(String(300), nullable=False)
    platform_role: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
