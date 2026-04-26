from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, String, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AuditPolicy(Base):
    """Stores per-role or per-user audit policy overrides.

    scope_type = "role"  → scope_id = role name ("operator", "viewer")
    scope_type = "user"  → scope_id = user UUID (str)

    Lookup priority: user > role > system default.
    """

    __tablename__ = "audit_policy"
    __table_args__ = (UniqueConstraint("scope_type", "scope_id", "intent", name="uq_audit_policy"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "role" | "user"
    scope_id: Mapped[str] = mapped_column(String(255), nullable=False)
    intent: Mapped[str] = mapped_column(String(100), nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
