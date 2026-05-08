"""Fase 24 — Executive dashboard and report API."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db

router = APIRouter()

CtxDep = Annotated[TenantContext, Depends(get_tenant_context)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("/posture")
async def get_security_posture(db: DbDep, ctx: CtxDep):
    from app.services.executive_report_service import get_security_posture
    return await get_security_posture(db, ctx.tenant.id)


@router.get("/report/pdf")
async def download_pdf_report(
    db: DbDep,
    ctx: CtxDep,
    period_days: int = Query(default=30, ge=7, le=365),
):
    from app.services.executive_report_service import generate_pdf_report
    pdf_bytes = await generate_pdf_report(db, ctx.tenant.id, period_days)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=relatorio-executivo.pdf"},
    )
