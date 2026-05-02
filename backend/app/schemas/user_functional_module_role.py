from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.user_functional_module_role import FunctionalModule
from app.models.user_tenant_role import TenantRole


class ModuleRoleRead(BaseModel):
    user_id: UUID
    tenant_id: UUID
    module: FunctionalModule
    role: TenantRole
    granted_by: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ModuleRoleUpsert(BaseModel):
    user_id: UUID
    module: FunctionalModule
    role: TenantRole


class UserModuleRolesRead(BaseModel):
    """Full role profile for a user: tenant-wide role + all module overrides."""
    user_id: UUID
    user_name: str
    user_email: str
    tenant_role: TenantRole
    category_roles: list  # CategoryRoleRead list (avoid circular import)
    module_roles: list[ModuleRoleRead]

    model_config = {"from_attributes": True}
