from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.device import DeviceCategory
from app.models.user_tenant_role import TenantRole


class CategoryRoleRead(BaseModel):
    user_id: UUID
    tenant_id: UUID
    category: DeviceCategory
    role: TenantRole
    granted_by: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CategoryRoleUpsert(BaseModel):
    user_id: UUID
    category: DeviceCategory
    role: TenantRole


class UserCategoryRolesRead(BaseModel):
    """Full role profile for a user: tenant-wide role + all category overrides."""
    user_id: UUID
    user_name: str
    user_email: str
    tenant_role: TenantRole
    category_roles: list[CategoryRoleRead]

    model_config = {"from_attributes": True}
