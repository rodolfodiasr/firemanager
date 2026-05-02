import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ServerOpStatus(str, enum.Enum):
    pending_review = "pending_review"
    executing      = "executing"
    completed      = "completed"
    failed         = "failed"
    rejected       = "rejected"


class ServerOperation(Base):
    __tablename__ = "server_operations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    server_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("servers.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    commands: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ServerOpStatus] = mapped_column(
        Enum(ServerOpStatus, native_enum=False),
        nullable=False, default=ServerOpStatus.pending_review, index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    # Requester info (denormalised for display without joins)
    requester_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    requester_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Server info (denormalised)
    server_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    server_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )
