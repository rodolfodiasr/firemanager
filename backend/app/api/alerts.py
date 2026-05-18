"""Fase 23 — Alert channels, rules, and events API."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.alert import AlertChannel, AlertRule, AlertEvent
from app.utils.crypto import decrypt_credentials, encrypt_credentials

router = APIRouter()

CtxDep = Annotated[TenantContext, Depends(get_tenant_context)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


# ── Schemas ────────────────────────────────────────────────────────────────────

class ChannelCreate(BaseModel):
    name: str
    channel_type: str
    config: dict


class ChannelRead(BaseModel):
    id: str
    name: str
    channel_type: str
    is_active: bool
    created_at: str

    @classmethod
    def from_orm(cls, c: AlertChannel) -> "ChannelRead":
        return cls(
            id=str(c.id), name=c.name,
            channel_type=c.channel_type, is_active=c.is_active,
            created_at=c.created_at.isoformat(),
        )


class RuleCreate(BaseModel):
    name: str
    trigger: str
    severity: str = "warning"
    channel_ids: list[str] = []


class RuleRead(BaseModel):
    id: str
    name: str
    trigger: str
    severity: str
    channel_ids: list[str]
    is_active: bool
    created_at: str

    @classmethod
    def from_orm(cls, r: AlertRule) -> "RuleRead":
        return cls(
            id=str(r.id), name=r.name, trigger=r.trigger,
            severity=r.severity, channel_ids=r.channel_ids or [],
            is_active=r.is_active, created_at=r.created_at.isoformat(),
        )


class EventRead(BaseModel):
    id: str
    trigger: str
    severity: str
    title: str
    body: str
    channels_result: dict
    created_at: str

    @classmethod
    def from_orm(cls, e: AlertEvent) -> "EventRead":
        return cls(
            id=str(e.id), trigger=e.trigger, severity=e.severity,
            title=e.title, body=e.body,
            channels_result=e.channels_result or {},
            created_at=e.created_at.isoformat(),
        )


# ── Alert Channels ─────────────────────────────────────────────────────────────

@router.get("/channels", response_model=list[ChannelRead])
async def list_channels(db: DbDep, ctx: CtxDep):
    rows = (await db.execute(
        select(AlertChannel).where(AlertChannel.tenant_id == ctx.tenant.id).order_by(AlertChannel.created_at)
    )).scalars().all()
    return [ChannelRead.from_orm(c) for c in rows]


@router.post("/channels", response_model=ChannelRead, status_code=201)
async def create_channel(body: ChannelCreate, db: DbDep, ctx: CtxDep):
    ch = AlertChannel(
        tenant_id=ctx.tenant.id,
        name=body.name,
        channel_type=body.channel_type,
        encrypted_config=encrypt_credentials(body.config),
    )
    db.add(ch)
    await db.flush()
    await db.refresh(ch)
    return ChannelRead.from_orm(ch)


@router.delete("/channels/{channel_id}", status_code=204)
async def delete_channel(channel_id: UUID, db: DbDep, ctx: CtxDep):
    ch = await db.get(AlertChannel, channel_id)
    if not ch or ch.tenant_id != ctx.tenant.id:
        raise HTTPException(404)
    await db.delete(ch)


@router.post("/channels/{channel_id}/test")
async def test_channel(channel_id: UUID, db: DbDep, ctx: CtxDep):
    ch = await db.get(AlertChannel, channel_id)
    if not ch or ch.tenant_id != ctx.tenant.id:
        raise HTTPException(404)
    from app.services.alert_service import test_channel as _test
    ok, msg = await _test(ch)
    return {"success": ok, "message": msg}


# ── Alert Rules ────────────────────────────────────────────────────────────────

@router.get("/rules", response_model=list[RuleRead])
async def list_rules(db: DbDep, ctx: CtxDep):
    rows = (await db.execute(
        select(AlertRule).where(AlertRule.tenant_id == ctx.tenant.id).order_by(AlertRule.created_at)
    )).scalars().all()
    return [RuleRead.from_orm(r) for r in rows]


@router.post("/rules", response_model=RuleRead, status_code=201)
async def create_rule(body: RuleCreate, db: DbDep, ctx: CtxDep):
    rule = AlertRule(
        tenant_id=ctx.tenant.id,
        name=body.name,
        trigger=body.trigger,
        severity=body.severity,
        channel_ids=body.channel_ids,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return RuleRead.from_orm(rule)


@router.put("/rules/{rule_id}", response_model=RuleRead)
async def update_rule(rule_id: UUID, body: RuleCreate, db: DbDep, ctx: CtxDep):
    rule = await db.get(AlertRule, rule_id)
    if not rule or rule.tenant_id != ctx.tenant.id:
        raise HTTPException(404)
    rule.name = body.name
    rule.trigger = body.trigger
    rule.severity = body.severity
    rule.channel_ids = body.channel_ids
    await db.flush()
    await db.refresh(rule)
    return RuleRead.from_orm(rule)


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(rule_id: UUID, db: DbDep, ctx: CtxDep):
    rule = await db.get(AlertRule, rule_id)
    if not rule or rule.tenant_id != ctx.tenant.id:
        raise HTTPException(404)
    await db.delete(rule)


@router.patch("/rules/{rule_id}/toggle")
async def toggle_rule(rule_id: UUID, db: DbDep, ctx: CtxDep):
    rule = await db.get(AlertRule, rule_id)
    if not rule or rule.tenant_id != ctx.tenant.id:
        raise HTTPException(404)
    rule.is_active = not rule.is_active
    await db.flush()
    return {"is_active": rule.is_active}


# ── Alert Events ───────────────────────────────────────────────────────────────

@router.get("/events", response_model=list[EventRead])
async def list_events(db: DbDep, ctx: CtxDep):
    rows = (await db.execute(
        select(AlertEvent)
        .where(AlertEvent.tenant_id == ctx.tenant.id)
        .order_by(AlertEvent.created_at.desc())
        .limit(200)
    )).scalars().all()
    return [EventRead.from_orm(e) for e in rows]


@router.post("/events/{event_id}/remediate", status_code=201)
async def remediate_event(event_id: UUID, db: DbDep, ctx: CtxDep):
    """Gera um plano de remediação a partir de um evento de alerta."""
    event = await db.get(AlertEvent, event_id)
    if not event or event.tenant_id != ctx.tenant.id:
        raise HTTPException(404)

    from app.services.remediation_service import generate_plan_from_context
    from app.schemas.remediation import RemediationPlanRead
    try:
        plan = await generate_plan_from_context(
            db=db,
            tenant_id=ctx.tenant.id,
            request=f"[Alerta] {event.title}\n\n{event.body}",
            origin_type="alert",
            origin_ref=str(event_id),
        )
        await db.commit()
        return RemediationPlanRead.model_validate(plan)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar plano: {exc}")
