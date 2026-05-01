from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.device import DeviceCategory, DeviceStatus, VendorEnum


class DeviceCredentials(BaseModel):
    auth_type: str = "token"  # "token" | "user_pass" | "ssh"
    token: str | None = None
    username: str | None = None
    password: str | None = None
    ssh_port: int = 22
    vdom: str | None = None        # Fortinet: VDOM name (default "root")
    os_version: int | None = None  # SonicWall: 6 or 7
    cmdline_password: str | None = None  # HP Comware: _cmdline-mode on password


class DeviceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    vendor: VendorEnum
    category: DeviceCategory
    firmware_version: str | None = None
    host: str
    port: int = 443
    credentials: DeviceCredentials
    use_ssl: bool = True
    verify_ssl: bool = False
    notes: str | None = None


class DeviceUpdate(BaseModel):
    name: str | None = None
    category: DeviceCategory | None = None
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
    category: DeviceCategory
    firmware_version: str | None
    host: str
    port: int
    use_ssl: bool
    verify_ssl: bool
    status: DeviceStatus
    last_seen: datetime | None
    last_error: str | None
    notes: str | None
    bookstack_page_id: int | None = None
    bookstack_fm_page_id: int | None = None
    bookstack_doc_page_id: int | None = None
    bookstack_snapshot_page_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeviceBookstackLink(BaseModel):
    bookstack_page_id: int | None = None
    bookstack_fm_page_id: int | None = None
    bookstack_doc_page_id: int | None = None
    bookstack_snapshot_page_id: int | None = None


class DocDraftResult(BaseModel):
    page_url: str
    message: str
