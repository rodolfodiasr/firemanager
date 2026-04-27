from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.bulk_job import BulkJobStatus
from app.schemas.operation import OperationRead


class BulkJobCreate(BaseModel):
    device_ids: list[UUID] = Field(min_length=2, max_length=50)
    natural_language_input: str = Field(min_length=5)


class BulkJobRead(BaseModel):
    id: UUID
    tenant_id: UUID
    created_by: UUID
    description: str
    status: BulkJobStatus
    device_count: int
    completed_count: int
    failed_count: int
    intent: str | None
    error_summary: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BulkJobDetail(BulkJobRead):
    operations: list[OperationRead]
