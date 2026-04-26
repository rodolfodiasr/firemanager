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


# ── Audit review / policy schemas ──────────────────────────────────────────────

class ReviewRequest(BaseModel):
    approved: bool
    comment: str = ""


class AuditPolicyRead(BaseModel):
    id: UUID
    scope_type: str
    scope_id: str
    intent: str
    requires_approval: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class AuditPolicyUpsert(BaseModel):
    scope_type: str   # "role" | "user"
    scope_id: str     # role name or user UUID
    intent: str
    requires_approval: bool


class AuditOperationRead(BaseModel):
    """Operation enriched with requester and device info for the audit page."""
    id: UUID
    natural_language_input: str
    intent: str | None
    action_plan: dict | None
    status: str
    error_message: str | None
    review_comment: str | None
    reviewed_at: datetime | None
    executed_direct: bool
    created_at: datetime
    updated_at: datetime
    # Enriched fields
    requester_name: str | None = None
    requester_email: str | None = None
    device_name: str | None = None
    device_vendor: str | None = None
    reviewer_name: str | None = None


class UserForPolicyRead(BaseModel):
    id: UUID
    name: str
    email: str
    role: str

    model_config = {"from_attributes": True}

