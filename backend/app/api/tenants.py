import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import (
    oauth2_scheme,
    require_super_admin,
    resolve_tenant_access,
    _hash_password,
)
from app.database import get_db
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.user_tenant_role import TenantRole, UserTenantRole
from app.schemas.tenant import (
    MemberInvite,
    MemberInviteByEmail,
    MemberInviteResponse,
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
    token: Annotated[str, Depends(oauth2_scheme)],
    db:    Annotated[AsyncSession, Depends(get_db)],
) -> list[TenantMemberRead]:
    await resolve_tenant_access(token, tenant_id, db)
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
    token: Annotated[str, Depends(oauth2_scheme)],
    db:    Annotated[AsyncSession, Depends(get_db)],
) -> TenantMemberRead:
    await resolve_tenant_access(token, tenant_id, db)

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


@router.post("/{tenant_id}/members/by-email", response_model=MemberInviteResponse, status_code=201)
async def invite_member_by_email(
    tenant_id: UUID,
    data: MemberInviteByEmail,
    token: Annotated[str, Depends(oauth2_scheme)],
    db:    Annotated[AsyncSession, Depends(get_db)],
) -> MemberInviteResponse:
    await resolve_tenant_access(token, tenant_id, db)

    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    temp_password: str | None = None

    if not user:
        temp_password = secrets.token_urlsafe(10)
        user = User(
            email=data.email,
            name=data.name or data.email.split("@")[0],
            hashed_password=_hash_password(temp_password),
            role=UserRole.operator,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)

    existing_r = await db.execute(
        select(UserTenantRole).where(
            UserTenantRole.user_id == user.id,
            UserTenantRole.tenant_id == tenant_id,
        )
    )
    utr = existing_r.scalar_one_or_none()
    if utr:
        # User already a member — return existing record (no password shown)
        member = TenantMemberRead(
            user_id=utr.user_id,
            tenant_id=utr.tenant_id,
            role=utr.role,
            email=user.email,
            name=user.name,
            is_active=user.is_active,
        )
        return MemberInviteResponse(member=member, temp_password=None)

    utr = UserTenantRole(user_id=user.id, tenant_id=tenant_id, role=data.role)
    db.add(utr)
    await db.flush()

    member = TenantMemberRead(
        user_id=utr.user_id,
        tenant_id=utr.tenant_id,
        role=utr.role,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
    )
    return MemberInviteResponse(member=member, temp_password=temp_password)


@router.patch("/{tenant_id}/members/{user_id}", response_model=TenantMemberRead)
async def update_member_role(
    tenant_id: UUID,
    user_id:   UUID,
    data: MemberRoleUpdate,
    token: Annotated[str, Depends(oauth2_scheme)],
    db:    Annotated[AsyncSession, Depends(get_db)],
) -> TenantMemberRead:
    await resolve_tenant_access(token, tenant_id, db)

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
    token: Annotated[str, Depends(oauth2_scheme)],
    db:    Annotated[AsyncSession, Depends(get_db)],
) -> None:
    ctx = await resolve_tenant_access(token, tenant_id, db)
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
