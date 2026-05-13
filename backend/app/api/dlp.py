"""DLP — endpoints REST para configuração por tenant."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.dlp import DLPConfig, DLPIncident, DLPRule
from app.models.user_tenant_role import TenantRole
from app.services import dlp_service

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class DLPConfigRead(BaseModel):
    id: str
    tenant_id: str
    enabled: bool
    compliance_mode: bool
    incident_threshold_count: int
    incident_threshold_hours: int


class DLPConfigUpdate(BaseModel):
    enabled: bool | None = None
    compliance_mode: bool | None = None
    incident_threshold_count: int | None = None
    incident_threshold_hours: int | None = None


class DLPRuleRead(BaseModel):
    id: str
    rule_key: str
    rule_name: str
    description: str | None
    category: str
    action: str
    is_enabled: bool
    is_builtin: bool
    pattern: str | None


class DLPRuleUpdate(BaseModel):
    action: str | None = None
    is_enabled: bool | None = None


class DLPRuleCreate(BaseModel):
    rule_key: str
    rule_name: str
    description: str | None = None
    category: str = "custom"
    action: str = "warn"
    pattern: str


class DLPIncidentRead(BaseModel):
    id: str
    pii_type: str
    action_taken: str
    source: str
    ip_address: str | None
    user_id: str | None
    created_at: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_admin(ctx: TenantContext) -> None:
    if not ctx.user.is_super_admin and ctx.role not in (TenantRole.admin,):
        raise HTTPException(status_code=403, detail="Requer perfil admin")


async def _get_config(db: AsyncSession, tenant_id: UUID) -> DLPConfig:
    return await dlp_service.get_or_create_config(db, tenant_id)


async def _ensure_rules_seeded(db: AsyncSession, tenant_id: UUID) -> None:
    count = (await db.execute(
        select(sqlfunc.count()).select_from(DLPRule).where(DLPRule.tenant_id == tenant_id)
    )).scalar_one()
    if count == 0:
        await dlp_service.seed_builtin_rules(db, tenant_id)
        await db.commit()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/config", response_model=DLPConfigRead)
async def get_config(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
    tenant_id: UUID | None = None,
) -> DLPConfigRead:
    _require_admin(ctx)
    tid = tenant_id if (ctx.user.is_super_admin and tenant_id) else ctx.tenant.id
    cfg = await _get_config(db, tid)
    return DLPConfigRead(
        id=str(cfg.id), tenant_id=str(cfg.tenant_id),
        enabled=cfg.enabled, compliance_mode=cfg.compliance_mode,
        incident_threshold_count=cfg.incident_threshold_count,
        incident_threshold_hours=cfg.incident_threshold_hours,
    )


@router.put("/config", response_model=DLPConfigRead)
async def update_config(
    body: DLPConfigUpdate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
    tenant_id: UUID | None = None,
) -> DLPConfigRead:
    _require_admin(ctx)
    tid = tenant_id if (ctx.user.is_super_admin and tenant_id) else ctx.tenant.id
    cfg = await _get_config(db, tid)

    # compliance_mode = true → admin do tenant não pode desativar DLP
    if cfg.compliance_mode and not ctx.user.is_super_admin:
        if body.enabled is False:
            raise HTTPException(status_code=403, detail="Modo compliance ativo — DLP não pode ser desativado")
        if body.compliance_mode is False:
            raise HTTPException(status_code=403, detail="Modo compliance só pode ser desativado por super admin")

    if body.enabled is not None:
        cfg.enabled = body.enabled
    if body.compliance_mode is not None:
        cfg.compliance_mode = body.compliance_mode
    if body.incident_threshold_count is not None:
        cfg.incident_threshold_count = body.incident_threshold_count
    if body.incident_threshold_hours is not None:
        cfg.incident_threshold_hours = body.incident_threshold_hours

    await db.flush()
    await db.refresh(cfg)
    await db.commit()
    return DLPConfigRead(
        id=str(cfg.id), tenant_id=str(cfg.tenant_id),
        enabled=cfg.enabled, compliance_mode=cfg.compliance_mode,
        incident_threshold_count=cfg.incident_threshold_count,
        incident_threshold_hours=cfg.incident_threshold_hours,
    )


@router.get("/rules", response_model=list[DLPRuleRead])
async def list_rules(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
    tenant_id: UUID | None = None,
) -> list[DLPRuleRead]:
    _require_admin(ctx)
    tid = tenant_id if (ctx.user.is_super_admin and tenant_id) else ctx.tenant.id
    await _ensure_rules_seeded(db, tid)

    rows = (await db.execute(
        select(DLPRule).where(DLPRule.tenant_id == tid).order_by(DLPRule.category, DLPRule.rule_name)
    )).scalars().all()

    return [
        DLPRuleRead(
            id=str(r.id), rule_key=r.rule_key, rule_name=r.rule_name,
            description=r.description, category=r.category,
            action=r.action, is_enabled=r.is_enabled,
            is_builtin=r.is_builtin, pattern=r.pattern,
        )
        for r in rows
    ]


@router.put("/rules/{rule_id}", response_model=DLPRuleRead)
async def update_rule(
    rule_id: UUID,
    body: DLPRuleUpdate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
    tenant_id: UUID | None = None,
) -> DLPRuleRead:
    _require_admin(ctx)
    tid = tenant_id if (ctx.user.is_super_admin and tenant_id) else ctx.tenant.id

    row = (await db.execute(
        select(DLPRule).where(DLPRule.id == rule_id, DLPRule.tenant_id == tid)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Regra não encontrada")

    if body.action is not None:
        if body.action not in ("block", "warn"):
            raise HTTPException(status_code=422, detail="action deve ser 'block' ou 'warn'")
        row.action = body.action
    if body.is_enabled is not None:
        row.is_enabled = body.is_enabled

    await db.flush()
    await db.refresh(row)
    await db.commit()
    return DLPRuleRead(
        id=str(row.id), rule_key=row.rule_key, rule_name=row.rule_name,
        description=row.description, category=row.category,
        action=row.action, is_enabled=row.is_enabled,
        is_builtin=row.is_builtin, pattern=row.pattern,
    )


@router.post("/rules", response_model=DLPRuleRead, status_code=201)
async def create_rule(
    body: DLPRuleCreate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
    tenant_id: UUID | None = None,
) -> DLPRuleRead:
    _require_admin(ctx)
    tid = tenant_id if (ctx.user.is_super_admin and tenant_id) else ctx.tenant.id

    if body.action not in ("block", "warn"):
        raise HTTPException(status_code=422, detail="action deve ser 'block' ou 'warn'")

    import re as _re
    try:
        _re.compile(body.pattern)
    except _re.error as exc:
        raise HTTPException(status_code=422, detail=f"Padrão regex inválido: {exc}")

    existing = (await db.execute(
        select(DLPRule).where(DLPRule.tenant_id == tid, DLPRule.rule_key == body.rule_key)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="rule_key já existe para este tenant")

    row = DLPRule(
        tenant_id=tid, rule_key=body.rule_key, rule_name=body.rule_name,
        description=body.description, category=body.category,
        action=body.action, is_enabled=True, is_builtin=False, pattern=body.pattern,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    await db.commit()
    return DLPRuleRead(
        id=str(row.id), rule_key=row.rule_key, rule_name=row.rule_name,
        description=row.description, category=row.category,
        action=row.action, is_enabled=row.is_enabled,
        is_builtin=row.is_builtin, pattern=row.pattern,
    )


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
    tenant_id: UUID | None = None,
) -> None:
    _require_admin(ctx)
    tid = tenant_id if (ctx.user.is_super_admin and tenant_id) else ctx.tenant.id

    row = (await db.execute(
        select(DLPRule).where(DLPRule.id == rule_id, DLPRule.tenant_id == tid)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    if row.is_builtin:
        raise HTTPException(status_code=403, detail="Regras builtin não podem ser removidas — desative-as em vez disso")

    await db.delete(row)
    await db.commit()


@router.get("/incidents", response_model=list[DLPIncidentRead])
async def list_incidents(
    ctx:   Annotated[TenantContext, Depends(get_tenant_context)],
    db:    Annotated[AsyncSession, Depends(get_db)],
    tenant_id: UUID | None = None,
    limit: int = 50,
) -> list[DLPIncidentRead]:
    _require_admin(ctx)
    tid = tenant_id if (ctx.user.is_super_admin and tenant_id) else ctx.tenant.id

    rows = (await db.execute(
        select(DLPIncident)
        .where(DLPIncident.tenant_id == tid)
        .order_by(DLPIncident.created_at.desc())
        .limit(min(limit, 200))
    )).scalars().all()

    return [
        DLPIncidentRead(
            id=str(r.id), pii_type=r.pii_type, action_taken=r.action_taken,
            source=r.source, ip_address=r.ip_address,
            user_id=str(r.user_id) if r.user_id else None,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]
