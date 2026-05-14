"""F37.ext — SIEM Syslog Configs API."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.siem_syslog import SiemSyslogConfig
from app.services.siem_syslog_service import send_cef_event

router = APIRouter()


class SyslogConfigCreate(BaseModel):
    name: str
    target_host: str
    target_port: int = 514
    protocol: str = "tcp"
    tls_enabled: bool = False
    tls_verify: bool = True
    facility: int = 1
    min_severity: str = "low"
    event_types: list[str] | None = None
    enabled: bool = True


class SyslogConfigUpdate(BaseModel):
    name: str | None = None
    target_host: str | None = None
    target_port: int | None = None
    protocol: str | None = None
    tls_enabled: bool | None = None
    tls_verify: bool | None = None
    facility: int | None = None
    min_severity: str | None = None
    enabled: bool | None = None


class SyslogConfigRead(BaseModel):
    id: UUID
    name: str
    target_host: str
    target_port: int
    protocol: str
    tls_enabled: bool
    tls_verify: bool
    facility: int
    min_severity: str
    event_types: Any | None
    enabled: bool
    last_forward_at: datetime | None
    events_forwarded: int
    created_at: datetime
    model_config = {"from_attributes": True}


@router.get("", response_model=list[SyslogConfigRead])
async def list_configs(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SyslogConfigRead]:
    result = await db.execute(
        select(SiemSyslogConfig)
        .where(SiemSyslogConfig.tenant_id == ctx.tenant.id)
        .order_by(SiemSyslogConfig.name)
    )
    configs = list(result.scalars().all())
    return [SyslogConfigRead.model_validate(c) for c in configs]


@router.post("", response_model=SyslogConfigRead, status_code=201)
async def create_config(
    data: SyslogConfigCreate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SyslogConfigRead:
    if data.protocol not in ("udp", "tcp", "tls"):
        raise HTTPException(status_code=400, detail="Protocolo deve ser udp, tcp ou tls.")
    config = SiemSyslogConfig(
        tenant_id=ctx.tenant.id,
        name=data.name.strip(),
        target_host=data.target_host.strip(),
        target_port=data.target_port,
        protocol=data.protocol,
        tls_enabled=data.tls_enabled,
        tls_verify=data.tls_verify,
        facility=data.facility,
        min_severity=data.min_severity,
        event_types=data.event_types,
        enabled=data.enabled,
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)
    await db.commit()
    return SyslogConfigRead.model_validate(config)


@router.patch("/{config_id}", response_model=SyslogConfigRead)
async def update_config(
    config_id: UUID,
    data: SyslogConfigUpdate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SyslogConfigRead:
    result = await db.execute(
        select(SiemSyslogConfig).where(
            SiemSyslogConfig.id == config_id,
            SiemSyslogConfig.tenant_id == ctx.tenant.id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada.")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(config, field, value)
    await db.flush()
    await db.refresh(config)
    await db.commit()
    return SyslogConfigRead.model_validate(config)


@router.delete("/{config_id}", status_code=204)
async def delete_config(
    config_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    result = await db.execute(
        select(SiemSyslogConfig).where(
            SiemSyslogConfig.id == config_id,
            SiemSyslogConfig.tenant_id == ctx.tenant.id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada.")
    await db.delete(config)
    await db.commit()
    return Response(status_code=204)


@router.post("/{config_id}/test")
async def test_config(
    config_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(
        select(SiemSyslogConfig).where(
            SiemSyslogConfig.id == config_id,
            SiemSyslogConfig.tenant_id == ctx.tenant.id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada.")
    try:
        await send_cef_event(
            target_host=config.target_host,
            target_port=config.target_port,
            protocol=config.protocol,
            tls_enabled=config.tls_enabled,
            tls_verify=config.tls_verify,
            facility=config.facility,
            event_type="TEST",
            severity="info",
            name="Eternity SecOps — Teste de conectividade CEF",
            message="Evento de teste gerado pela plataforma Eternity SecOps",
        )
        return {"ok": True, "message": "Evento CEF de teste enviado com sucesso."}
    except Exception as e:
        return {"ok": False, "message": str(e)}
