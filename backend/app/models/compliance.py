from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Float, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ComplianceReport(Base):
    __tablename__ = "compliance_reports"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    server_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("servers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(8), nullable=False)        # "wazuh" | "ssh"
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    policy_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    policy_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    score_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_checks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    not_applicable: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    controls: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    ai_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ai_recommendations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    framework: Mapped[str] = mapped_column(String(20), nullable=False, default="cis_benchmark", index=True)
    framework_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True
    )
