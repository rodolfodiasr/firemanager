"""Fase 21 — Identity lifecycle API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import AsyncSessionLocal, get_db
from app.models.identity import (
    ActionStatus, ActionType, IdentityProvider, IdentityUser,
    LifecycleAction, LifecycleTask, ProviderType, SystemType, TaskStatus,
)
from app.utils.crypto import decrypt_credentials, encrypt_credentials

router = APIRouter()

CtxDep = Annotated[TenantContext, Depends(get_tenant_context)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


# ── Schemas ────────────────────────────────────────────────────────────────────

class ProviderCreate(BaseModel):
    name: str
    provider_type: ProviderType
    config: dict


class ProviderRead(BaseModel):
    id: str
    name: str
    provider_type: str
    is_active: bool
    last_sync_at: str | None
    last_sync_count: int | None
    created_at: str

    @classmethod
    def from_orm(cls, p: IdentityProvider) -> "ProviderRead":
        return cls(
            id=str(p.id),
            name=p.name,
            provider_type=p.provider_type,
            is_active=p.is_active,
            last_sync_at=p.last_sync_at.isoformat() if p.last_sync_at else None,
            last_sync_count=p.last_sync_count,
            created_at=p.created_at.isoformat(),
        )


class UserRead(BaseModel):
    id: str
    provider_id: str
    external_id: str
    username: str
    display_name: str | None
    email: str | None
    is_enabled: bool
    department: str | None
    job_title: str | None
    last_sign_in_raw: str | None
    synced_at: str

    @classmethod
    def from_orm(cls, u: IdentityUser) -> "UserRead":
        return cls(
            id=str(u.id),
            provider_id=str(u.provider_id),
            external_id=u.external_id,
            username=u.username,
            display_name=u.display_name,
            email=u.email,
            is_enabled=u.is_enabled,
            department=u.department,
            job_title=u.job_title,
            last_sign_in_raw=u.last_sign_in_raw,
            synced_at=u.synced_at.isoformat(),
        )


class TaskRead(BaseModel):
    id: str
    system_type: str
    system_id: str | None
    system_name: str
    status: str
    result: str | None
    error: str | None
    executed_at: str | None

    @classmethod
    def from_orm(cls, t: LifecycleTask) -> "TaskRead":
        return cls(
            id=str(t.id),
            system_type=t.system_type,
            system_id=t.system_id,
            system_name=t.system_name,
            status=t.status,
            result=t.result,
            error=t.error,
            executed_at=t.executed_at.isoformat() if t.executed_at else None,
        )


class ActionRead(BaseModel):
    id: str
    action_type: str
    target_username: str
    display_name: str | None
    email: str | None
    status: str
    notes: str | None
    created_at: str
    approved_at: str | None
    completed_at: str | None
    tasks: list[TaskRead]

    @classmethod
    def from_orm(cls, a: LifecycleAction) -> "ActionRead":
        return cls(
            id=str(a.id),
            action_type=a.action_type,
            target_username=a.target_username,
            display_name=a.display_name,
            email=a.email,
            status=a.status,
            notes=a.notes,
            created_at=a.created_at.isoformat(),
            approved_at=a.approved_at.isoformat() if a.approved_at else None,
            completed_at=a.completed_at.isoformat() if a.completed_at else None,
            tasks=[TaskRead.from_orm(t) for t in a.tasks],
        )


class ActionCreate(BaseModel):
    target_username: str
    display_name: str | None = None
    email: str | None = None
    notes: str | None = None


class OrphanUser(BaseModel):
    provider_id: str
    provider_name: str
    provider_type: str
    username: str
    display_name: str | None
    email: str | None
    department: str | None
    last_sign_in_raw: str | None


# ── Identity Providers ─────────────────────────────────────────────────────────

@router.get("/providers", response_model=list[ProviderRead])
async def list_providers(db: DbDep, ctx: CtxDep):
    rows = (await db.execute(
        select(IdentityProvider)
        .where(IdentityProvider.tenant_id == ctx.tenant.id)
        .order_by(IdentityProvider.created_at)
    )).scalars().all()
    return [ProviderRead.from_orm(p) for p in rows]


@router.post("/providers", response_model=ProviderRead, status_code=201)
async def create_provider(body: ProviderCreate, db: DbDep, ctx: CtxDep):
    provider = IdentityProvider(
        tenant_id=ctx.tenant.id,
        name=body.name,
        provider_type=body.provider_type,
        encrypted_config=encrypt_credentials(body.config),
    )
    db.add(provider)
    await db.flush()
    await db.refresh(provider)
    return ProviderRead.from_orm(provider)


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(provider_id: UUID, db: DbDep, ctx: CtxDep):
    p = await db.get(IdentityProvider, provider_id)
    if not p or p.tenant_id != ctx.tenant.id:
        raise HTTPException(404)
    await db.delete(p)


@router.post("/providers/{provider_id}/sync", response_model=ProviderRead)
async def sync_provider(provider_id: UUID, db: DbDep, ctx: CtxDep):
    provider = await db.get(IdentityProvider, provider_id)
    if not provider or provider.tenant_id != ctx.tenant.id:
        raise HTTPException(404)

    config = decrypt_credentials(provider.encrypted_config)

    if provider.provider_type == ProviderType.azure_ad:
        from app.services.azure_ad_service import list_users
        raw_users = await list_users(config)
        normalized = [_normalize_azure(u) for u in raw_users]
    else:
        from app.services.google_workspace_service import list_users
        raw_users = await list_users(config)
        normalized = [_normalize_google(u) for u in raw_users]

    await db.execute(delete(IdentityUser).where(IdentityUser.provider_id == provider_id))
    for n in normalized:
        db.add(IdentityUser(tenant_id=ctx.tenant.id, provider_id=provider_id, **n))

    provider.last_sync_at = datetime.now(timezone.utc)
    provider.last_sync_count = len(normalized)
    await db.flush()
    await db.refresh(provider)
    return ProviderRead.from_orm(provider)


def _normalize_azure(u: dict) -> dict:
    sign_in = (u.get("signInActivity") or {}).get("lastSignInDateTime")
    return dict(
        external_id=u["id"],
        username=u.get("userPrincipalName", u["id"]),
        display_name=u.get("displayName"),
        email=u.get("mail"),
        is_enabled=u.get("accountEnabled", True),
        department=u.get("department"),
        job_title=u.get("jobTitle"),
        last_sign_in_raw=sign_in,
    )


def _normalize_google(u: dict) -> dict:
    return dict(
        external_id=u["id"],
        username=u.get("primaryEmail", u["id"]),
        display_name=(u.get("name") or {}).get("fullName"),
        email=u.get("primaryEmail"),
        is_enabled=not u.get("suspended", False),
        department=u.get("orgUnitPath"),
        job_title=None,
        last_sign_in_raw=u.get("lastLoginTime"),
    )


@router.get("/providers/{provider_id}/users", response_model=list[UserRead])
async def list_provider_users(provider_id: UUID, db: DbDep, ctx: CtxDep):
    p = await db.get(IdentityProvider, provider_id)
    if not p or p.tenant_id != ctx.tenant.id:
        raise HTTPException(404)
    rows = (await db.execute(
        select(IdentityUser)
        .where(IdentityUser.provider_id == provider_id)
        .order_by(IdentityUser.display_name)
    )).scalars().all()
    return [UserRead.from_orm(u) for u in rows]


# ── Orphan Accounts ────────────────────────────────────────────────────────────

@router.get("/orphans", response_model=list[OrphanUser])
async def get_orphan_accounts(db: DbDep, ctx: CtxDep):
    rows = (await db.execute(
        select(IdentityUser, IdentityProvider.name, IdentityProvider.provider_type)
        .join(IdentityProvider, IdentityUser.provider_id == IdentityProvider.id)
        .where(
            IdentityUser.tenant_id == ctx.tenant.id,
            IdentityUser.is_enabled.is_(False),
        )
        .order_by(IdentityUser.display_name)
    )).all()
    return [
        OrphanUser(
            provider_id=str(u.provider_id),
            provider_name=pname,
            provider_type=ptype,
            username=u.username,
            display_name=u.display_name,
            email=u.email,
            department=u.department,
            last_sign_in_raw=u.last_sign_in_raw,
        )
        for u, pname, ptype in rows
    ]


# ── Lifecycle Actions ──────────────────────────────────────────────────────────

@router.get("/actions", response_model=list[ActionRead])
async def list_actions(db: DbDep, ctx: CtxDep):
    rows = (await db.execute(
        select(LifecycleAction)
        .where(LifecycleAction.tenant_id == ctx.tenant.id)
        .order_by(LifecycleAction.created_at.desc())
    )).scalars().all()
    return [ActionRead.from_orm(a) for a in rows]


@router.post("/actions", response_model=ActionRead, status_code=201)
async def create_action(body: ActionCreate, background_tasks: BackgroundTasks, db: DbDep, ctx: CtxDep):
    action = LifecycleAction(
        tenant_id=ctx.tenant.id,
        action_type=ActionType.offboard,
        target_username=body.target_username,
        display_name=body.display_name,
        email=body.email,
        status=ActionStatus.pending_discovery,
        requested_by=ctx.user.id,
        notes=body.notes,
    )
    db.add(action)
    await db.flush()
    await db.refresh(action)
    action_id = str(action.id)
    tenant_id = ctx.tenant.id
    background_tasks.add_task(_bg_discover, action_id, tenant_id)
    return ActionRead.from_orm(action)


@router.get("/actions/{action_id}", response_model=ActionRead)
async def get_action(action_id: UUID, db: DbDep, ctx: CtxDep):
    action = await db.get(LifecycleAction, action_id)
    if not action or action.tenant_id != ctx.tenant.id:
        raise HTTPException(404)
    return ActionRead.from_orm(action)


@router.post("/actions/{action_id}/approve")
async def approve_action(action_id: UUID, background_tasks: BackgroundTasks, db: DbDep, ctx: CtxDep):
    action = await db.get(LifecycleAction, action_id)
    if not action or action.tenant_id != ctx.tenant.id:
        raise HTTPException(404)
    if action.status != ActionStatus.pending_approval:
        raise HTTPException(400, "Ação não está aguardando aprovação")
    action.approved_by = ctx.user.id
    action.approved_at = datetime.now(timezone.utc)
    action.status = ActionStatus.running
    await db.flush()
    background_tasks.add_task(_bg_offboard, str(action.id))
    return {"status": "running"}


@router.post("/actions/{action_id}/cancel")
async def cancel_action(action_id: UUID, db: DbDep, ctx: CtxDep):
    action = await db.get(LifecycleAction, action_id)
    if not action or action.tenant_id != ctx.tenant.id:
        raise HTTPException(404)
    if action.status not in (ActionStatus.pending_discovery, ActionStatus.pending_approval):
        raise HTTPException(400, "Não é possível cancelar ação já iniciada")
    action.status = ActionStatus.cancelled
    return {"status": "cancelled"}


# ── HR Webhook ─────────────────────────────────────────────────────────────────

class HRWebhookPayload(BaseModel):
    username: str
    display_name: str | None = None
    email: str | None = None
    notes: str | None = None
    api_key: str


@router.post("/webhook/hr", status_code=201)
async def hr_webhook(body: HRWebhookPayload, background_tasks: BackgroundTasks, db: DbDep):
    from sqlalchemy import text
    from app.models.user import User

    row = (await db.execute(
        text("SELECT id FROM tenants WHERE settings->>'hr_webhook_key' = :key LIMIT 1"),
        {"key": body.api_key},
    )).first()
    if not row:
        raise HTTPException(401, "Chave de webhook inválida")

    tenant_id = row[0]
    admin = (await db.execute(
        select(User).where(User.tenant_id == tenant_id, User.role == "admin").limit(1)
    )).scalar_one_or_none()
    if not admin:
        raise HTTPException(500, "Tenant sem admin configurado")

    action = LifecycleAction(
        tenant_id=tenant_id,
        action_type=ActionType.offboard,
        target_username=body.username,
        display_name=body.display_name,
        email=body.email,
        status=ActionStatus.pending_discovery,
        requested_by=admin.id,
        notes=body.notes or "Offboarding automático via webhook RH",
    )
    db.add(action)
    await db.flush()
    action_id = str(action.id)
    background_tasks.add_task(_bg_discover, action_id, tenant_id)
    return {"action_id": action_id, "status": "pending_discovery"}


# ── Background tasks ───────────────────────────────────────────────────────────

async def _bg_discover(action_id: str, tenant_id) -> None:
    from app.services.lifecycle_service import discover_user_accesses
    async with AsyncSessionLocal() as db:
        action = await db.get(LifecycleAction, UUID(action_id))
        if not action:
            return
        try:
            tasks = await discover_user_accesses(db, tenant_id, action)
            for t in tasks:
                db.add(t)
            action.status = ActionStatus.pending_approval
        except Exception:
            action.status = ActionStatus.failed
        await db.commit()


async def _bg_offboard(action_id: str) -> None:
    from app.services.lifecycle_service import run_offboarding
    async with AsyncSessionLocal() as db:
        action = await db.get(LifecycleAction, UUID(action_id))
        if action:
            await run_offboarding(db, action)
