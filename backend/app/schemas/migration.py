from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MigrationCreate(BaseModel):
    source_device_id: str
    target_device_id: str


class PortMappingUpdate(BaseModel):
    port_mapping: dict[str, str]  # { "source_port_name": "target_port_name" }


class MigrationRead(BaseModel):
    id: UUID
    tenant_id: UUID
    source_device_id: UUID
    target_device_id: UUID
    source_vendor: str
    target_vendor: str
    status: str
    source_config_raw: str | None
    target_config_raw: str | None
    migration_plan: dict | None
    port_mapping: dict | None
    commands_preview: str | None
    warnings: list | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MigrationListItem(BaseModel):
    id: UUID
    source_device_id: UUID
    target_device_id: UUID
    source_vendor: str
    target_vendor: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
