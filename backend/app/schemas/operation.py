from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.operation import OperationStatus


class AttachmentSchema(BaseModel):
    type: str  # "image" | "text"
    data: str  # base64 for images, raw text for text files
    filename: str
    mime_type: str = "application/octet-stream"


class OperationCreate(BaseModel):
    device_id: UUID
    natural_language_input: str
    parent_operation_id: UUID | None = None
    use_bookstack_context: bool = True
    attachment: AttachmentSchema | None = None


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    attachment: AttachmentSchema | None = None


class OperationRead(BaseModel):
    id: UUID
    device_id: UUID
    natural_language_input: str
    intent: str | None
    action_plan: dict | None
    status: OperationStatus
    error_message: str | None
    review_comment: str | None = None
    reviewer_id: UUID | None = None
    reviewed_at: datetime | None = None
    executed_direct: bool = False
    bulk_job_id: UUID | None = None
    parent_operation_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    # Clarification loop (Fase 40-A)
    clarification_questions: list[dict] | None = None
    clarification_answers: list[dict] | None = None
    confidence_score: float | None = None
    # Populated when fetched as part of BulkJobDetail (JOIN with devices)
    device_name: str | None = None
    device_category: str | None = None

    model_config = {"from_attributes": True}


class OperationApprove(BaseModel):
    approved: bool
    comment: str | None = None
