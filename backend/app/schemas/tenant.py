from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.user_tenant_role import TenantRole


class TenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    is_active: bool | None = None


class TenantRead(BaseModel):
    id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantMemberRead(BaseModel):
    user_id: UUID
    tenant_id: UUID
    role: TenantRole
    email: str
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class MemberInvite(BaseModel):
    user_id: UUID
    role: TenantRole = TenantRole.analyst


class MemberRoleUpdate(BaseModel):
    role: TenantRole
