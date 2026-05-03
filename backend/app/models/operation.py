import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class OperationStatus(str, enum.Enum):
    pending = "pending"
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    executing = "executing"
    pending_review = "pending_review"  # waiting for N2 approval
    completed = "completed"
    failed = "failed"
    rejected = "rejected"


class OperationRisk(str, enum.Enum):
    low      = "low"       # read-only — no approval gate
    medium   = "medium"    # create/edit — standard single approval
    high     = "high"      # delete — standard approval + notification
    critical = "critical"  # destructive bulk / guardrail-flagged — multi-sig required


# Intents classified as critical always require 2 approvals (direct_ssh + guardrail-blocked)
_CRITICAL_INTENTS = frozenset({"direct_ssh"})

# Intents classified as high risk (single-approval but flagged)
_HIGH_INTENTS = frozenset({
    "delete_rule", "delete_nat_policy", "delete_route_policy", "delete_vlan",
})

# Read-only intents — no approval needed
_LOW_INTENTS = frozenset({
    "list_rules", "list_nat_policies", "list_route_policies", "get_security_status",
    "health_check", "get_snapshot", "list_vlans", "list_ports", "get_info",
})


def classify_risk(intent: str | None) -> tuple[OperationRisk, int]:
    """Return (risk_level, required_approvals) for a given intent string."""
    if not intent:
        return OperationRisk.medium, 1
    if intent in _CRITICAL_INTENTS:
        return OperationRisk.critical, 2
    if intent in _HIGH_INTENTS:
        return OperationRisk.high, 1
    if intent in _LOW_INTENTS:
        return OperationRisk.low, 1
    return OperationRisk.medium, 1


class Operation(Base):
    __tablename__ = "operations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    device_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("devices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    natural_language_input: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[OperationStatus] = mapped_column(
        Enum(OperationStatus, native_enum=False), nullable=False, default=OperationStatus.pending, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Audit review fields
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    executed_direct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tutorial: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Multi-sig approval fields (P6)
    risk_level: Mapped[OperationRisk] = mapped_column(
        Enum(OperationRisk, native_enum=False), nullable=False, default=OperationRisk.medium
    )
    required_approvals: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    co_approvals: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    bulk_job_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("bulk_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parent_operation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("operations.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    steps: Mapped[list["OperationStep"]] = relationship(  # type: ignore[name-defined]
        "OperationStep", back_populates="operation", lazy="select"
    )


# Avoid circular import — OperationStep is defined in operation_step.py
from app.models.operation_step import OperationStep  # noqa: E402, F401
