import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class RemediationOriginType(str, enum.Enum):
    manual      = "manual"
    compliance  = "compliance"
    glpi_ticket = "glpi_ticket"
    soar_playbook = "soar_playbook"
    cve_firmware  = "cve_firmware"
    alert         = "alert"
    investigation = "investigation"


class RemediationStatus(str, enum.Enum):
    pending_approval = "pending_approval"
    approved         = "approved"
    executing        = "executing"
    completed        = "completed"
    partial          = "partial"   # some commands failed
    rejected         = "rejected"


class RemediationRisk(str, enum.Enum):
    low    = "low"
    medium = "medium"
    high   = "high"


class CommandStatus(str, enum.Enum):
    pending   = "pending"
    approved  = "approved"
    rejected  = "rejected"
    executing = "executing"
    completed = "completed"
    failed    = "failed"
    skipped   = "skipped"   # command was rejected before execution


class RemediationPlan(Base):
    __tablename__ = "remediation_plans"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    server_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("servers.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    origin_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    origin_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    campaign_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("remediation_campaigns.id", ondelete="SET NULL"),
        nullable=True,
    )
    session_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("analysis_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    request: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[RemediationStatus] = mapped_column(
        Enum(RemediationStatus, native_enum=False),
        nullable=False,
        default=RemediationStatus.pending_approval,
        index=True,
    )
    rollback_steps: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    reviewer_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    commands: Mapped[list["RemediationCommand"]] = relationship(
        "RemediationCommand",
        back_populates="plan",
        order_by="RemediationCommand.order",
        cascade="all, delete-orphan",
        lazy="select",
    )


class RemediationCommand(Base):
    __tablename__ = "remediation_commands"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("remediation_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    risk: Mapped[RemediationRisk] = mapped_column(
        Enum(RemediationRisk, native_enum=False), nullable=False, default=RemediationRisk.low
    )
    status: Mapped[CommandStatus] = mapped_column(
        Enum(CommandStatus, native_enum=False),
        nullable=False,
        default=CommandStatus.pending,
    )
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    plan: Mapped["RemediationPlan"] = relationship("RemediationPlan", back_populates="commands")


class RemediationTemplate(Base):
    __tablename__ = "remediation_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    commands: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False,
    )


class RemediationCampaign(Base):
    __tablename__ = "remediation_campaigns"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    template_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("remediation_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    origin_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    origin_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    created_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False,
    )
