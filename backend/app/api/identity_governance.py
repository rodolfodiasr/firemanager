"""API — Governança de Identidade AD/M365 (F36)."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_tenant_admin
from app.database import get_db
from app.models.identity_governance import (
    AccessCampaign,
    AccessReviewTask,
    IdentityConnector,
    JitRequest,
    SodRule,
    SodViolation,
)
from app.utils.crypto import decrypt_credentials, encrypt_credentials

router = APIRouter()


# ── Identity Connectors ───────────────────────────────────────────────────────

class ConnectorCreate(BaseModel):
    name: str
    source: str = "ad_ldap"
    config: dict   # {host, port, username, password, base_dn, use_ssl, ...}


class ConnectorRead(BaseModel):
    id: str
    name: str
    source: str
    is_active: bool
    last_sync_at: str | None
    last_sync_status: str | None

    class Config:
        from_attributes = True


@router.get("/connectors", response_model=list[ConnectorRead])
async def list_connectors(
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ConnectorRead]:
    result = await db.execute(
        select(IdentityConnector).where(IdentityConnector.tenant_id == ctx.tenant.id)
    )
    connectors = result.scalars().all()
    return [
        ConnectorRead(
            id=str(c.id),
            name=c.name,
            source=c.source,
            is_active=c.is_active,
            last_sync_at=c.last_sync_at.isoformat() if c.last_sync_at else None,
            last_sync_status=c.last_sync_status,
        )
        for c in connectors
    ]


@router.post("/connectors", status_code=201, response_model=ConnectorRead)
async def create_connector(
    body: ConnectorCreate,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConnectorRead:
    encrypted = encrypt_credentials(body.config)
    conn = IdentityConnector(
        tenant_id=ctx.tenant.id,
        name=body.name,
        source=body.source,
        config_encrypted=encrypted,
    )
    db.add(conn)
    await db.flush()
    await db.refresh(conn)
    await db.commit()
    return ConnectorRead(
        id=str(conn.id), name=conn.name, source=conn.source,
        is_active=conn.is_active, last_sync_at=None, last_sync_status=None,
    )


@router.post("/connectors/{connector_id}/test")
async def test_connector(
    connector_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(
        select(IdentityConnector).where(
            IdentityConnector.id == connector_id,
            IdentityConnector.tenant_id == ctx.tenant.id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(404, "Conector não encontrado")

    config = decrypt_credentials(conn.config_encrypted)
    from app.services import local_ad_service as ldap
    success, message = await ldap.test_connection(config)
    return {"success": success, "message": message}


@router.post("/connectors/{connector_id}/sync", status_code=202)
async def trigger_sync(
    connector_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(
        select(IdentityConnector).where(
            IdentityConnector.id == connector_id,
            IdentityConnector.tenant_id == ctx.tenant.id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(404, "Conector não encontrado")

    from app.workers.identity_sync import sync_identity_connector
    sync_identity_connector.delay(str(connector_id))
    return {"queued": True, "connector_id": str(connector_id)}


# ── AD Tool Kit endpoints (leitura) ──────────────────────────────────────────

@router.get("/connectors/{connector_id}/users")
async def list_ad_users(
    connector_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    department: str | None = Query(None),
    enabled_only: bool = Query(False),
    inactive_days: int | None = Query(None),
) -> dict:
    config = await _get_config(connector_id, ctx.tenant.id, db)
    from app.services.ad_governance_service import ad_list_users, ad_list_inactive_users

    if inactive_days:
        users = await ad_list_inactive_users(config, days=inactive_days)
    else:
        users = await ad_list_users(config, department=department, enabled_only=enabled_only)

    return {"count": len(users), "users": users}


@router.get("/connectors/{connector_id}/groups")
async def list_ad_groups(
    connector_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    config = await _get_config(connector_id, ctx.tenant.id, db)
    from app.services.ad_governance_service import ad_list_groups
    groups = await ad_list_groups(config)
    return {"count": len(groups), "groups": groups}


@router.get("/connectors/{connector_id}/reports/{report_type}")
async def compliance_report(
    connector_id: UUID,
    report_type: str,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    config = await _get_config(connector_id, ctx.tenant.id, db)
    from app.services.ad_governance_service import ad_compliance_report
    return await ad_compliance_report(config, report_type)


# ── AD Tool Kit endpoints (escrita — requerem admin) ─────────────────────────

class UserActionBody(BaseModel):
    username_or_upn: str
    reason: str


class GroupActionBody(BaseModel):
    username_or_upn: str
    group_name: str
    reason: str


class BatchDisableBody(BaseModel):
    upn_list: list[str]
    reason: str


@router.post("/connectors/{connector_id}/users/disable")
async def disable_user(
    connector_id: UUID,
    body: UserActionBody,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    config = await _get_config(connector_id, ctx.tenant.id, db)
    from app.services.ad_governance_service import ad_disable_user
    return await ad_disable_user(config, body.username_or_upn, body.reason, db, ctx.tenant.id, ctx.user.id)


@router.post("/connectors/{connector_id}/users/enable")
async def enable_user(
    connector_id: UUID,
    body: UserActionBody,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    config = await _get_config(connector_id, ctx.tenant.id, db)
    from app.services.ad_governance_service import ad_enable_user
    return await ad_enable_user(config, body.username_or_upn, body.reason, db, ctx.tenant.id, ctx.user.id)


@router.post("/connectors/{connector_id}/users/reset-password")
async def reset_password(
    connector_id: UUID,
    body: UserActionBody,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    config = await _get_config(connector_id, ctx.tenant.id, db)
    from app.services.ad_governance_service import ad_reset_password
    return await ad_reset_password(config, body.username_or_upn, db, ctx.tenant.id, ctx.user.id)


@router.post("/connectors/{connector_id}/users/add-to-group")
async def add_to_group(
    connector_id: UUID,
    body: GroupActionBody,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    config = await _get_config(connector_id, ctx.tenant.id, db)
    from app.services.ad_governance_service import ad_add_to_group
    return await ad_add_to_group(config, body.username_or_upn, body.group_name, body.reason, db, ctx.tenant.id, ctx.user.id)


@router.post("/connectors/{connector_id}/users/remove-from-group")
async def remove_from_group(
    connector_id: UUID,
    body: GroupActionBody,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    config = await _get_config(connector_id, ctx.tenant.id, db)
    from app.services.ad_governance_service import ad_remove_from_group
    return await ad_remove_from_group(config, body.username_or_upn, body.group_name, body.reason, db, ctx.tenant.id, ctx.user.id)


@router.post("/connectors/{connector_id}/users/batch-disable")
async def batch_disable(
    connector_id: UUID,
    body: BatchDisableBody,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    if len(body.upn_list) > 200:
        raise HTTPException(400, "Máximo 200 usuários por lote")
    config = await _get_config(connector_id, ctx.tenant.id, db)
    from app.services.ad_governance_service import ad_batch_disable_users
    return await ad_batch_disable_users(config, body.upn_list, body.reason, db, ctx.tenant.id, ctx.user.id)


# ── SoD Rules ─────────────────────────────────────────────────────────────────

@router.get("/sod/rules")
async def list_sod_rules(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    from app.services.ad_governance_service import seed_builtin_sod_rules
    await seed_builtin_sod_rules(db, ctx.tenant.id)
    result = await db.execute(select(SodRule).where(SodRule.tenant_id == ctx.tenant.id))
    rules = result.scalars().all()
    return [
        {
            "id": str(r.id), "name": r.name,
            "role_a": r.role_a_name, "role_b": r.role_b_name,
            "severity": r.severity, "enabled": r.enabled, "is_builtin": r.is_builtin,
        }
        for r in rules
    ]


@router.get("/sod/violations")
async def list_sod_violations(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(None),
) -> list[dict]:
    stmt = select(SodViolation).where(SodViolation.tenant_id == ctx.tenant.id)
    if status:
        stmt = stmt.where(SodViolation.status == status)
    result = await db.execute(stmt)
    violations = result.scalars().all()
    return [
        {
            "id": str(v.id), "user_id": str(v.user_id), "rule_id": str(v.rule_id),
            "status": v.status, "detected_at": v.detected_at.isoformat(),
        }
        for v in violations
    ]


# ── JIT Requests ──────────────────────────────────────────────────────────────

class JitCreateBody(BaseModel):
    target_group_name: str
    reason: str
    duration_hours: int = 4


@router.post("/jit/request", status_code=201)
async def jit_request(
    body: JitCreateBody,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    from app.services.ad_governance_service import jit_request_create
    return await jit_request_create(
        db, ctx.tenant.id, ctx.user.id,
        body.target_group_name, body.reason, body.duration_hours,
    )


@router.post("/jit/{jit_id}/approve")
async def jit_approve_endpoint(
    jit_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    connector_id: UUID | None = Body(None),
) -> dict:
    ad_config: dict | None = None
    if connector_id:
        ad_config = await _get_config(connector_id, ctx.tenant.id, db)

    from app.services.ad_governance_service import jit_approve
    return await jit_approve(db, jit_id, ctx.tenant.id, ctx.user.id, ad_config, ctx.user.id)


@router.get("/jit/pending")
async def list_jit_pending(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    result = await db.execute(
        select(JitRequest).where(
            JitRequest.tenant_id == ctx.tenant.id,
            JitRequest.status == "pending",
        ).order_by(JitRequest.created_at.desc())
    )
    items = result.scalars().all()
    return [
        {
            "id": str(j.id), "requester_id": str(j.requester_id),
            "target_group": j.target_group_name, "reason": j.reason,
            "duration_hours": j.duration_hours, "status": j.status,
            "created_at": j.created_at.isoformat(),
        }
        for j in items
    ]


# ── Access Campaigns ──────────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    name: str
    campaign_type: str = "by_manager"
    deadline: str
    recurrence: str = "once"
    scope_filter: dict = {}


@router.post("/campaigns", status_code=201)
async def create_campaign(
    body: CampaignCreate,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    from datetime import datetime
    campaign = AccessCampaign(
        tenant_id=ctx.tenant.id,
        name=body.name,
        campaign_type=body.campaign_type,
        deadline=datetime.fromisoformat(body.deadline),
        recurrence=body.recurrence,
        scope_filter=body.scope_filter,
        created_by=ctx.user.id,
        status="draft",
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    await db.commit()
    return {"id": str(campaign.id), "name": campaign.name, "status": campaign.status}


@router.get("/campaigns")
async def list_campaigns(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    result = await db.execute(
        select(AccessCampaign).where(AccessCampaign.tenant_id == ctx.tenant.id)
        .order_by(AccessCampaign.created_at.desc())
    )
    campaigns = result.scalars().all()
    return [
        {
            "id": str(c.id), "name": c.name, "status": c.status,
            "campaign_type": c.campaign_type,
            "deadline": c.deadline.isoformat(),
        }
        for c in campaigns
    ]


# ── Helper ────────────────────────────────────────────────────────────────────

async def _get_config(connector_id: UUID, tenant_id: UUID, db: AsyncSession) -> dict:
    result = await db.execute(
        select(IdentityConnector).where(
            IdentityConnector.id == connector_id,
            IdentityConnector.tenant_id == tenant_id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(404, "Conector de identidade não encontrado")
    return decrypt_credentials(conn.config_encrypted)
