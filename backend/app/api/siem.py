"""F37 — SIEM connectors + webhook receiver + alert management."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_tenant_admin
from app.database import get_db
from app.models.siem import SiemAlert, SiemConnector

router = APIRouter()
webhook_router = APIRouter()

CtxDep = Annotated[TenantContext, Depends(get_tenant_context)]
DbDep = Annotated[AsyncSession, Depends(get_db)]

_VALID_TYPES = {"wazuh", "splunk", "sentinel", "log360", "qradar"}


# ── Schemas ───────────────────────────────────────────────────────────────────

class SiemConnectorCreate(BaseModel):
    name: str
    siem_type: str
    base_url: str
    config: dict = {}
    webhook_secret: str | None = None


class SiemConnectorRead(BaseModel):
    id: str
    name: str
    siem_type: str
    base_url: str
    webhook_secret: str
    is_active: bool
    last_event_at: str | None = None
    created_at: str

    @classmethod
    def from_orm(cls, c: SiemConnector) -> "SiemConnectorRead":
        return cls(
            id=str(c.id),
            name=c.name,
            siem_type=c.siem_type,
            base_url=c.base_url,
            webhook_secret=c.webhook_secret,
            is_active=c.is_active,
            last_event_at=c.last_event_at.isoformat() if c.last_event_at else None,
            created_at=c.created_at.isoformat(),
        )


class SiemAlertRead(BaseModel):
    id: str
    connector_id: str
    source_rule_id: str | None
    severity: str
    title: str
    description: str | None
    affected_host: str | None
    source_ip: str | None
    normalized_at: str
    playbook_triggered: bool


# ── Connector CRUD ────────────────────────────────────────────────────────────

@router.get("", response_model=list[SiemConnectorRead])
async def list_connectors(ctx: CtxDep, db: DbDep) -> list[SiemConnectorRead]:
    rows = (await db.execute(
        select(SiemConnector)
        .where(SiemConnector.tenant_id == ctx.tenant.id)
        .order_by(SiemConnector.created_at)
    )).scalars().all()
    return [SiemConnectorRead.from_orm(r) for r in rows]


@router.post("", response_model=SiemConnectorRead, status_code=201)
async def create_connector(
    body: SiemConnectorCreate,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: DbDep,
) -> SiemConnectorRead:
    if body.siem_type not in _VALID_TYPES:
        raise HTTPException(400, f"siem_type inválido. Use: {', '.join(_VALID_TYPES)}")

    from app.utils.crypto import encrypt_credentials
    config_enc = encrypt_credentials(body.config) if body.config else None
    webhook_secret = body.webhook_secret or secrets.token_hex(32)

    connector = SiemConnector(
        tenant_id=ctx.tenant.id,
        name=body.name,
        siem_type=body.siem_type,
        base_url=body.base_url.rstrip("/"),
        config_encrypted=config_enc,
        webhook_secret=webhook_secret,
    )
    db.add(connector)
    await db.flush()
    await db.refresh(connector)
    await db.commit()
    return SiemConnectorRead.from_orm(connector)


@router.get("/{connector_id}", response_model=SiemConnectorRead)
async def get_connector(connector_id: UUID, ctx: CtxDep, db: DbDep) -> SiemConnectorRead:
    c = await _get(connector_id, ctx.tenant.id, db)
    return SiemConnectorRead.from_orm(c)


@router.patch("/{connector_id}", response_model=SiemConnectorRead)
async def update_connector(
    connector_id: UUID,
    body: SiemConnectorCreate,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: DbDep,
) -> SiemConnectorRead:
    c = await _get(connector_id, ctx.tenant.id, db)
    if body.siem_type not in _VALID_TYPES:
        raise HTTPException(400, f"siem_type inválido")

    from app.utils.crypto import encrypt_credentials
    c.name = body.name
    c.siem_type = body.siem_type
    c.base_url = body.base_url.rstrip("/")
    if body.config:
        c.config_encrypted = encrypt_credentials(body.config)
    await db.flush()
    await db.refresh(c)
    await db.commit()
    return SiemConnectorRead.from_orm(c)


@router.delete("/{connector_id}", status_code=204, response_model=None)
async def delete_connector(
    connector_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: DbDep,
) -> None:
    c = await _get(connector_id, ctx.tenant.id, db)
    c.is_active = False
    await db.commit()


@router.post("/{connector_id}/ingest", status_code=202)
async def manual_ingest(
    connector_id: UUID,
    payload: dict,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: DbDep,
) -> dict:
    """Ingest manual de alerta (teste / reprocessamento)."""
    c = await _get(connector_id, ctx.tenant.id, db)
    from app.services.siem_service import process_inbound_alert
    alert = await process_inbound_alert(db, c, payload)
    return {"alert_id": str(alert.id), "severity": alert.severity, "title": alert.title}


# ── Alerts ────────────────────────────────────────────────────────────────────

@router.get("/alerts/list", response_model=list[SiemAlertRead])
async def list_alerts(
    ctx: CtxDep,
    db: DbDep,
    severity: str | None = None,
    triggered_only: bool = False,
    limit: int = 50,
) -> list[SiemAlertRead]:
    stmt = select(SiemAlert).where(SiemAlert.tenant_id == ctx.tenant.id)
    if severity:
        stmt = stmt.where(SiemAlert.severity == severity)
    if triggered_only:
        stmt = stmt.where(SiemAlert.playbook_triggered.is_(True))
    stmt = stmt.order_by(SiemAlert.normalized_at.desc()).limit(min(limit, 200))
    rows = (await db.execute(stmt)).scalars().all()
    return [
        SiemAlertRead(
            id=str(a.id), connector_id=str(a.connector_id),
            source_rule_id=a.source_rule_id, severity=a.severity,
            title=a.title, description=a.description,
            affected_host=a.affected_host, source_ip=a.source_ip,
            normalized_at=a.normalized_at.isoformat(),
            playbook_triggered=a.playbook_triggered,
        )
        for a in rows
    ]


# ── Webhook público (sem auth JWT) ────────────────────────────────────────────

@webhook_router.post("/siem/{webhook_secret}", status_code=200)
async def receive_webhook(
    webhook_secret: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Receptor público de alertas SIEM via webhook.

    Autentica pelo webhook_secret na URL. Aceita qualquer payload JSON.
    Para Wazuh: configura integration com url=.../webhooks/siem/<secret>.
    Para Splunk: alert action custom com essa URL.
    Para Sentinel: Logic App HTTP trigger.
    """
    row = (await db.execute(
        select(SiemConnector).where(
            SiemConnector.webhook_secret == webhook_secret,
            SiemConnector.is_active.is_(True),
        )
    )).scalar_one_or_none()

    if not row:
        raise HTTPException(404, "Webhook not found or inactive")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON payload")

    from app.services.siem_service import process_inbound_alert
    alert = await process_inbound_alert(db, row, payload)
    return {"received": True, "alert_id": str(alert.id), "severity": alert.severity}


# ── Helper ────────────────────────────────────────────────────────────────────

async def _get(connector_id: UUID, tenant_id: UUID, db: AsyncSession) -> SiemConnector:
    c = (await db.execute(
        select(SiemConnector).where(
            SiemConnector.id == connector_id,
            SiemConnector.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()
    if not c:
        raise HTTPException(404, "Conector SIEM não encontrado")
    return c
