import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class MigrationStatus(str, enum.Enum):
    pending   = "pending"    # created, dispatching analysis
    analyzing = "analyzing"  # fetching config + parsing + claude review
    ready     = "ready"      # commands preview ready, waiting for port-mapping review
    applying  = "applying"   # sending commands to target device
    completed = "completed"
    failed    = "failed"


class ConfigMigration(Base):
    __tablename__ = "config_migrations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    source_device_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("devices.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_device_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("devices.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_vendor: Mapped[str] = mapped_column(String(50), nullable=False)
    target_vendor: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[MigrationStatus] = mapped_column(
        Enum(MigrationStatus, native_enum=False),
        nullable=False, default=MigrationStatus.pending, index=True,
    )
    # Raw CLI config fetched from source device
    source_config_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Raw CLI config fetched from target device (for port naming context)
    target_config_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Normalized intermediate representation from parser
    migration_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # User-defined port mapping: { "source_port": "target_port" }
    port_mapping: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Generated CLI commands to apply on target device
    commands_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    # List of warnings from parser / renderer / claude
    warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
