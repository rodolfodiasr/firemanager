from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, require_super_admin, require_tenant_admin
from app.database import get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.user_tenant_role import UserTenantRole
from app.schemas.tenant import (
    MemberInvite,
    MemberRoleUpdate,
    TenantCreate,
    TenantMemberRead,
    TenantRead,
    TenantUpdate,
)

router = APIRouter()


# ── Super-admin: tenant CRUD ──────────────────────────────────────────────────

@router.get("", response_model=list[TenantRead])
async def list_tenants(
    _: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TenantRead]:
    result = await db.execute(select(Tenant).order_by(Tenant.name))
    return list(result.scalars().all())


@router.post("", response_model=TenantRead, status_code=201)
async def create_tenant(
    data: TenantCreate,
    _:    Annotated[User, Depends(require_super_admin)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> TenantRead:
    existing = await db.execute(select(Tenant).where(Tenant.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Slug já em uso")
    tenant = Tenant(name=data.name, slug=data.slug)
    db.add(tenant)
    await db.flush()
    await db.refresh(tenant)
    return tenant


@router.patch("/{tenant_id}", response_model=TenantRead)
async def update_tenant(
    tenant_id: UUID,
    data: TenantUpdate,
    _:    Annotated[User, Depends(require_super_admin)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> TenantRead:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    if data.name is not None:
        tenant.name = data.name
    if data.is_active is not None:
        tenant.is_active = data.is_active
    await db.flush()
    await db.refresh(tenant)
    return tenant


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(
    tenant_id: UUID,
    _:  Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    if tenant.slug == "default":
        raise HTTPException(status_code=400, detail="O tenant padrão não pode ser removido")
    tenant.is_active = False
    await db.flush()


# ── Members (tenant admin or super admin) ────────────────────────────────────

@router.get("/{tenant_id}/members", response_model=list[TenantMemberRead])
async def list_members(
    tenant_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[TenantMemberRead]:
    if ctx.tenant.id != tenant_id:
        raise HTTPException(status_code=403, detail="Sem acesso a este tenant")
    result = await db.execute(
        select(UserTenantRole, User)
        .join(User, UserTenantRole.user_id == User.id)
        .where(UserTenantRole.tenant_id == tenant_id)
        .order_by(User.name)
    )
    rows = result.all()
    return [
        TenantMemberRead(
            user_id=utr.user_id,
            tenant_id=utr.tenant_id,
            role=utr.role,
            email=user.email,
            name=user.name,
            is_active=user.is_active,
        )
        for utr, user in rows
    ]


@router.post("/{tenant_id}/members", response_model=TenantMemberRead, status_code=201)
async def invite_member(
    tenant_id: UUID,
    data: MemberInvite,
    ctx:  Annotated[TenantContext, Depends(require_tenant_admin)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> TenantMemberRead:
    if ctx.tenant.id != tenant_id:
        raise HTTPException(status_code=403, detail="Sem acesso a este tenant")

    result = await db.execute(select(User).where(User.id == data.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    existing = await db.execute(
        select(UserTenantRole).where(
            UserTenantRole.user_id == data.user_id,
            UserTenantRole.tenant_id == tenant_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Usuário já é membro deste tenant")

    utr = UserTenantRole(user_id=data.user_id, tenant_id=tenant_id, role=data.role)
    db.add(utr)
    await db.flush()
    return TenantMemberRead(
        user_id=utr.user_id,
        tenant_id=utr.tenant_id,
        role=utr.role,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
    )


@router.patch("/{tenant_id}/members/{user_id}", response_model=TenantMemberRead)
async def update_member_role(
    tenant_id: UUID,
    user_id:   UUID,
    data: MemberRoleUpdate,
    ctx:  Annotated[TenantContext, Depends(require_tenant_admin)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> TenantMemberRead:
    if ctx.tenant.id != tenant_id:
        raise HTTPException(status_code=403, detail="Sem acesso a este tenant")

    result = await db.execute(
        select(UserTenantRole, User)
        .join(User, UserTenantRole.user_id == User.id)
        .where(UserTenantRole.user_id == user_id, UserTenantRole.tenant_id == tenant_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Membro não encontrado")

    utr, user = row
    utr.role = data.role
    await db.flush()
    return TenantMemberRead(
        user_id=utr.user_id,
        tenant_id=utr.tenant_id,
        role=utr.role,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
    )


@router.delete("/{tenant_id}/members/{user_id}", status_code=204)
async def remove_member(
    tenant_id: UUID,
    user_id:   UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    if ctx.tenant.id != tenant_id:
        raise HTTPException(status_code=403, detail="Sem acesso a este tenant")
    if user_id == ctx.user.id:
        raise HTTPException(status_code=400, detail="Não é possível remover a si mesmo")

    result = await db.execute(
        select(UserTenantRole).where(
            UserTenantRole.user_id == user_id,
            UserTenantRole.tenant_id == tenant_id,
        )
    )
    utr = result.scalar_one_or_none()
    if not utr:
        raise HTTPException(status_code=404, detail="Membro não encontrado")
    await db.delete(utr)
    await db.flush()
