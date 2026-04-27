import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class TenantRole(str, enum.Enum):
    admin    = "admin"
    analyst  = "analyst"
    readonly = "readonly"


class UserTenantRole(Base):
    __tablename__ = "user_tenant_roles"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, primary_key=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, primary_key=True, index=True,
    )
    role: Mapped[TenantRole] = mapped_column(
        Enum(TenantRole, native_enum=False), nullable=False, default=TenantRole.analyst
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
