"""F23.ext — RMM Integrations API."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.services import rmm_service

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class RmmIntegrationCreate(BaseModel):
    name: str
    rmm_type: str
    base_url: str
    credentials: dict
    verify_ssl: bool = True
    site_filter: str | None = None


class RmmIntegrationUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    credentials: dict | None = None
    verify_ssl: bool | None = None
    is_active: bool | None = None
    site_filter: str | None = None


class RmmIntegrationRead(BaseModel):
    id: UUID
    name: str
    rmm_type: str
    base_url: str
    verify_ssl: bool
    is_active: bool
    last_sync_at: datetime | None
    last_sync_status: str | None
    last_sync_message: str | None
    agent_count: int
    site_filter: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class RmmAgentRead(BaseModel):
    id: UUID
    integration_id: UUID
    external_id: str
    hostname: str
    os_name: str | None
    ip_address: str | None
    status: str
    last_seen: datetime | None
    patches_pending: int | None
    alerts_count: int
    synced_at: datetime
    raw_data: Any | None = None
    model_config = {"from_attributes": True}


class RunRequest(BaseModel):
    run_type: str  # "script" | "command"
    shell: str = "powershell"
    body: str
    timeout: int = 60


class RmmScriptRunRead(BaseModel):
    id: UUID
    integration_id: UUID
    agent_external_id: str
    agent_hostname: str
    run_type: str
    shell: str
    body: str
    output: str | None
    exit_code: int | None
    status: str
    started_at: datetime
    finished_at: datetime | None
    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[RmmIntegrationRead])
async def list_integrations(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[RmmIntegrationRead]:
    integrations = await rmm_service.list_integrations(db, ctx.tenant.id)
    return [RmmIntegrationRead.model_validate(i) for i in integrations]


@router.post("", response_model=RmmIntegrationRead, status_code=201)
async def create_integration(
    data: RmmIntegrationCreate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RmmIntegrationRead:
    try:
        integration = await rmm_service.create_integration(
            db,
            tenant_id=ctx.tenant.id,
            name=data.name.strip(),
            rmm_type=data.rmm_type,
            base_url=data.base_url,
            credentials=data.credentials,
            verify_ssl=data.verify_ssl,
            site_filter=data.site_filter,
        )
        await db.commit()
        return RmmIntegrationRead.model_validate(integration)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{integration_id}", response_model=RmmIntegrationRead)
async def update_integration(
    integration_id: UUID,
    data: RmmIntegrationUpdate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RmmIntegrationRead:
    integration = await rmm_service.get_integration(db, integration_id, ctx.tenant.id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integração não encontrada.")
    integration = await rmm_service.update_integration(
        db, integration,
        name=data.name,
        base_url=data.base_url,
        credentials=data.credentials,
        verify_ssl=data.verify_ssl,
        is_active=data.is_active,
        site_filter=data.site_filter,
    )
    await db.commit()
    return RmmIntegrationRead.model_validate(integration)


@router.delete("/{integration_id}", status_code=204)
async def delete_integration(
    integration_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    integration = await rmm_service.get_integration(db, integration_id, ctx.tenant.id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integração não encontrada.")
    await rmm_service.delete_integration(db, integration)
    await db.commit()
    return Response(status_code=204)


@router.post("/{integration_id}/test")
async def test_connection(
    integration_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    integration = await rmm_service.get_integration(db, integration_id, ctx.tenant.id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integração não encontrada.")
    ok, message = await rmm_service.test_connection(integration)
    return {"ok": ok, "message": message}


@router.post("/{integration_id}/sync")
async def sync_agents(
    integration_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    integration = await rmm_service.get_integration(db, integration_id, ctx.tenant.id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integração não encontrada.")
    if not integration.is_active:
        raise HTTPException(status_code=400, detail="Integração inativa.")
    try:
        count = await rmm_service.sync_agents(db, integration)
        await db.commit()
        return {"synced": count, "message": f"{count} agente(s) sincronizados"}
    except Exception as e:
        integration.last_sync_status = "error"
        integration.last_sync_message = str(e)
        await db.commit()
        raise HTTPException(status_code=502, detail=f"Erro ao sincronizar: {e}")


@router.get("/{integration_id}/agents", response_model=list[RmmAgentRead])
async def list_agents(
    integration_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(None, description="Filtrar por status: online | offline"),
) -> list[RmmAgentRead]:
    integration = await rmm_service.get_integration(db, integration_id, ctx.tenant.id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integração não encontrada.")
    agents = await rmm_service.list_agents(db, ctx.tenant.id, integration_id)
    if status:
        agents = [a for a in agents if a.status == status]
    return [RmmAgentRead.model_validate(a) for a in agents]


@router.post("/{integration_id}/agents/{agent_external_id}/run", response_model=RmmScriptRunRead)
async def run_on_agent(
    integration_id: UUID,
    agent_external_id: str,
    data: RunRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RmmScriptRunRead:
    integration = await rmm_service.get_integration(db, integration_id, ctx.tenant.id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integração não encontrada.")
    if data.run_type not in ("script", "command"):
        raise HTTPException(status_code=400, detail="run_type deve ser 'script' ou 'command'.")
    if data.timeout < 5 or data.timeout > 300:
        raise HTTPException(status_code=400, detail="timeout deve estar entre 5 e 300 segundos.")

    agents = await rmm_service.list_agents(db, ctx.tenant.id, integration_id)
    agent = next((a for a in agents if a.external_id == agent_external_id), None)
    hostname = agent.hostname if agent else agent_external_id

    run = await rmm_service.execute_on_agent(
        db=db,
        integration=integration,
        agent_external_id=agent_external_id,
        agent_hostname=hostname,
        run_type=data.run_type,
        shell=data.shell,
        body=data.body,
        timeout=data.timeout,
        executed_by=ctx.user.id,
    )
    await db.commit()
    return RmmScriptRunRead.model_validate(run)


@router.get("/{integration_id}/script-runs", response_model=list[RmmScriptRunRead])
async def list_script_runs(
    integration_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    agent_id: str | None = Query(None),
    limit: int = Query(50, le=200),
) -> list[RmmScriptRunRead]:
    integration = await rmm_service.get_integration(db, integration_id, ctx.tenant.id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integração não encontrada.")
    runs = await rmm_service.list_script_runs(
        db, ctx.tenant.id, integration_id, agent_id, limit
    )
    return [RmmScriptRunRead.model_validate(r) for r in runs]
