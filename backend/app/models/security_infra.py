import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class VaultConfig(Base):
    __tablename__ = "vault_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    vault_url: Mapped[str] = mapped_column(String(500), nullable=False)
    auth_method: Mapped[str] = mapped_column(String(30), nullable=False, server_default="token")
    token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    role_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    secret_id_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_mount: Mapped[str] = mapped_column(String(100), nullable=False, server_default="secret")
    namespace: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_verified_ok: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    secret_refs: Mapped[list["VaultSecretRef"]] = relationship("VaultSecretRef", back_populates="vault_config", cascade="all, delete-orphan")


class VaultSecretRef(Base):
    __tablename__ = "vault_secret_refs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    vault_config_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vault_configs.id", ondelete="CASCADE"), nullable=False)
    alias: Mapped[str] = mapped_column(String(200), nullable=False)
    vault_path: Mapped[str] = mapped_column(String(500), nullable=False)
    vault_key: Mapped[str] = mapped_column(String(200), nullable=False, server_default="value")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    vault_config: Mapped["VaultConfig"] = relationship("VaultConfig", back_populates="secret_refs")


class OpaPolicy(Base):
    __tablename__ = "opa_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    package_name: Mapped[str] = mapped_column(String(200), nullable=False, server_default="eternity")
    rego_source: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    evaluations: Mapped[list["OpaEvaluation"]] = relationship("OpaEvaluation", back_populates="policy")


class OpaEvaluation(Base):
    __tablename__ = "opa_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("opa_policies.id", ondelete="SET NULL"), nullable=True)
    policy_name: Mapped[str] = mapped_column(String(200), nullable=False)
    input_data: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    result: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    allowed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    evaluated_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    policy: Mapped[Optional["OpaPolicy"]] = relationship("OpaPolicy", back_populates="evaluations")


class SecurityProfile(Base):
    __tablename__ = "security_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    profile_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default="hardening")
    controls: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    applied_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class PentestSchedule(Base):
    __tablename__ = "pentest_schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    scope: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pentest_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default="external")
    vendor: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="planned")
    findings_critical: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    findings_high: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    findings_medium: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    findings_low: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    report_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    remediation_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
