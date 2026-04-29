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
    server_id: UUID
    session_id: UUID | None
    request: str
    summary: str
    status: RemediationStatus
    reviewer_comment: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    commands: list[RemediationCommandRead]

    model_config = {"from_attributes": True}


class RemediationRequest(BaseModel):
    server_id: UUID
    request: str
    session_id: UUID | None = None


class CommandReview(BaseModel):
    comment: str | None = None


class ReviewerComment(BaseModel):
    comment: str | None = None


class CommandEdit(BaseModel):
    command: str
    description: str | None = None


class CorrectiveRequest(BaseModel):
    observation: str
