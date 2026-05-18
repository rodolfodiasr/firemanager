"""Composite (coordinated) investigation API."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi import Depends
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.services import composite_service as svc

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class CompositeCreate(BaseModel):
    symptom: str
    domains: list[str]  # firewall | network | n3 | rmm


class SubmitFindingsRequest(BaseModel):
    findings: str
    investigation_session_id: UUID | None = None


class AssignRequest(BaseModel):
    assigned_to_id: UUID
    assigned_to_name: str


class CompositeChatRequest(BaseModel):
    message: str


class SubInvestigationRead(BaseModel):
    id: UUID
    composite_id: UUID
    domain: str
    assigned_to_id: UUID | None
    assigned_to_name: str | None
    status: str
    findings: str | None
    investigation_session_id: UUID | None
    submitted_at: str | None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class CompositeRead(BaseModel):
    id: UUID
    tenant_id: UUID
    created_by_id: UUID
    created_by_name: str
    symptom: str
    domains: list[str]
    status: str
    consolidation: str | None
    action_plan_session_id: UUID | None
    sub_investigations: list[SubInvestigationRead]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


def _sub_read(s) -> SubInvestigationRead:
    return SubInvestigationRead(
        id=s.id,
        composite_id=s.composite_id,
        domain=s.domain,
        assigned_to_id=s.assigned_to_id,
        assigned_to_name=s.assigned_to_name,
        status=s.status,
        findings=s.findings,
        investigation_session_id=s.investigation_session_id,
        submitted_at=s.submitted_at.isoformat() if s.submitted_at else None,
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
    )


def _inv_read(inv) -> CompositeRead:
    return CompositeRead(
        id=inv.id,
        tenant_id=inv.tenant_id,
        created_by_id=inv.created_by_id,
        created_by_name=inv.created_by_name,
        symptom=inv.symptom,
        domains=inv.domains or [],
        status=inv.status,
        consolidation=inv.consolidation,
        action_plan_session_id=inv.action_plan_session_id,
        sub_investigations=[_sub_read(s) for s in (inv.sub_investigations or [])],
        created_at=inv.created_at.isoformat(),
        updated_at=inv.updated_at.isoformat(),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=CompositeRead, status_code=201)
async def create_composite(
    data: CompositeCreate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> CompositeRead:
    valid_domains = {"firewall", "network", "n3", "rmm"}
    invalid = [d for d in data.domains if d not in valid_domains]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Domínios inválidos: {invalid}")
    if not data.domains:
        raise HTTPException(status_code=400, detail="Selecione ao menos um domínio.")
    if not data.symptom.strip():
        raise HTTPException(status_code=400, detail="Descreva o sintoma.")

    user_name = f"{ctx.user.first_name or ''} {ctx.user.last_name or ''}".strip() or ctx.user.email

    inv = await svc.create_composite(
        db,
        tenant_id=ctx.tenant.id,
        created_by_id=ctx.user.id,
        created_by_name=user_name,
        symptom=data.symptom,
        domains=data.domains,
    )
    return _inv_read(inv)


@router.get("", response_model=list[CompositeRead])
async def list_composites(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[CompositeRead]:
    invs = await svc.list_composites(db, ctx.tenant.id)
    return [_inv_read(inv) for inv in invs]


@router.get("/my-sub-investigations", response_model=list[SubInvestigationRead])
async def my_sub_investigations(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[SubInvestigationRead]:
    subs = await svc.list_my_sub_investigations(db, ctx.user.id, ctx.tenant.id)
    return [_sub_read(s) for s in subs]


@router.get("/{composite_id}", response_model=CompositeRead)
async def get_composite(
    composite_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> CompositeRead:
    inv = await svc.get_composite(db, composite_id, ctx.tenant.id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigação não encontrada.")
    return _inv_read(inv)


@router.post("/{composite_id}/sub/{sub_id}/assign", response_model=SubInvestigationRead)
async def assign_sub(
    composite_id: UUID,
    sub_id: UUID,
    body: AssignRequest,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> SubInvestigationRead:
    sub = await svc.get_sub_investigation(db, sub_id, ctx.tenant.id)
    if not sub or sub.composite_id != composite_id:
        raise HTTPException(status_code=404, detail="Sub-investigação não encontrada.")
    sub = await svc.assign_sub(db, sub, body.assigned_to_id, body.assigned_to_name)
    return _sub_read(sub)


@router.post("/{composite_id}/sub/{sub_id}/submit", response_model=SubInvestigationRead)
async def submit_findings(
    composite_id: UUID,
    sub_id: UUID,
    body: SubmitFindingsRequest,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> SubInvestigationRead:
    sub = await svc.get_sub_investigation(db, sub_id, ctx.tenant.id)
    if not sub or sub.composite_id != composite_id:
        raise HTTPException(status_code=404, detail="Sub-investigação não encontrada.")
    sub = await svc.submit_findings(db, sub, body.findings, body.investigation_session_id)
    return _sub_read(sub)


@router.post("/{composite_id}/sub/{sub_id}/escalate", response_model=SubInvestigationRead)
async def escalate_sub(
    composite_id: UUID,
    sub_id: UUID,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> SubInvestigationRead:
    sub = await svc.get_sub_investigation(db, sub_id, ctx.tenant.id)
    if not sub or sub.composite_id != composite_id:
        raise HTTPException(status_code=404, detail="Sub-investigação não encontrada.")
    sub = await svc.escalate_sub(db, sub)
    return _sub_read(sub)


@router.post("/{composite_id}/sub/{sub_id}/reopen", response_model=SubInvestigationRead)
async def reopen_sub(
    composite_id: UUID,
    sub_id: UUID,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> SubInvestigationRead:
    sub = await svc.get_sub_investigation(db, sub_id, ctx.tenant.id)
    if not sub or sub.composite_id != composite_id:
        raise HTTPException(status_code=404, detail="Sub-investigação não encontrada.")
    sub = await svc.reopen_sub(db, sub)
    return _sub_read(sub)


@router.post("/{composite_id}/consolidate", response_model=CompositeRead)
async def consolidate(
    composite_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> CompositeRead:
    inv = await svc.get_composite(db, composite_id, ctx.tenant.id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigação não encontrada.")
    has_findings = any(s.findings for s in (inv.sub_investigations or []))
    if not has_findings:
        raise HTTPException(status_code=400, detail="Nenhum achado submetido ainda.")
    inv = await svc.consolidate(db, inv)
    return _inv_read(inv)


@router.post("/{composite_id}/action-plan", response_model=CompositeRead)
async def generate_action_plan(
    composite_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> CompositeRead:
    inv = await svc.get_composite(db, composite_id, ctx.tenant.id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigação não encontrada.")
    if not inv.consolidation:
        raise HTTPException(status_code=400, detail="Realize a consolidação antes de gerar o plano.")
    inv = await svc.generate_action_plan(db, inv, ctx.user.id, ctx.tenant.id)
    return _inv_read(inv)


@router.post("/{composite_id}/resolve", response_model=CompositeRead)
async def resolve_composite(
    composite_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> CompositeRead:
    inv = await svc.get_composite(db, composite_id, ctx.tenant.id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigação não encontrada.")
    inv = await svc.resolve_composite(db, inv)
    return _inv_read(inv)


@router.post("/{composite_id}/chat", response_model=dict)
async def chat_in_composite(
    composite_id: UUID,
    body: CompositeChatRequest,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    inv = await svc.get_composite(db, composite_id, ctx.tenant.id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigação não encontrada.")
    response = await svc.chat_in_composite(db, inv, body.message)
    return {"response": response}


@router.delete("/{composite_id}", status_code=204, response_class=Response)
async def delete_composite(
    composite_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    inv = await svc.get_composite(db, composite_id, ctx.tenant.id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigação não encontrada.")
    await svc.delete_composite(db, inv)
    return Response(status_code=204)
