"""GLPI integration API — per-tenant config and ticket analysis listing."""
import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_current_user, require_tenant_admin, User
from app.database import get_db
from sqlalchemy.orm import joinedload
from app.models.glpi_integration import GlpiIntegration
from app.models.glpi_ticket_analysis import GlpiTicketAnalysis, GlpiAnalysisStatus
from app.schemas.glpi import (
    GlpiAnalysisListItem,
    GlpiIntegrationCreate,
    GlpiIntegrationRead,
    GlpiIntegrationUpdate,
    GlpiTestResult,
    GlpiTicketAnalysisRead,
)
from app.utils.crypto import decrypt_credentials, encrypt_credentials

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_integration_for_tenant(
    integration_id: UUID,
    tenant_id: UUID,
    db: AsyncSession,
) -> GlpiIntegration:
    result = await db.execute(
        select(GlpiIntegration).where(GlpiIntegration.id == integration_id)
    )
    intg = result.scalar_one_or_none()
    if not intg:
        raise HTTPException(status_code=404, detail="Integração GLPI não encontrada")
    if intg.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Sem acesso a esta integração")
    return intg


# ── Integration endpoints ─────────────────────────────────────────────────────

@router.get("/integrations", response_model=GlpiIntegrationRead | None)
async def get_glpi_integration(
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> GlpiIntegrationRead | None:
    """Return the GLPI integration for the current tenant, or null if not configured."""
    result = await db.execute(
        select(GlpiIntegration).where(GlpiIntegration.tenant_id == ctx.tenant.id)
    )
    intg = result.scalar_one_or_none()
    if not intg:
        return None
    return GlpiIntegrationRead.model_validate(intg)


@router.post("/integrations", response_model=GlpiIntegrationRead, status_code=201)
async def create_glpi_integration(
    data: GlpiIntegrationCreate,
    ctx:  Annotated[TenantContext, Depends(require_tenant_admin)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> GlpiIntegrationRead:
    """Create a GLPI integration for the current tenant (one per tenant)."""
    existing = await db.execute(
        select(GlpiIntegration.id).where(GlpiIntegration.tenant_id == ctx.tenant.id)
    )
    if existing.scalar():
        raise HTTPException(
            status_code=409,
            detail="Já existe uma integração GLPI para este tenant. Use PATCH para atualizar.",
        )

    encrypted = encrypt_credentials({"password": data.password})

    intg = GlpiIntegration(
        tenant_id             = ctx.tenant.id,
        glpi_url              = data.glpi_url,
        app_token             = data.app_token,
        username              = data.username,
        encrypted_password    = encrypted,
        verify_ssl            = data.verify_ssl,
        min_priority          = data.min_priority,
        trigger_types         = data.trigger_types,
        trigger_categories    = data.trigger_categories,
        tag_analyzed          = data.tag_analyzed,
        poll_interval_minutes = data.poll_interval_minutes,
        lookback_hours        = data.lookback_hours,
    )
    db.add(intg)
    await db.flush()
    await db.refresh(intg)
    await db.commit()
    return GlpiIntegrationRead.model_validate(intg)


@router.patch("/integrations/{integration_id}", response_model=GlpiIntegrationRead)
async def update_glpi_integration(
    integration_id: UUID,
    data: GlpiIntegrationUpdate,
    ctx:  Annotated[TenantContext, Depends(require_tenant_admin)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> GlpiIntegrationRead:
    intg = await _get_integration_for_tenant(integration_id, ctx.tenant.id, db)

    if data.glpi_url is not None:
        intg.glpi_url = data.glpi_url
    if data.app_token is not None:
        intg.app_token = data.app_token
    if data.username is not None:
        intg.username = data.username
    if data.password is not None:
        intg.encrypted_password = encrypt_credentials({"password": data.password})
    if data.verify_ssl is not None:
        intg.verify_ssl = data.verify_ssl
    if data.is_active is not None:
        intg.is_active = data.is_active
    if data.min_priority is not None:
        intg.min_priority = data.min_priority
    if data.trigger_types is not None:
        intg.trigger_types = data.trigger_types
    if data.trigger_categories is not None:
        intg.trigger_categories = data.trigger_categories
    if data.tag_analyzed is not None:
        intg.tag_analyzed = data.tag_analyzed
    if data.poll_interval_minutes is not None:
        intg.poll_interval_minutes = data.poll_interval_minutes
    if data.lookback_hours is not None:
        intg.lookback_hours = data.lookback_hours

    await db.flush()
    await db.refresh(intg)
    await db.commit()
    return GlpiIntegrationRead.model_validate(intg)


@router.delete("/integrations/{integration_id}", status_code=204)
async def delete_glpi_integration(
    integration_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    intg = await _get_integration_for_tenant(integration_id, ctx.tenant.id, db)
    await db.delete(intg)
    await db.commit()


# ── Test connection ───────────────────────────────────────────────────────────

@router.post("/integrations/{integration_id}/test", response_model=GlpiTestResult)
async def test_glpi_integration(
    integration_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> GlpiTestResult:
    """Test connectivity to the GLPI instance — initSession then killSession."""
    from app.services.glpi_service import GlpiClient

    intg = await _get_integration_for_tenant(integration_id, ctx.tenant.id, db)
    creds = decrypt_credentials(intg.encrypted_password)
    password = creds.get("password", "")

    t0 = time.monotonic()
    try:
        async with GlpiClient(
            glpi_url=intg.glpi_url,
            app_token=intg.app_token,
            username=intg.username,
            password=password,
            verify_ssl=intg.verify_ssl,
        ) as client:
            # If we reach here the session opened successfully
            latency = round((time.monotonic() - t0) * 1000, 1)
            return GlpiTestResult(
                success=True,
                message="Conexão com GLPI estabelecida com sucesso.",
                latency_ms=latency,
            )
    except Exception as exc:
        latency = round((time.monotonic() - t0) * 1000, 1)
        return GlpiTestResult(
            success=False,
            message=f"Falha ao conectar: {exc}",
            latency_ms=latency,
        )


# ── Manual sync trigger ───────────────────────────────────────────────────────

@router.post("/integrations/{integration_id}/sync", status_code=202)
async def trigger_glpi_sync(
    integration_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Dispatch the GLPI sync Celery task immediately (without waiting for beat schedule)."""
    from app.workers.glpi_sync import run_glpi_sync

    intg = await _get_integration_for_tenant(integration_id, ctx.tenant.id, db)
    if not intg.is_active:
        raise HTTPException(status_code=400, detail="Integração inativa. Ative-a antes de sincronizar.")

    run_glpi_sync.delay()
    return {"message": "Sincronização GLPI iniciada em background."}


# ── Analyses listing ──────────────────────────────────────────────────────────

@router.get("/analyses", response_model=list[GlpiAnalysisListItem])
async def list_glpi_analyses(
    ctx:    Annotated[TenantContext, Depends(require_tenant_admin)],
    db:     Annotated[AsyncSession, Depends(get_db)],
    skip:   int = Query(0, ge=0),
    limit:  int = Query(50, ge=1, le=200),
    status: GlpiAnalysisStatus | None = Query(None),
    security_only: bool = Query(False),
    recurrent_only: bool = Query(False),
    itemtype: str | None = Query(None),
) -> list[GlpiAnalysisListItem]:
    """List ticket analyses for the current tenant, newest first."""
    stmt = (
        select(GlpiTicketAnalysis, GlpiIntegration.glpi_url)
        .join(GlpiIntegration, GlpiTicketAnalysis.glpi_integration_id == GlpiIntegration.id)
        .where(GlpiTicketAnalysis.tenant_id == ctx.tenant.id)
        .order_by(GlpiTicketAnalysis.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if status:
        stmt = stmt.where(GlpiTicketAnalysis.status == status)
    if security_only:
        stmt = stmt.where(GlpiTicketAnalysis.is_security_incident == True)
    if recurrent_only:
        stmt = stmt.where(GlpiTicketAnalysis.is_recurrent == True)
    if itemtype:
        stmt = stmt.where(GlpiTicketAnalysis.glpi_itemtype == itemtype)

    result = await db.execute(stmt)
    rows = result.all()
    return [
        GlpiAnalysisListItem.model_validate(row[0]).model_copy(update={"glpi_url": row[1]})
        for row in rows
    ]


@router.get("/analyses/{analysis_id}", response_model=GlpiTicketAnalysisRead)
async def get_glpi_analysis(
    analysis_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> GlpiTicketAnalysisRead:
    result = await db.execute(
        select(GlpiTicketAnalysis, GlpiIntegration.glpi_url)
        .join(GlpiIntegration, GlpiTicketAnalysis.glpi_integration_id == GlpiIntegration.id)
        .where(GlpiTicketAnalysis.id == analysis_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Análise não encontrada")
    analysis, glpi_url = row
    if analysis.tenant_id != ctx.tenant.id:
        raise HTTPException(status_code=403, detail="Sem acesso a esta análise")
    return GlpiTicketAnalysisRead.model_validate(analysis).model_copy(update={"glpi_url": glpi_url})
