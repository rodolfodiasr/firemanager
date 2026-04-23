from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.operation import OperationStatus


class OperationCreate(BaseModel):
    device_id: UUID
    natural_language_input: str


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class OperationRead(BaseModel):
    id: UUID
    device_id: UUID
    natural_language_input: str
    intent: str | None
    action_plan: dict | None
    status: OperationStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OperationApprove(BaseModel):
    approved: bool
    comment: str | None = None
