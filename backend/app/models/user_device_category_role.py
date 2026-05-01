from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base
from app.models.device import DeviceCategory
from app.models.user_tenant_role import TenantRole


class UserDeviceCategoryRole(Base):
    """Per-category role override for a user within a tenant.

    Priority during resolution: category role > tenant-wide role.
    A missing entry means the user falls back to their tenant-wide role.
    """
    __tablename__ = "user_device_category_roles"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, primary_key=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, primary_key=True, index=True,
    )
    category: Mapped[DeviceCategory] = mapped_column(
        Enum(DeviceCategory, native_enum=False), nullable=False, primary_key=True,
    )
    role: Mapped[TenantRole] = mapped_column(
        Enum(TenantRole, native_enum=False), nullable=False,
    )
    granted_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
