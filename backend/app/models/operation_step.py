import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, Integer, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class StepStatus(str, enum.Enum):
    pending = "pending"
    executing = "executing"
    completed = "completed"
    failed = "failed"


class OperationStep(Base):
    __tablename__ = "operation_steps"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    operation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("operations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[StepStatus] = mapped_column(
        Enum(StepStatus, native_enum=False), nullable=False, default=StepStatus.pending
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    operation: Mapped["Operation"] = relationship("Operation", back_populates="steps")  # type: ignore[name-defined]


from app.models.operation import Operation  # noqa: E402, F401
