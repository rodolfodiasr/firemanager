import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Enum, Float, Text, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class FrameworkEnum(str, enum.Enum):
    cis_benchmark = "cis_benchmark"
    nist_csf      = "nist_csf"
    iso_27001     = "iso_27001"
    eternity      = "eternity"   # Eternity Trust Score — índice composto


class TrustScore(Base):
    """Snapshot histórico de score de compliance por framework e tenant."""

    __tablename__ = "trust_scores"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    framework: Mapped[FrameworkEnum] = mapped_column(
        Enum(FrameworkEnum, native_enum=False), nullable=False, index=True,
    )
    score_pct: Mapped[float] = mapped_column(Float, nullable=False)
    breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    narrative: Mapped[str] = mapped_column(Text, nullable=False, default="")
    computed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True,
    )
