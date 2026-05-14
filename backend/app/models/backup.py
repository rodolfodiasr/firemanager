from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BackupConfig(Base):
    __tablename__ = "backup_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    backup_type: Mapped[str] = mapped_column(String(20), nullable=False, default="platform")
    destination: Mapped[str] = mapped_column(String(20), nullable=False, default="local")
    schedule_cron: Mapped[str | None] = mapped_column(String(50), nullable=True)
    retention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=7)

    local_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    s3_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    s3_prefix: Mapped[str | None] = mapped_column(String(255), nullable=True)
    s3_region: Mapped[str | None] = mapped_column(String(50), nullable=True)
    s3_credentials_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    sftp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sftp_port: Mapped[int | None] = mapped_column(Integer, nullable=True, default=22)
    sftp_user: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sftp_credentials_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    sftp_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))

    jobs: Mapped[list[BackupJob]] = relationship("BackupJob", back_populates="config", cascade="all, delete-orphan")


class BackupJob(Base):
    __tablename__ = "backup_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    config_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("backup_configs.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    backup_type: Mapped[str] = mapped_column(String(20), nullable=False, default="platform")
    destination: Mapped[str] = mapped_column(String(20), nullable=False, default="local")
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))

    config: Mapped[BackupConfig] = relationship("BackupConfig", back_populates="jobs")
