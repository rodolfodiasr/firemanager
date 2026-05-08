"""Fase 22 — Onboarding profiles and external connector API."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import AsyncSessionLocal, get_db
from app.models.identity import LifecycleAction, ActionType, ActionStatus
from app.models.onboarding import ExternalConnector, OnboardingProfile, OnboardingProfileSystem
from app.utils.crypto import decrypt_credentials, encrypt_credentials

router = APIRouter()

CtxDep = Annotated[TenantContext, Depends(get_tenant_context)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


# ── Schemas ────────────────────────────────────────────────────────────────────

class ConnectorCreate(BaseModel):
    name: str
    connector_type: str
    config: dict


class ConnectorRead(BaseModel):
    id: str
    name: str
    connector_type: str
    is_active: bool
    created_at: str

    @classmethod
    def from_orm(cls, c: ExternalConnector) -> "ConnectorRead":
        return cls(
            id=str(c.id),
            name=c.name,
            connector_type=c.connector_type,
            is_active=c.is_active,
            created_at=c.created_at.isoformat(),
        )


class ProfileSystemIn(BaseModel):
    system_type: str
    system_id: str | None = None
    system_name: str
    config: dict = {}


class ProfileCreate(BaseModel):
    name: str
    description: str | None = None
    ad_groups: list[str] = []
    systems: list[ProfileSystemIn] = []


class ProfileRead(BaseModel):
    id: str
    name: str
    description: str | None
    ad_groups: list[str]
    systems: list[dict]
    created_at: str

    @classmethod
    def from_orm(cls, p: OnboardingProfile) -> "ProfileRead":
        return cls(
            id=str(p.id),
            name=p.name,
            description=p.description,
            ad_groups=p.ad_groups or [],
            systems=[
                {
                    "id": str(s.id),
                    "system_type": s.system_type,
                    "system_id": s.system_id,
                    "system_name": s.system_name,
                    "config": s.config or {},
                }
                for s in p.systems
            ],
            created_at=p.created_at.isoformat(),
        )


class OnboardCreate(BaseModel):
    target_username: str
    display_name: str | None = None
    email: str | None = None
    profile_id: str
    notes: str | None = None


# ── External Connectors ────────────────────────────────────────────────────────

@router.get("/connectors", response_model=list[ConnectorRead])
async def list_connectors(db: DbDep, ctx: CtxDep):
    rows = (await db.execute(
        select(ExternalConnector)
        .where(ExternalConnector.tenant_id == ctx.tenant.id)
        .order_by(ExternalConnector.created_at)
    )).scalars().all()
    return [ConnectorRead.from_orm(c) for c in rows]


@router.post("/connectors", response_model=ConnectorRead, status_code=201)
async def create_connector(body: ConnectorCreate, db: DbDep, ctx: CtxDep):
    conn = ExternalConnector(
        tenant_id=ctx.tenant.id,
        name=body.name,
        connector_type=body.connector_type,
        encrypted_config=encrypt_credentials(body.config),
    )
    db.add(conn)
    await db.flush()
    await db.refresh(conn)
    return ConnectorRead.from_orm(conn)


@router.delete("/connectors/{connector_id}", status_code=204)
async def delete_connector(connector_id: UUID, db: DbDep, ctx: CtxDep):
    c = await db.get(ExternalConnector, connector_id)
    if not c or c.tenant_id != ctx.tenant.id:
        raise HTTPException(404)
    await db.delete(c)


@router.post("/connectors/{connector_id}/test")
async def test_connector(connector_id: UUID, db: DbDep, ctx: CtxDep):
    c = await db.get(ExternalConnector, connector_id)
    if not c or c.tenant_id != ctx.tenant.id:
        raise HTTPException(404)
    config = decrypt_credentials(c.encrypted_config)
    if c.connector_type == "guacamole":
        from app.services.guacamole_service import test_connection
    elif c.connector_type == "tactical_rmm":
        from app.services.tactical_rmm_service import test_connection
    elif c.connector_type == "unifi":
        from app.services.unifi_service import test_connection
    else:
        raise HTTPException(400, "Tipo de conector sem teste disponível")
    ok, msg = await test_connection(config)
    return {"success": ok, "message": msg}


# ── Onboarding Profiles ────────────────────────────────────────────────────────

@router.get("/profiles", response_model=list[ProfileRead])
async def list_profiles(db: DbDep, ctx: CtxDep):
    rows = (await db.execute(
        select(OnboardingProfile)
        .where(OnboardingProfile.tenant_id == ctx.tenant.id)
        .order_by(OnboardingProfile.name)
    )).scalars().all()
    return [ProfileRead.from_orm(p) for p in rows]


@router.post("/profiles", response_model=ProfileRead, status_code=201)
async def create_profile(body: ProfileCreate, db: DbDep, ctx: CtxDep):
    profile = OnboardingProfile(
        tenant_id=ctx.tenant.id,
        name=body.name,
        description=body.description,
        ad_groups=body.ad_groups,
    )
    db.add(profile)
    await db.flush()

    for s in body.systems:
        ps = OnboardingProfileSystem(
            profile_id=profile.id,
            system_type=s.system_type,
            system_id=s.system_id,
            system_name=s.system_name,
            config=s.config,
        )
        db.add(ps)

    await db.flush()
    await db.refresh(profile)
    return ProfileRead.from_orm(profile)


@router.put("/profiles/{profile_id}", response_model=ProfileRead)
async def update_profile(profile_id: UUID, body: ProfileCreate, db: DbDep, ctx: CtxDep):
    profile = await db.get(OnboardingProfile, profile_id)
    if not profile or profile.tenant_id != ctx.tenant.id:
        raise HTTPException(404)
    profile.name = body.name
    profile.description = body.description
    profile.ad_groups = body.ad_groups

    # Replace systems
    for s in profile.systems:
        await db.delete(s)
    await db.flush()

    for s in body.systems:
        ps = OnboardingProfileSystem(
            profile_id=profile.id,
            system_type=s.system_type,
            system_id=s.system_id,
            system_name=s.system_name,
            config=s.config,
        )
        db.add(ps)

    await db.flush()
    await db.refresh(profile)
    return ProfileRead.from_orm(profile)


@router.delete("/profiles/{profile_id}", status_code=204)
async def delete_profile(profile_id: UUID, db: DbDep, ctx: CtxDep):
    profile = await db.get(OnboardingProfile, profile_id)
    if not profile or profile.tenant_id != ctx.tenant.id:
        raise HTTPException(404)
    await db.delete(profile)


# ── Onboarding Actions ─────────────────────────────────────────────────────────

@router.post("/actions", status_code=201)
async def trigger_onboarding(body: OnboardCreate, background_tasks: BackgroundTasks, db: DbDep, ctx: CtxDep):
    profile = await db.get(OnboardingProfile, UUID(body.profile_id))
    if not profile or profile.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Perfil não encontrado")

    action = LifecycleAction(
        tenant_id=ctx.tenant.id,
        action_type=ActionType.onboard,
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
    profile_id = str(profile.id)
    tenant_id = ctx.tenant.id
    background_tasks.add_task(_bg_onboard, action_id, profile_id, tenant_id)
    return {"action_id": action_id, "status": "pending_discovery"}


async def _bg_onboard(action_id: str, profile_id: str, tenant_id) -> None:
    from uuid import UUID
    from app.services.onboarding_service import build_onboarding_tasks, run_onboarding
    async with AsyncSessionLocal() as db:
        action = await db.get(LifecycleAction, UUID(action_id))
        profile = await db.get(OnboardingProfile, UUID(profile_id))
        if not action or not profile:
            return
        try:
            tasks = await build_onboarding_tasks(db, action, profile)
            for t in tasks:
                db.add(t)
            action.status = ActionStatus.running
            await db.commit()
            # Reload for fresh session
            action = await db.get(LifecycleAction, UUID(action_id))
            profile = await db.get(OnboardingProfile, UUID(profile_id))
            await run_onboarding(db, action, profile)
        except Exception:
            action.status = ActionStatus.failed
            await db.commit()
