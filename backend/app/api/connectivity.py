"""API routes for Fase 18 — Network Connectivity Analysis."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_reviewer
from app.database import get_db
from app.models.connectivity import ConnectivityAnalysis, ConnectivityStatus
from app.models.device import Device
from app.schemas.connectivity import (
    ConnectivityAnalysisRead,
    ConnectivityAnalysisSummary,
)

router = APIRouter()


def _to_summary(r: ConnectivityAnalysis) -> ConnectivityAnalysisSummary:
    return ConnectivityAnalysisSummary(
        id=str(r.id),
        tenant_id=str(r.tenant_id) if r.tenant_id else None,
        device_id=str(r.device_id),
        status=r.status,
        anomaly_count=len(r.anomalies or []),
        route_count=len(r.routes or []),
        created_at=r.created_at.isoformat(),
        completed_at=r.completed_at.isoformat() if r.completed_at else None,
        error=r.error,
    )


def _to_read(r: ConnectivityAnalysis) -> ConnectivityAnalysisRead:
    return ConnectivityAnalysisRead(
        id=str(r.id),
        tenant_id=str(r.tenant_id) if r.tenant_id else None,
        device_id=str(r.device_id),
        status=r.status,
        routes=r.routes,
        bgp_peers=r.bgp_peers,
        ospf_neighbors=r.ospf_neighbors,
        sdwan_services=r.sdwan_services,
        anomalies=r.anomalies,
        ai_summary=r.ai_summary,
        ai_recommendations=r.ai_recommendations,
        error=r.error,
        created_at=r.created_at.isoformat(),
        completed_at=r.completed_at.isoformat() if r.completed_at else None,
    )


@router.post("/analyze/{device_id}", response_model=ConnectivityAnalysisSummary, status_code=201)
async def trigger_analysis(
    device_id: UUID,
    background_tasks: BackgroundTasks,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> ConnectivityAnalysisSummary:
    device = await db.get(Device, device_id)
    if not device or (not ctx.user.is_super_admin and device.tenant_id != ctx.tenant.id):
        raise HTTPException(404, "Dispositivo não encontrado")

    record = ConnectivityAnalysis(
        tenant_id=device.tenant_id,
        device_id=device.id,
        status=ConnectivityStatus.pending,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    analysis_id = str(record.id)
    await db.commit()

    from app.services.connectivity_service import run_analysis
    background_tasks.add_task(run_analysis, analysis_id)

    await db.refresh(record)
    return _to_summary(record)


@router.get("", response_model=list[ConnectivityAnalysisSummary])
async def list_analyses(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[ConnectivityAnalysisSummary]:
    q = select(ConnectivityAnalysis).order_by(ConnectivityAnalysis.created_at.desc())
    if not ctx.user.is_super_admin:
        q = q.where(ConnectivityAnalysis.tenant_id == ctx.tenant.id)
    rows = await db.execute(q)
    return [_to_summary(r) for r in rows.scalars().all()]


@router.get("/device/{device_id}", response_model=list[ConnectivityAnalysisSummary])
async def list_device_analyses(
    device_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[ConnectivityAnalysisSummary]:
    device = await db.get(Device, device_id)
    if not device or (not ctx.user.is_super_admin and device.tenant_id != ctx.tenant.id):
        raise HTTPException(404, "Dispositivo não encontrado")

    rows = await db.execute(
        select(ConnectivityAnalysis)
        .where(ConnectivityAnalysis.device_id == device_id)
        .order_by(ConnectivityAnalysis.created_at.desc())
    )
    return [_to_summary(r) for r in rows.scalars().all()]


@router.get("/{analysis_id}", response_model=ConnectivityAnalysisRead)
async def get_analysis(
    analysis_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> ConnectivityAnalysisRead:
    record = await db.get(ConnectivityAnalysis, analysis_id)
    if not record:
        raise HTTPException(404, "Análise não encontrada")
    if not ctx.user.is_super_admin and record.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Análise não encontrada")
    return _to_read(record)


@router.delete("/{analysis_id}", status_code=204)
async def delete_analysis(
    analysis_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    record = await db.get(ConnectivityAnalysis, analysis_id)
    if not record:
        raise HTTPException(404, "Análise não encontrada")
    if not ctx.user.is_super_admin and record.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Análise não encontrada")
    if record.status == ConnectivityStatus.running:
        raise HTTPException(400, "Não é possível excluir uma análise em execução")
    await db.delete(record)
    await db.commit()
