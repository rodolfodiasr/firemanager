import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import _hash_password, get_current_user, oauth2_scheme, resolve_tenant_access
from app.database import get_db
from app.models.invite_token import InviteToken
from app.models.tenant import Tenant
from app.models.user import User, UserRole, AuthSource
from app.models.user_tenant_role import TenantRole, UserTenantRole
from app.utils.email import send_invite_email

router = APIRouter()

INVITE_TTL = timedelta(hours=24)


class InviteCreate(BaseModel):
    email: EmailStr
    tenant_id: UUID
    role: TenantRole = TenantRole.analyst_n2
    auth_source: str = "local"
    frontend_url: str = "http://localhost:5173"


class InviteInfo(BaseModel):
    token: str
    email: str
    tenant_id: str
    tenant_name: str
    role: str
    auth_source: str = "local"
    expires_at: str


class AcceptInvite(BaseModel):
    name: str | None = None
    password: str | None = None


class AcceptResponse(BaseModel):
    message: str


@router.post("", response_model=InviteInfo, status_code=201)
async def create_invite(
    data: InviteCreate,
    token: Annotated[str, Depends(oauth2_scheme)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InviteInfo:
    # Require admin access to the tenant
    ctx = await resolve_tenant_access(token, data.tenant_id, db)

    # Check if invite already pending for this email+tenant
    existing_r = await db.execute(
        select(InviteToken).where(
            InviteToken.email == data.email,
            InviteToken.tenant_id == data.tenant_id,
            InviteToken.used_at.is_(None),
            InviteToken.expires_at > datetime.now(timezone.utc),
        )
    )
    if existing_r.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Já existe um convite pendente para este email neste tenant")

    # Validate auth_source value
    valid_sources = ("local", "ldap", "oidc", "break_glass")
    auth_source = data.auth_source if data.auth_source in valid_sources else "local"

    raw_token = secrets.token_urlsafe(32)
    invite = InviteToken(
        token=raw_token,
        email=str(data.email),
        tenant_id=data.tenant_id,
        role=data.role.value,
        auth_source=auth_source,
        invited_by=current_user.id,
        expires_at=datetime.now(timezone.utc) + INVITE_TTL,
    )
    db.add(invite)
    await db.flush()

    send_invite_email(
        to_email=str(data.email),
        tenant_name=ctx.tenant.name,
        token=raw_token,
        inviter_name=current_user.name,
        frontend_url=data.frontend_url,
    )

    return InviteInfo(
        token=raw_token,
        email=str(data.email),
        tenant_id=str(data.tenant_id),
        tenant_name=ctx.tenant.name,
        role=data.role.value,
        auth_source=auth_source,
        expires_at=invite.expires_at.isoformat(),
    )


@router.get("/{token}", response_model=InviteInfo)
async def get_invite(token: str, db: Annotated[AsyncSession, Depends(get_db)]) -> InviteInfo:
    invite = await _get_valid_invite(token, db)
    tenant_r = await db.execute(select(Tenant).where(Tenant.id == invite.tenant_id))
    tenant = tenant_r.scalar_one_or_none()
    return InviteInfo(
        token=invite.token,
        email=invite.email,
        tenant_id=str(invite.tenant_id),
        tenant_name=tenant.name if tenant else "",
        role=invite.role,
        auth_source=getattr(invite, "auth_source", "local"),
        expires_at=invite.expires_at.isoformat(),
    )


@router.post("/{token}/accept", response_model=AcceptResponse)
async def accept_invite(
    token: str,
    data: AcceptInvite,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AcceptResponse:
    invite = await _get_valid_invite(token, db)

    # Upsert user
    user_r = await db.execute(select(User).where(User.email == invite.email))
    user = user_r.scalar_one_or_none()

    invite_auth_source = getattr(invite, "auth_source", "local")
    needs_password = invite_auth_source in ("local", "break_glass")

    if not user:
        if not data.name:
            raise HTTPException(status_code=422, detail="Nome obrigatório para novos usuários")
        if needs_password and not data.password:
            raise HTTPException(status_code=422, detail="Senha obrigatória para este método de autenticação")
        user = User(
            email=invite.email,
            name=data.name,
            hashed_password=_hash_password(data.password) if needs_password and data.password else None,
            role=UserRole.operator,
            auth_source=invite_auth_source,
            break_glass=(invite_auth_source == "break_glass"),
        )
        db.add(user)
        await db.flush()
    # Existing user — no changes to their profile or auth_source

    # Add to tenant (idempotent)
    utr_r = await db.execute(
        select(UserTenantRole).where(
            UserTenantRole.user_id == user.id,
            UserTenantRole.tenant_id == invite.tenant_id,
        )
    )
    if not utr_r.scalar_one_or_none():
        db.add(UserTenantRole(
            user_id=user.id,
            tenant_id=invite.tenant_id,
            role=TenantRole(invite.role),
        ))

    invite.used_at = datetime.now(timezone.utc)
    await db.flush()

    return AcceptResponse(message="Convite aceito com sucesso. Você já pode fazer login.")


async def _get_valid_invite(token: str, db: AsyncSession) -> InviteToken:
    r = await db.execute(select(InviteToken).where(InviteToken.token == token))
    invite = r.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Convite não encontrado")
    if invite.used_at:
        raise HTTPException(status_code=410, detail="Convite já utilizado")
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Convite expirado")
    return invite
