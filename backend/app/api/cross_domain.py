"""Cross-domain automatic investigation API."""
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
from app.services import cross_domain_service as svc

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class CrossDomainStart(BaseModel):
    problem_description: str
    domains: list[str]  # firewall | network | n3 | rmm


class CrossDomainChatRequest(BaseModel):
    message: str


class CrossDomainRerunRequest(BaseModel):
    additional_context: str | None = None


class SubResultRead(BaseModel):
    domain: str
    status: str
    investigation_session_id: str | None
    synthesis: str | None
    error: str | None
    started_at: str | None
    finished_at: str | None


class CrossDomainSessionRead(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    problem_description: str
    domains: list[str]
    status: str
    sub_results: list[SubResultRead]
    correlation: str | None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


def _session_read(s) -> CrossDomainSessionRead:
    return CrossDomainSessionRead(
        id=s.id,
        tenant_id=s.tenant_id,
        user_id=s.user_id,
        problem_description=s.problem_description,
        domains=s.domains or [],
        status=s.status,
        sub_results=[SubResultRead(**sr) for sr in (s.sub_results or [])],
        correlation=s.correlation,
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=CrossDomainSessionRead, status_code=201)
async def start_cross_domain(
    data: CrossDomainStart,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> CrossDomainSessionRead:
    valid_domains = {"firewall", "network", "n3", "rmm"}
    invalid = [d for d in data.domains if d not in valid_domains]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Domínios inválidos: {invalid}")
    if not data.domains:
        raise HTTPException(status_code=400, detail="Selecione ao menos um domínio.")
    if not data.problem_description.strip():
        raise HTTPException(status_code=400, detail="Descreva o problema.")

    session = await svc.start_session(
        db,
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        problem_description=data.problem_description,
        domains=data.domains,
    )
    return _session_read(session)


@router.get("", response_model=list[CrossDomainSessionRead])
async def list_cross_domain(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[CrossDomainSessionRead]:
    sessions = await svc.list_sessions(db, ctx.tenant.id)
    return [_session_read(s) for s in sessions]


@router.get("/{session_id}", response_model=CrossDomainSessionRead)
async def get_cross_domain(
    session_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> CrossDomainSessionRead:
    session = await svc.get_session(db, session_id, ctx.tenant.id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    return _session_read(session)


@router.post("/{session_id}/correlate", response_model=CrossDomainSessionRead)
async def correlate_cross_domain(
    session_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> CrossDomainSessionRead:
    session = await svc.get_session(db, session_id, ctx.tenant.id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    any_done = any(sr.get("status") == "done" for sr in (session.sub_results or []))
    if not any_done:
        raise HTTPException(status_code=400, detail="Nenhum domínio concluído ainda.")
    session = await svc.correlate(db, session)
    return _session_read(session)


@router.post("/{session_id}/rerun/{domain}", response_model=CrossDomainSessionRead)
async def rerun_domain(
    session_id: UUID,
    domain: str,
    body: CrossDomainRerunRequest,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> CrossDomainSessionRead:
    session = await svc.get_session(db, session_id, ctx.tenant.id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    session = await svc.rerun_domain(db, session, domain, body.additional_context)
    return _session_read(session)


@router.post("/{session_id}/chat/{domain}", response_model=dict)
async def chat_in_domain(
    session_id: UUID,
    domain: str,
    body: CrossDomainChatRequest,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    session = await svc.get_session(db, session_id, ctx.tenant.id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    response = await svc.chat_in_domain(db, session, domain, body.message)
    return {"response": response}


@router.delete("/{session_id}", status_code=204, response_class=Response)
async def delete_cross_domain(
    session_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    session = await svc.get_session(db, session_id, ctx.tenant.id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    await svc.delete_session(db, session)
    return Response(status_code=204)
