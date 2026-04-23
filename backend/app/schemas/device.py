from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.device import DeviceStatus, VendorEnum


class DeviceCredentials(BaseModel):
    auth_type: str = "token"  # "token" | "user_pass"
    token: str | None = None
    username: str | None = None
    password: str | None = None


class DeviceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    vendor: VendorEnum
    firmware_version: str | None = None
    host: str
    port: int = 443
    credentials: DeviceCredentials
    use_ssl: bool = True
    verify_ssl: bool = False
    notes: str | None = None


class DeviceUpdate(BaseModel):
    name: str | None = None
    firmware_version: str | None = None
    host: str | None = None
    port: int | None = None
    credentials: DeviceCredentials | None = None
    use_ssl: bool | None = None
    verify_ssl: bool | None = None
    notes: str | None = None


class DeviceRead(BaseModel):
    id: UUID
    name: str
    vendor: VendorEnum
    firmware_version: str | None
    host: str
    port: int
    use_ssl: bool
    verify_ssl: bool
    status: DeviceStatus
    last_seen: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
