"""Functional module role management.

Admins assign per-module role overrides to tenant members.
Modules: compliance, remediation, server_analysis, bulk_jobs.
Resolution: module role > tenant-wide role (fallback).
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, require_tenant_admin
from app.database import get_db
from app.models.user import User
from app.models.user_functional_module_role import FunctionalModule, UserFunctionalModuleRole
from app.models.user_tenant_role import UserTenantRole
from app.schemas.user_device_category_role import CategoryRoleRead
from app.schemas.user_functional_module_role import ModuleRoleRead, ModuleRoleUpsert, UserModuleRolesRead
from app.services import permission_service

router = APIRouter()


@router.get("/users", response_model=list[UserModuleRolesRead])
async def list_user_module_profiles(
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[UserModuleRolesRead]:
    members_result = await db.execute(
        select(User, UserTenantRole.role)
        .join(UserTenantRole, UserTenantRole.user_id == User.id)
        .where(UserTenantRole.tenant_id == ctx.tenant.id)
        .order_by(User.name)
    )
    rows = members_result.all()

    cat_roles = await permission_service.get_all_tenant_category_roles(db, ctx.tenant.id)
    mod_roles = await permission_service.get_all_tenant_module_roles(db, ctx.tenant.id)

    cat_by_user: dict[UUID, list] = {}
    for cr in cat_roles:
        cat_by_user.setdefault(cr.user_id, []).append(cr)

    mod_by_user: dict[UUID, list[UserFunctionalModuleRole]] = {}
    for mr in mod_roles:
        mod_by_user.setdefault(mr.user_id, []).append(mr)

    return [
        UserModuleRolesRead(
            user_id=user.id,
            user_name=user.name,
            user_email=user.email,
            tenant_role=tenant_role,
            category_roles=[CategoryRoleRead.model_validate(cr) for cr in cat_by_user.get(user.id, [])],
            module_roles=[ModuleRoleRead.model_validate(mr) for mr in mod_by_user.get(user.id, [])],
        )
        for user, tenant_role in rows
    ]


@router.get("/users/{user_id}", response_model=UserModuleRolesRead)
async def get_user_module_profile(
    user_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> UserModuleRolesRead:
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
    mod_roles = await permission_service.get_user_module_roles(db, ctx.tenant.id, user_id)

    return UserModuleRolesRead(
        user_id=user.id,
        user_name=user.name,
        user_email=user.email,
        tenant_role=tenant_role,
        category_roles=[CategoryRoleRead.model_validate(cr) for cr in cat_roles],
        module_roles=[ModuleRoleRead.model_validate(mr) for mr in mod_roles],
    )


@router.put("", response_model=ModuleRoleRead, status_code=200)
async def upsert_module_role(
    body: ModuleRoleUpsert,
    ctx:  Annotated[TenantContext, Depends(require_tenant_admin)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> ModuleRoleRead:
    member_result = await db.execute(
        select(UserTenantRole).where(
            UserTenantRole.user_id == body.user_id,
            UserTenantRole.tenant_id == ctx.tenant.id,
        )
    )
    if not member_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Usuário não é membro deste tenant")

    entry = await permission_service.upsert_module_role(
        db=db,
        tenant_id=ctx.tenant.id,
        user_id=body.user_id,
        module=body.module,
        role=body.role,
        granted_by=ctx.user.id,
    )
    await db.commit()
    return ModuleRoleRead.model_validate(entry)


@router.delete("/users/{user_id}/modules/{module}", status_code=204)
async def delete_module_role(
    user_id: UUID,
    module: FunctionalModule,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    deleted = await permission_service.delete_module_role(
        db=db,
        tenant_id=ctx.tenant.id,
        user_id=user_id,
        module=module,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Papel de módulo não encontrado")
    await db.commit()


@router.put("/users/{user_id}", response_model=UserModuleRolesRead)
async def replace_user_module_roles(
    user_id: UUID,
    body: list[ModuleRoleUpsert],
    ctx:  Annotated[TenantContext, Depends(require_tenant_admin)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> UserModuleRolesRead:
    """Replace ALL module roles for a user. Modules not in the list revert to tenant-wide."""
    member_result = await db.execute(
        select(User, UserTenantRole.role)
        .join(UserTenantRole, UserTenantRole.user_id == User.id)
        .where(UserTenantRole.user_id == user_id, UserTenantRole.tenant_id == ctx.tenant.id)
    )
    row = member_result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Usuário não é membro deste tenant")

    user, tenant_role = row

    existing = await permission_service.get_user_module_roles(db, ctx.tenant.id, user_id)
    for mr in existing:
        await db.delete(mr)
    await db.flush()

    new_roles: list[UserFunctionalModuleRole] = []
    for item in body:
        if item.user_id != user_id:
            continue
        entry = await permission_service.upsert_module_role(
            db=db,
            tenant_id=ctx.tenant.id,
            user_id=user_id,
            module=item.module,
            role=item.role,
            granted_by=ctx.user.id,
        )
        new_roles.append(entry)

    cat_roles = await permission_service.get_user_category_roles(db, ctx.tenant.id, user_id)
    await db.commit()

    return UserModuleRolesRead(
        user_id=user.id,
        user_name=user.name,
        user_email=user.email,
        tenant_role=tenant_role,
        category_roles=[CategoryRoleRead.model_validate(cr) for cr in cat_roles],
        module_roles=[ModuleRoleRead.model_validate(mr) for mr in new_roles],
    )
