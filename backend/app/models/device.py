import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum, Integer, String, TIMESTAMP, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class VendorEnum(str, enum.Enum):
    fortinet = "fortinet"
    sonicwall = "sonicwall"
    pfsense = "pfsense"
    opnsense = "opnsense"
    mikrotik = "mikrotik"
    endian = "endian"


class DeviceStatus(str, enum.Enum):
    online = "online"
    offline = "offline"
    unknown = "unknown"
    error = "error"


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    vendor: Mapped[VendorEnum] = mapped_column(Enum(VendorEnum), nullable=False)
    firmware_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=443)
    # Credentials encrypted with Fernet (AES-256)
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    use_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus), nullable=False, default=DeviceStatus.unknown
    )
    last_seen: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
