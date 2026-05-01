"""Category-level role management.

Admins assign per-category role overrides to tenant members.
Resolution: category role > tenant-wide role (fallback).
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, require_tenant_admin
from app.database import get_db
from app.models.device import DeviceCategory
from app.models.user import User
from app.models.user_device_category_role import UserDeviceCategoryRole
from app.models.user_tenant_role import TenantRole, UserTenantRole
from app.schemas.user_device_category_role import (
    CategoryRoleRead,
    CategoryRoleUpsert,
    UserCategoryRolesRead,
)
from app.services import permission_service

router = APIRouter()


# ── List all users with their role profiles ────────────────────────────────────

@router.get("/users", response_model=list[UserCategoryRolesRead])
async def list_user_role_profiles(
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[UserCategoryRolesRead]:
    """Return every tenant member with their tenant-wide role and all category overrides."""
    members_result = await db.execute(
        select(User, UserTenantRole.role)
        .join(UserTenantRole, UserTenantRole.user_id == User.id)
        .where(UserTenantRole.tenant_id == ctx.tenant.id)
        .order_by(User.name)
    )
    rows = members_result.all()

    cat_roles = await permission_service.get_all_tenant_category_roles(db, ctx.tenant.id)
    cat_by_user: dict[UUID, list[UserDeviceCategoryRole]] = {}
    for cr in cat_roles:
        cat_by_user.setdefault(cr.user_id, []).append(cr)

    return [
        UserCategoryRolesRead(
            user_id=user.id,
            user_name=user.name,
            user_email=user.email,
            tenant_role=tenant_role,
            category_roles=[
                CategoryRoleRead.model_validate(cr)
                for cr in cat_by_user.get(user.id, [])
            ],
        )
        for user, tenant_role in rows
    ]


# ── Get role profile for a single user ────────────────────────────────────────

@router.get("/users/{user_id}", response_model=UserCategoryRolesRead)
async def get_user_role_profile(
    user_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> UserCategoryRolesRead:
    member_result = await db.execute(
        select(User, UserTenantRole.role)
        .join(UserTenantRole, UserTenantRole.user_id == User.id)
        .where(UserTenantRole.user_id == user_id, UserTenantRole.tenant_id == ctx.tenant.id)
    )
    row = member_result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Usuário não encontrado neste tenant")

    user, tenant_role = row
    cat_roles = await permission_service.get_user_category_roles(db, ctx.tenant.id, user_id)

    return UserCategoryRolesRead(
        user_id=user.id,
        user_name=user.name,
        user_email=user.email,
        tenant_role=tenant_role,
        category_roles=[CategoryRoleRead.model_validate(cr) for cr in cat_roles],
    )


# ── Upsert a category role ─────────────────────────────────────────────────────

@router.put("", response_model=CategoryRoleRead, status_code=200)
async def upsert_category_role(
    body: CategoryRoleUpsert,
    ctx:  Annotated[TenantContext, Depends(require_tenant_admin)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> CategoryRoleRead:
    """Create or update a per-category role for a user in this tenant."""
    member_result = await db.execute(
        select(UserTenantRole).where(
            UserTenantRole.user_id == body.user_id,
            UserTenantRole.tenant_id == ctx.tenant.id,
        )
    )
    if not member_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Usuário não é membro deste tenant")

    entry = await permission_service.upsert_category_role(
        db=db,
        tenant_id=ctx.tenant.id,
        user_id=body.user_id,
        category=body.category,
        role=body.role,
        granted_by=ctx.user.id,
    )
    await db.commit()
    return CategoryRoleRead.model_validate(entry)


# ── Delete a category role (user reverts to tenant-wide role) ─────────────────

@router.delete("/users/{user_id}/categories/{category}", status_code=204)
async def delete_category_role(
    user_id:  UUID,
    category: DeviceCategory,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Remove a category override — user falls back to their tenant-wide role."""
    deleted = await permission_service.delete_category_role(
        db=db,
        tenant_id=ctx.tenant.id,
        user_id=user_id,
        category=category,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Papel de categoria não encontrado")
    await db.commit()


# ── Bulk replace: set all category roles for a user at once ───────────────────

@router.put("/users/{user_id}", response_model=UserCategoryRolesRead)
async def replace_user_category_roles(
    user_id: UUID,
    body: list[CategoryRoleUpsert],
    ctx:  Annotated[TenantContext, Depends(require_tenant_admin)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> UserCategoryRolesRead:
    """Replace ALL category roles for a user. Categories not in the list revert to tenant-wide."""
    member_result = await db.execute(
        select(User, UserTenantRole.role)
        .join(UserTenantRole, UserTenantRole.user_id == User.id)
        .where(UserTenantRole.user_id == user_id, UserTenantRole.tenant_id == ctx.tenant.id)
    )
    row = member_result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Usuário não é membro deste tenant")

    user, tenant_role = row

    # Delete all existing category roles for this user in this tenant
    existing = await permission_service.get_user_category_roles(db, ctx.tenant.id, user_id)
    for cr in existing:
        await db.delete(cr)
    await db.flush()

    # Insert the new set
    new_roles: list[UserDeviceCategoryRole] = []
    for item in body:
        if item.user_id != user_id:
            continue
        entry = await permission_service.upsert_category_role(
            db=db,
            tenant_id=ctx.tenant.id,
            user_id=user_id,
            category=item.category,
            role=item.role,
            granted_by=ctx.user.id,
        )
        new_roles.append(entry)

    await db.commit()

    return UserCategoryRolesRead(
        user_id=user.id,
        user_name=user.name,
        user_email=user.email,
        tenant_role=tenant_role,
        category_roles=[CategoryRoleRead.model_validate(cr) for cr in new_roles],
    )
