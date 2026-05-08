"""Fase 21 — Identity lifecycle: providers, users, actions, tasks."""
import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class ProviderType(str, enum.Enum):
    azure_ad = "azure_ad"
    google_workspace = "google_workspace"
    local_ad = "local_ad"


class ActionType(str, enum.Enum):
    offboard = "offboard"
    onboard = "onboard"


class ActionStatus(str, enum.Enum):
    pending_discovery = "pending_discovery"
    pending_approval = "pending_approval"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    skipped = "skipped"
    not_found = "not_found"


class SystemType(str, enum.Enum):
    azure_ad = "azure_ad"
    google_workspace = "google_workspace"
    local_ad = "local_ad"
    ssh_linux = "ssh_linux"
    winrm_windows = "winrm_windows"
    database = "database"
    guacamole = "guacamole"
    tactical_rmm = "tactical_rmm"
    unifi = "unifi"


class IdentityProvider(Base):
    __tablename__ = "identity_providers"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_type: Mapped[ProviderType] = mapped_column(
        SAEnum(ProviderType, name="identity_provider_type_enum", native_enum=False),
        nullable=False,
    )
    encrypted_config: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_sync_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IdentityUser(Base):
    __tablename__ = "identity_users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    provider_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("identity_providers.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    username: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    department: Mapped[str | None] = mapped_column(String(256), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    last_sign_in_raw: Mapped[str | None] = mapped_column(String(64), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class LifecycleAction(Base):
    __tablename__ = "lifecycle_actions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    action_type: Mapped[ActionType] = mapped_column(
        SAEnum(ActionType, name="lifecycle_action_type_enum", native_enum=False),
        nullable=False,
    )
    target_username: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[ActionStatus] = mapped_column(
        SAEnum(ActionStatus, name="lifecycle_action_status_enum", native_enum=False),
        nullable=False, default=ActionStatus.pending_discovery,
    )
    requested_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    tasks: Mapped[list["LifecycleTask"]] = relationship(
        "LifecycleTask", back_populates="action", cascade="all, delete-orphan",
        lazy="selectin",
    )


class LifecycleTask(Base):
    __tablename__ = "lifecycle_tasks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    action_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("lifecycle_actions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    system_type: Mapped[SystemType] = mapped_column(
        SAEnum(SystemType, name="lifecycle_system_type_enum", native_enum=False),
        nullable=False,
    )
    system_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    system_name: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="lifecycle_task_status_enum", native_enum=False),
        nullable=False, default=TaskStatus.pending,
    )
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    action: Mapped["LifecycleAction"] = relationship("LifecycleAction", back_populates="tasks")
