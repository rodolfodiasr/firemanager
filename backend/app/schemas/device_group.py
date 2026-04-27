from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DeviceInGroup(BaseModel):
    id: UUID
    name: str
    vendor: str
    category: str
    status: str
    host: str

    model_config = {"from_attributes": True}


class DeviceGroupRead(BaseModel):
    id: UUID
    tenant_id: UUID
    created_by: UUID
    name: str
    description: str | None
    device_count: int
    category_counts: dict[str, int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeviceGroupDetail(DeviceGroupRead):
    devices: list[DeviceInGroup]


class DeviceGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    device_ids: list[UUID] = Field(min_length=1, max_length=200)


class DeviceGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    device_ids: list[UUID] | None = None


class GroupBulkJobCreate(BaseModel):
    natural_language_input: str = Field(min_length=5)
