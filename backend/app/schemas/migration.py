from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MigrationCreate(BaseModel):
    source_device_id: str
    target_device_id: str
    ai_level: int = 2


class PortMappingUpdate(BaseModel):
    port_mapping: dict[str, str]  # { "source_port_name": "target_port_name" }


class CommandsUpdate(BaseModel):
    commands_preview: str


class RegenerateRequest(BaseModel):
    port_mapping: dict[str, str] | None = None


class InterfaceAdd(BaseModel):
    name: str
    target_name: str
    mode: str = "access"
    pvid: str | None = None
    tagged_vlans: list[str] = []
    description: str | None = None
    port_type: str = "ethernet"


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
    ai_level: int
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
    ai_level: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
