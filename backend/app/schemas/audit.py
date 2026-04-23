from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditLogRead(BaseModel):
    id: UUID
    user_id: UUID | None
    device_id: UUID | None
    operation_id: UUID | None
    action: str
    details: dict | None
    ip_address: str | None
    record_hash: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogFilter(BaseModel):
    device_id: UUID | None = None
    user_id: UUID | None = None
    action: str | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
