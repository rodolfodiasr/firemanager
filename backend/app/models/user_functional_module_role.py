import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base
from app.models.user_tenant_role import TenantRole


class FunctionalModule(str, enum.Enum):
    compliance      = "compliance"
    remediation     = "remediation"
    server_analysis = "server_analysis"
    bulk_jobs       = "bulk_jobs"


class UserFunctionalModuleRole(Base):
    __tablename__ = "user_functional_module_roles"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, primary_key=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, primary_key=True, index=True,
    )
    module: Mapped[FunctionalModule] = mapped_column(
        Enum(FunctionalModule, native_enum=False), nullable=False, primary_key=True,
    )
    role: Mapped[TenantRole] = mapped_column(
        Enum(TenantRole, native_enum=False), nullable=False,
    )
    granted_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
