import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class DocumentType(str, enum.Enum):
    audit_report_pdf = "audit_report_pdf"
    manual_guide_docx = "manual_guide_docx"
    compliance_report_pdf = "compliance_report_pdf"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    operation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("operations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    doc_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType, native_enum=False), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
