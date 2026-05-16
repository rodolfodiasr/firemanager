from __future__ import annotations
from typing import Annotated, Optional
from uuid import UUID
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_tenant_context, require_tenant_admin, TenantContext
from app.database import get_db
from app.models.web_audit import WebAuditConfig, WebAuditEntry, WebAuditFinding
from app.services import web_audit_service

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class WebAuditConfigRead(BaseModel):
    id: UUID
    tenant_id: UUID
    enabled: bool
    collection_method: str
    gpo_share_path: Optional[str]
    poll_interval_minutes: int
    retention_days: int
    alert_on_malicious: bool
    alert_on_shadow_it: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class WebAuditConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    collection_method: Optional[str] = None
    gpo_share_path: Optional[str] = None
    poll_interval_minutes: Optional[int] = None
    retention_days: Optional[int] = None
    alert_on_malicious: Optional[bool] = None
    alert_on_shadow_it: Optional[bool] = None


class WebAuditEntryRead(BaseModel):
    id: UUID
    workstation: str
    ad_user: Optional[str]
    department: Optional[str]
    url: str
    domain: str
    visited_at: datetime
    browser: Optional[str]
    title: Optional[str]
    visit_count: int
    category: str
    ai_analyzed: bool
    model_config = {"from_attributes": True}


class WebAuditFindingRead(BaseModel):
    id: UUID
    workstation: str
    ad_user: Optional[str]
    finding_type: str
    severity: str
    domain: str
    description: str
    recommendation: Optional[str]
    ai_confidence: Optional[float]
    soar_triggered: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class UserRiskSummary(BaseModel):
    ad_user: str
    department: Optional[str]
    total_visits: int
    malicious_count: int
    shadow_it_count: int
    productivity_score: int
    risk_level: str


class DomainStats(BaseModel):
    domain: str
    category: str
    visit_count: int
    unique_users: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/config", response_model=WebAuditConfigRead)
async def get_config(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WebAuditConfig:
    return await web_audit_service.get_or_create_config(db, ctx.tenant.id)


@router.put("/config", response_model=WebAuditConfigRead)
async def update_config(
    data: WebAuditConfigUpdate,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WebAuditConfig:
    cfg = await web_audit_service.get_or_create_config(db, ctx.tenant.id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(cfg, field, value)
    await db.flush()
    await db.refresh(cfg)
    return cfg


@router.post("/upload")
async def upload_history(
    file: UploadFile = File(...),
    workstation: str = Query(...),
    ad_user: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    content = (await file.read()).decode("utf-8", errors="replace")
    rows = web_audit_service.parse_browsing_history_csv(content)
    if not rows:
        raise HTTPException(status_code=400, detail="Nenhuma entrada válida encontrada no arquivo")
    cfg = await web_audit_service.get_or_create_config(db, ctx.tenant.id)
    count = await web_audit_service.ingest_entries(
        db, ctx.tenant.id, cfg.id, rows, workstation, ad_user, department
    )
    return {"ingested": count}


@router.get("/entries", response_model=list[WebAuditEntryRead])
async def list_entries(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    workstation: Optional[str] = Query(None),
    ad_user: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    days: int = Query(30),
    limit: int = Query(200),
) -> list[WebAuditEntry]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = (
        select(WebAuditEntry)
        .where(WebAuditEntry.tenant_id == ctx.tenant.id, WebAuditEntry.visited_at >= since)
    )
    if workstation:
        q = q.where(WebAuditEntry.workstation.ilike(f"%{workstation}%"))
    if ad_user:
        q = q.where(WebAuditEntry.ad_user.ilike(f"%{ad_user}%"))
    if category:
        q = q.where(WebAuditEntry.category == category)
    q = q.order_by(WebAuditEntry.visited_at.desc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/findings", response_model=list[WebAuditFindingRead])
async def list_findings(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    severity: Optional[str] = Query(None),
    finding_type: Optional[str] = Query(None),
    limit: int = Query(200),
) -> list[WebAuditFinding]:
    return await web_audit_service.get_findings(db, ctx.tenant.id, severity, finding_type, limit)


@router.get("/stats/users", response_model=list[UserRiskSummary])
async def user_risk_stats(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(30),
) -> list[dict]:
    return await web_audit_service.get_user_risk_summary(db, ctx.tenant.id, days)


@router.get("/stats/domains", response_model=list[DomainStats])
async def domain_stats(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(30),
    limit: int = Query(50),
) -> list[dict]:
    return await web_audit_service.get_domain_stats(db, ctx.tenant.id, days, limit)


@router.post("/analyze")
async def trigger_analysis(
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    analyzed = await web_audit_service.analyze_entries_with_ai(db, ctx.tenant.id)
    return {"analyzed": analyzed}
