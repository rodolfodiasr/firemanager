import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Integer, String, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class GlpiIntegration(Base):
    __tablename__ = "glpi_integrations"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_glpi_integrations_tenant"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    glpi_url: Mapped[str] = mapped_column(String(500), nullable=False)
    app_token: Mapped[str] = mapped_column(String(200), nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    encrypted_password: Mapped[str] = mapped_column(Text, nullable=False)

    verify_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Filtering — which tickets to analyse
    min_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    trigger_types: Mapped[list] = mapped_column(JSONB, nullable=False, default=lambda: [1, 2])
    trigger_categories: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    tag_analyzed: Mapped[str] = mapped_column(String(100), nullable=False, default="fm-analyzed")
    poll_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    lookback_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
