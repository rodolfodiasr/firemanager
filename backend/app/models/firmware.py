from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class DeviceFirmwareVersion(Base):
    __tablename__ = "device_firmware_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    version: Mapped[str] = mapped_column(String(100))
    vendor_label: Mapped[str] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(200))
    build: Mapped[str | None] = mapped_column(String(50))
    read_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now())
    read_method: Mapped[str] = mapped_column(String(20), server_default="rest")
    raw_output: Mapped[str | None] = mapped_column(Text)


class FirmwareCVE(Base):
    __tablename__ = "firmware_cves"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cve_id: Mapped[str] = mapped_column(String(30), unique=True)
    vendor: Mapped[str] = mapped_column(String(50))
    product: Mapped[str] = mapped_column(String(100))
    affected_versions: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    cvss_v3: Mapped[float | None] = mapped_column(Float)
    cvss_v2: Mapped[float | None] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(20), server_default="UNKNOWN")
    description: Mapped[str] = mapped_column(Text, server_default="")
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    modified_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    cpe_uri: Mapped[str | None] = mapped_column(String(500))
    nvd_url: Mapped[str] = mapped_column(String(300), server_default="")
    synced_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now())


class DeviceFirmwareVulnerability(Base):
    __tablename__ = "device_firmware_vulnerabilities"
    __table_args__ = (UniqueConstraint("device_id", "cve_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    cve_id: Mapped[str] = mapped_column(String(30))
    device_version: Mapped[str] = mapped_column(String(100))
    detected_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now())
    status: Mapped[str] = mapped_column(String(20), server_default="open")
    accepted_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    accepted_reason: Mapped[str | None] = mapped_column(Text)
    patched_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
