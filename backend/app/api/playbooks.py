"""API F35 — SOAR Playbooks (CRUD, trigger manual, templates, MTTR)."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_tenant_admin
from app.database import get_db
from app.models.playbook import PlaybookExecution, PlaybookRule

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class PlaybookCreate(BaseModel):
    name: str
    description: str | None = None
    trigger_type: str
    trigger_condition: dict = {}
    actions: list[dict] = []
    cooldown_minutes: int = 30
    enabled: bool = True


class PlaybookRead(BaseModel):
    id: str
    name: str
    description: str | None
    trigger_type: str
    trigger_condition: dict
    actions: list[dict]
    cooldown_minutes: int
    enabled: bool
    is_template: bool
    template_name: str | None
    created_at: str


class PlaybookExecutionRead(BaseModel):
    id: str
    rule_id: str
    status: str
    triggered_at: str
    resolved_at: str | None
    actions_taken: list[dict]


# ── Rules ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[PlaybookRead])
async def list_playbooks(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    trigger_type: str | None = Query(None),
    enabled_only: bool = Query(False),
) -> list[PlaybookRead]:
    stmt = select(PlaybookRule).where(PlaybookRule.tenant_id == ctx.tenant.id)
    if trigger_type:
        stmt = stmt.where(PlaybookRule.trigger_type == trigger_type)
    if enabled_only:
        stmt = stmt.where(PlaybookRule.enabled.is_(True))
    result = await db.execute(stmt.order_by(PlaybookRule.created_at.desc()))
    rules = result.scalars().all()
    return [_rule_to_read(r) for r in rules]


@router.post("", response_model=PlaybookRead, status_code=201)
async def create_playbook(
    body: PlaybookCreate,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlaybookRead:
    rule = PlaybookRule(
        tenant_id=ctx.tenant.id,
        name=body.name,
        description=body.description,
        trigger_type=body.trigger_type,
        trigger_condition=body.trigger_condition,
        actions=body.actions,
        cooldown_minutes=body.cooldown_minutes,
        enabled=body.enabled,
        created_by=ctx.user.id,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    await db.commit()
    return _rule_to_read(rule)


@router.patch("/{rule_id}", response_model=PlaybookRead)
async def update_playbook(
    rule_id: UUID,
    body: PlaybookCreate,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlaybookRead:
    rule = await _get_rule(rule_id, ctx.tenant.id, db)
    rule.name = body.name
    rule.description = body.description
    rule.trigger_type = body.trigger_type
    rule.trigger_condition = body.trigger_condition
    rule.actions = body.actions
    rule.cooldown_minutes = body.cooldown_minutes
    rule.enabled = body.enabled
    await db.flush()
    await db.refresh(rule)
    await db.commit()
    return _rule_to_read(rule)


@router.delete("/{rule_id}", status_code=204, response_model=None)
async def delete_playbook(
    rule_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    rule = await _get_rule(rule_id, ctx.tenant.id, db)
    await db.delete(rule)
    await db.commit()


# ── Templates ─────────────────────────────────────────────────────────────────

@router.post("/templates/seed", status_code=201)
async def seed_templates(
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    from app.services.soar_service import seed_ad_templates
    count = await seed_ad_templates(db, ctx.tenant.id, ctx.user.id)
    return {"seeded": count, "message": "Templates AD instalados" if count else "Templates já existem"}


# ── Manual trigger ────────────────────────────────────────────────────────────

@router.post("/{rule_id}/trigger", status_code=202)
async def manual_trigger(
    rule_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    context: dict = {},
) -> dict:
    rule = await _get_rule(rule_id, ctx.tenant.id, db)
    from app.services.soar_service import evaluate_trigger
    executions = await evaluate_trigger(db, ctx.tenant.id, rule.trigger_type, context)
    return {"triggered": len(executions) > 0, "executions": executions}


# ── Executions ─────────────────────────────────────────────────────────────────

@router.get("/{rule_id}/executions", response_model=list[PlaybookExecutionRead])
async def list_executions(
    rule_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(20, le=100),
) -> list[PlaybookExecutionRead]:
    result = await db.execute(
        select(PlaybookExecution)
        .where(PlaybookExecution.rule_id == rule_id, PlaybookExecution.tenant_id == ctx.tenant.id)
        .order_by(PlaybookExecution.triggered_at.desc())
        .limit(limit)
    )
    execs = result.scalars().all()
    return [
        PlaybookExecutionRead(
            id=str(e.id), rule_id=str(e.rule_id), status=e.status,
            triggered_at=e.triggered_at.isoformat(),
            resolved_at=e.resolved_at.isoformat() if e.resolved_at else None,
            actions_taken=e.actions_taken or [],
        )
        for e in execs
    ]


@router.get("/stats/mttr")
async def mttr_stats(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    from app.services.soar_service import get_mttr_stats
    return await get_mttr_stats(db, ctx.tenant.id)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _get_rule(rule_id: UUID, tenant_id: UUID, db: AsyncSession) -> PlaybookRule:
    result = await db.execute(
        select(PlaybookRule).where(PlaybookRule.id == rule_id, PlaybookRule.tenant_id == tenant_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Playbook não encontrado")
    return rule


def _rule_to_read(r: PlaybookRule) -> PlaybookRead:
    return PlaybookRead(
        id=str(r.id), name=r.name, description=r.description,
        trigger_type=r.trigger_type, trigger_condition=r.trigger_condition,
        actions=r.actions, cooldown_minutes=r.cooldown_minutes,
        enabled=r.enabled, is_template=r.is_template, template_name=r.template_name,
        created_at=r.created_at.isoformat(),
    )
