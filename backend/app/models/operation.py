import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class OperationStatus(str, enum.Enum):
    pending = "pending"
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    executing = "executing"
    completed = "completed"
    failed = "failed"
    rejected = "rejected"


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
