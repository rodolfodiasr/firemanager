from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    sources_used: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    server_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    integration_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    host_filter: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True
    )
