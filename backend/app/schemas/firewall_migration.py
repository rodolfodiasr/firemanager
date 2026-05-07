from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FirewallMigrationCreate(BaseModel):
    source_device_id: str
    target_device_id: str


class FirewallCommandsUpdate(BaseModel):
    commands_preview: str


class FirewallMigrationRead(BaseModel):
    id: UUID
    tenant_id: UUID
    source_device_id: UUID | None
    target_device_id: UUID | None
    source_vendor: str
    target_vendor: str
    status: str
    source_rules_raw: str | None
    migration_plan: dict | None
    commands_preview: str | None
    warnings: list | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FirewallMigrationListItem(BaseModel):
    id: UUID
    source_device_id: UUID | None
    target_device_id: UUID | None
    source_vendor: str
    target_vendor: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
