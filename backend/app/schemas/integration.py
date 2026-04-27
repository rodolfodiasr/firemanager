from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.integration import IntegrationType


class IntegrationCreate(BaseModel):
    type: IntegrationType
    name: str
    config: dict          # plaintext — encrypted server-side
    is_active: bool = True
    tenant_id: UUID | None = None  # None = global (super admin only)


class IntegrationUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    is_active: bool | None = None


class IntegrationRead(BaseModel):
    id: UUID
    tenant_id: UUID | None
    type: IntegrationType
    name: str
    is_active: bool
    scope: str            # "global" | "tenant"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestResult(BaseModel):
    success: bool
    message: str
    latency_ms: float | None = None
