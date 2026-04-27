import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


_DEFAULT_CATEGORY = "firewall"


class VendorEnum(str, enum.Enum):
    # Firewalls
    fortinet  = "fortinet"
    sonicwall = "sonicwall"
    pfsense   = "pfsense"
    opnsense  = "opnsense"
    mikrotik  = "mikrotik"
    endian    = "endian"
    # Routers / Switches
    cisco_ios  = "cisco_ios"
    cisco_nxos = "cisco_nxos"
    juniper    = "juniper"
    aruba      = "aruba"
    ubiquiti   = "ubiquiti"
    dell       = "dell"


class DeviceCategory(str, enum.Enum):
    firewall  = "firewall"
    router    = "router"
    switch    = "switch"
    l3_switch = "l3_switch"


class DeviceStatus(str, enum.Enum):
    online = "online"
    offline = "offline"
    unknown = "unknown"
    error = "error"


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    vendor: Mapped[VendorEnum] = mapped_column(Enum(VendorEnum, native_enum=False), nullable=False)
    firmware_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=443)
    # Credentials encrypted with Fernet (AES-256)
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    use_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus, native_enum=False), nullable=False, default=DeviceStatus.unknown
    )
    last_seen: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    category: Mapped[DeviceCategory] = mapped_column(
        Enum(DeviceCategory, native_enum=False), nullable=False, default=DeviceCategory.firewall
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
