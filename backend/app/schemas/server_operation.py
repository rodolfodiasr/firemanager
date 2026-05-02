from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.server_operation import ServerOpStatus


class ExecRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    commands: list[str] = Field(..., min_length=1)


class ReviewRequest(BaseModel):
    approved: bool
    comment: str = ""


class ServerOperationRead(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    server_id: UUID
    description: str
    commands: list[str]
    output: str | None
    status: ServerOpStatus
    error_message: str | None
    review_comment: str | None
    reviewer_id: UUID | None
    reviewed_at: datetime | None
    requester_name: str | None
    requester_email: str | None
    server_name: str | None
    server_host: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
