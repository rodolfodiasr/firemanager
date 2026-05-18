from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.remediation import CommandStatus, RemediationRisk, RemediationStatus


class RemediationCommandRead(BaseModel):
    id: UUID
    plan_id: UUID
    order: int
    description: str
    command: str
    risk: RemediationRisk
    status: CommandStatus
    output: str | None
    executed_at: datetime | None

    model_config = {"from_attributes": True}


class RemediationPlanRead(BaseModel):
    id: UUID
    tenant_id: UUID
    server_id: UUID | None
    session_id: UUID | None
    request: str
    summary: str
    status: RemediationStatus
    rollback_steps: list | None
    reviewer_comment: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    commands: list[RemediationCommandRead]
    origin_type: str | None = None
    origin_ref: str | None = None
    campaign_id: UUID | None = None

    model_config = {"from_attributes": True}


class RemediationRequest(BaseModel):
    server_id: UUID
    request: str
    session_id: UUID | None = None


class RemediationContextRequest(BaseModel):
    """Remediação sem server — gerada por GLPI, SOAR, alertas, etc."""
    request: str
    origin_type: str | None = None
    origin_ref: str | None = None
    device_name: str | None = None
    campaign_id: UUID | None = None


class CommandReview(BaseModel):
    comment: str | None = None


class ReviewerComment(BaseModel):
    comment: str | None = None


class CommandEdit(BaseModel):
    command: str
    description: str | None = None


class CorrectiveRequest(BaseModel):
    observation: str


# ── Templates ─────────────────────────────────────────────────────────────────

class TemplateCreate(BaseModel):
    name: str
    description: str | None = None
    vendor: str | None = None
    category: str | None = None
    commands: list[dict] = []


class TemplateRead(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    vendor: str | None
    category: str | None
    commands: list
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Campaigns ─────────────────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    name: str
    template_id: UUID | None = None
    origin_type: str | None = None
    origin_ref: str | None = None


class CampaignRead(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    template_id: UUID | None
    origin_type: str | None
    origin_ref: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
