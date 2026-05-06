import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum, Float, Integer, String, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class GlpiAnalysisStatus(str, enum.Enum):
    pending         = "pending"
    pending_manual  = "pending_manual"   # captured, awaiting user-triggered analysis
    analyzing       = "analyzing"
    completed       = "completed"
    failed          = "failed"


class GlpiTicketAnalysis(Base):
    __tablename__ = "glpi_ticket_analyses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "glpi_ticket_id", name="uq_glpi_analyses_tenant_ticket"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    glpi_integration_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    glpi_ticket_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    glpi_itemtype: Mapped[str] = mapped_column(String(50), nullable=False, default="Ticket", index=True)
    glpi_ticket_title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    glpi_ticket_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[GlpiAnalysisStatus] = mapped_column(
        Enum(GlpiAnalysisStatus, native_enum=False),
        nullable=False,
        default=GlpiAnalysisStatus.pending,
        index=True,
    )

    # AI analysis result fields
    diagnostico: Mapped[str | None] = mapped_column(Text, nullable=True)
    acoes_imediatas: Mapped[str | None] = mapped_column(Text, nullable=True)
    plano_remediacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    causa_raiz: Mapped[str | None] = mapped_column(Text, nullable=True)
    prevencao: Mapped[str | None] = mapped_column(Text, nullable=True)
    confianca: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_security_incident: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Recurrence detection
    is_recurrent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    recurrence_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    related_ticket_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    glpi_followup_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
