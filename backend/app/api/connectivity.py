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
    PairAnalysisRequest,
)

router = APIRouter()


def _to_summary(r: ConnectivityAnalysis) -> ConnectivityAnalysisSummary:
    return ConnectivityAnalysisSummary(
        id=str(r.id),
        tenant_id=str(r.tenant_id) if r.tenant_id else None,
        device_id=str(r.device_id),
        mode=r.mode or "single",
        device_b_id=str(r.device_b_id) if r.device_b_id else None,
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
        mode=r.mode or "single",
        device_b_id=str(r.device_b_id) if r.device_b_id else None,
        status=r.status,
        routes=r.routes,
        bgp_peers=r.bgp_peers,
        ospf_neighbors=r.ospf_neighbors,
        sdwan_services=r.sdwan_services,
        device_b_routes=r.device_b_routes,
        device_b_bgp_peers=r.device_b_bgp_peers,
        device_b_ospf_neighbors=r.device_b_ospf_neighbors,
        device_b_sdwan_services=r.device_b_sdwan_services,
        anomalies=r.anomalies,
        ai_summary=r.ai_summary,
        ai_recommendations=r.ai_recommendations,
        error=r.error,
        created_at=r.created_at.isoformat(),
        completed_at=r.completed_at.isoformat() if r.completed_at else None,
    )


def _check_device_access(device: Device | None, ctx: TenantContext) -> Device:
    if not device or (not ctx.user.is_super_admin and device.tenant_id != ctx.tenant.id):
        raise HTTPException(404, "Dispositivo não encontrado")
    return device


# ── Análise individual ────────────────────────────────────────────────────────

@router.post("/analyze/{device_id}", response_model=ConnectivityAnalysisSummary, status_code=201)
async def trigger_analysis(
    device_id: UUID,
    background_tasks: BackgroundTasks,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> ConnectivityAnalysisSummary:
    device = _check_device_access(await db.get(Device, device_id), ctx)

    record = ConnectivityAnalysis(
        tenant_id=device.tenant_id,
        device_id=device.id,
        mode="single",
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


# ── Análise ponto-a-ponto (dois firewalls) ────────────────────────────────────

@router.post("/analyze-pair/{device_a_id}/{device_b_id}", response_model=ConnectivityAnalysisSummary, status_code=201)
async def trigger_pair_analysis(
    device_a_id: UUID,
    device_b_id: UUID,
    background_tasks: BackgroundTasks,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> ConnectivityAnalysisSummary:
    if device_a_id == device_b_id:
        raise HTTPException(400, "Dispositivo A e B devem ser diferentes")

    device_a = _check_device_access(await db.get(Device, device_a_id), ctx)
    device_b = _check_device_access(await db.get(Device, device_b_id), ctx)

    record = ConnectivityAnalysis(
        tenant_id=device_a.tenant_id,
        device_id=device_a.id,
        device_b_id=device_b.id,
        mode="pair",
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


# ── Listagens ─────────────────────────────────────────────────────────────────

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
    device = _check_device_access(await db.get(Device, device_id), ctx)

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
