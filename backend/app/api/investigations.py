"""Investigations API — iterative read-only diagnostic sessions."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.investigation import InvestigationMessage, InvestigationPhase, InvestigationSession
from app.services import investigation_service as svc
from app.services.audit_log_service import write_audit

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class InvestigationStart(BaseModel):
    problem_description: str
    agent_type: str  # network | firewall | n3 | unified
    device_id: UUID | None = None
    device_ids: list[UUID] | None = None
    server_id: UUID | None = None
    integration_ids: list[str] | None = None


class ChatRequest(BaseModel):
    message: str


class CommandStateRead(BaseModel):
    idx: int
    command: str
    edited: str | None
    status: str  # pending | approved | rejected


class CommandStateUpdate(BaseModel):
    status: str | None = None   # pending | approved | rejected
    edited: str | None = None


class PhaseRead(BaseModel):
    id: UUID
    phase_number: int
    phase_name: str
    phase_purpose: str | None
    commands: list[str]
    command_states: list[CommandStateRead] | None
    raw_output: str | None
    analysis: str | None
    findings: list[str]
    status: str
    executed_at: str | None

    class Config:
        from_attributes = True


class MessageRead(BaseModel):
    id: UUID
    role: str
    content: str
    phase_number: int | None
    created_at: str

    class Config:
        from_attributes = True


class InvestigationRead(BaseModel):
    id: UUID
    tenant_id: UUID
    agent_type: str
    problem_description: str
    status: str
    current_phase: int
    synthesis: str | None
    cross_domain_detected: bool
    cross_domain_hint: str | None
    device_id: UUID | None = None
    device_ids: list[str] | None = None
    server_id: UUID | None = None
    phases: list[PhaseRead]
    messages: list[MessageRead]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


def _phase_read(p: InvestigationPhase) -> PhaseRead:
    cs_raw = p.command_states or []
    command_states = [
        CommandStateRead(
            idx=cs.get("idx", i),
            command=cs.get("command", ""),
            edited=cs.get("edited"),
            status=cs.get("status", "pending"),
        )
        for i, cs in enumerate(cs_raw)
    ] if cs_raw else None
    return PhaseRead(
        id=p.id,
        phase_number=p.phase_number,
        phase_name=p.phase_name,
        phase_purpose=p.phase_purpose,
        commands=p.commands or [],
        command_states=command_states,
        raw_output=p.raw_output,
        analysis=p.analysis,
        findings=p.findings or [],
        status=p.status,
        executed_at=p.executed_at.isoformat() if p.executed_at else None,
    )


def _msg_read(m: InvestigationMessage) -> MessageRead:
    return MessageRead(
        id=m.id,
        role=m.role,
        content=m.content,
        phase_number=m.phase_number,
        created_at=m.created_at.isoformat(),
    )


def _session_read(s: InvestigationSession) -> InvestigationRead:
    return InvestigationRead(
        id=s.id,
        tenant_id=s.tenant_id,
        agent_type=s.agent_type,
        problem_description=s.problem_description,
        status=s.status,
        current_phase=s.current_phase,
        synthesis=s.synthesis,
        cross_domain_detected=s.cross_domain_detected,
        cross_domain_hint=s.cross_domain_hint,
        device_id=s.device_id,
        device_ids=[str(did) for did in s.device_ids] if s.device_ids else None,
        server_id=s.server_id,
        phases=[_phase_read(p) for p in (s.phases or [])],
        messages=[_msg_read(m) for m in (s.messages or [])],
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
    )


_LOAD_RELATIONS = [
    selectinload(InvestigationSession.phases),
    selectinload(InvestigationSession.messages),
]


async def _get_session(db: AsyncSession, session_id: UUID, tenant_id: UUID) -> InvestigationSession:
    result = await db.execute(
        select(InvestigationSession)
        .options(*_LOAD_RELATIONS)
        .where(
            InvestigationSession.id == session_id,
            InvestigationSession.tenant_id == tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão de investigação não encontrada.")
    return session


async def _reload_session(db: AsyncSession, session_id: UUID) -> InvestigationSession:
    """Re-fetch a session with relationships after mutations (avoids lazy-load MissingGreenlet)."""
    result = await db.execute(
        select(InvestigationSession)
        .options(*_LOAD_RELATIONS)
        .where(InvestigationSession.id == session_id)
    )
    return result.scalar_one()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=InvestigationRead, status_code=201)
async def start_investigation(
    data: InvestigationStart,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> InvestigationRead:
    """Start a new investigation session. Claude plans the investigation phases."""
    if data.agent_type not in ("network", "firewall", "n3", "unified"):
        raise HTTPException(status_code=400, detail="agent_type inválido.")
    if not data.problem_description.strip():
        raise HTTPException(status_code=400, detail="Descreva o problema.")

    device_ids_str = [str(did) for did in data.device_ids] if data.device_ids else None
    # When device_ids provided but no single device_id, use first as primary for audit
    primary_device_id = data.device_id or (data.device_ids[0] if data.device_ids else None)

    session = InvestigationSession(
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        device_id=primary_device_id,
        device_ids=device_ids_str,
        server_id=data.server_id,
        integration_ids=data.integration_ids,
        agent_type=data.agent_type,
        problem_description=data.problem_description,
        status="planning",
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    # Add user's first message to chat history
    db.add(InvestigationMessage(
        session_id=session.id,
        role="user",
        content=data.problem_description,
    ))

    await svc.plan_investigation(db, session)
    await db.flush()

    reloaded = await _reload_session(db, session.id)
    await write_audit(
        db,
        action="investigation.started",
        user_id=ctx.user.id,
        device_id=session.device_id,
        details={
            "session_id": str(session.id),
            "agent_type": session.agent_type,
            "problem": session.problem_description[:200],
            "phases_planned": len(reloaded.phases),
        },
    )
    return _session_read(reloaded)


@router.get("", response_model=list[InvestigationRead])
async def list_investigations(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
    agent_type: str | None = None,
    limit: int = 20,
) -> list[InvestigationRead]:
    """List recent investigation sessions for this tenant."""
    q = (
        select(InvestigationSession)
        .options(*_LOAD_RELATIONS)
        .where(InvestigationSession.tenant_id == ctx.tenant.id)
    )
    if agent_type:
        q = q.where(InvestigationSession.agent_type == agent_type)
    q = q.order_by(InvestigationSession.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return [_session_read(s) for s in result.scalars().all()]


@router.get("/{session_id}", response_model=InvestigationRead)
async def get_investigation(
    session_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> InvestigationRead:
    session = await _get_session(db, session_id, ctx.tenant.id)
    return _session_read(session)


@router.post("/{session_id}/run-phase/{phase_number}", response_model=InvestigationRead)
async def run_phase(
    session_id: UUID,
    phase_number: int,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> InvestigationRead:
    """Execute a phase's read-only commands and analyze the results."""
    session = await _get_session(db, session_id, ctx.tenant.id)

    phase_result = await db.execute(
        select(InvestigationPhase).where(
            InvestigationPhase.session_id == session_id,
            InvestigationPhase.phase_number == phase_number,
        )
    )
    phase = phase_result.scalar_one_or_none()
    if not phase:
        raise HTTPException(status_code=404, detail=f"Fase {phase_number} não encontrada.")
    if phase.status == "done":
        raise HTTPException(status_code=400, detail="Fase já executada.")

    # Prevent parallel execution — only one phase at a time per session
    executing = [p for p in session.phases if p.status == "executing"]
    if executing:
        raise HTTPException(
            status_code=409,
            detail=f"Fase {executing[0].phase_number} já está em execução. Aguarde antes de iniciar outra.",
        )

    from app.services.investigation_service import _commands_to_run
    commands_run = _commands_to_run(phase)

    await svc.execute_phase(db, session, phase)
    await svc.analyze_phase(db, session, phase)
    await db.flush()

    await write_audit(
        db,
        action="investigation.phase_executed",
        user_id=ctx.user.id,
        device_id=session.device_id,
        details={
            "session_id": str(session_id),
            "phase_number": phase.phase_number,
            "phase_name": phase.phase_name,
            "commands_executed": commands_run,
            "findings_count": len(phase.findings or []),
            "cross_domain_detected": session.cross_domain_detected,
            "cross_domain_hint": session.cross_domain_hint,
        },
    )
    return _session_read(await _reload_session(db, session_id))


@router.patch("/{session_id}/phases/{phase_number}/commands/{cmd_idx}", response_model=InvestigationRead)
async def update_command_state(
    session_id: UUID,
    phase_number: int,
    cmd_idx: int,
    body: CommandStateUpdate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> InvestigationRead:
    """Update a single command's status (approve/reject) or edited text."""
    await _get_session(db, session_id, ctx.tenant.id)

    phase_result = await db.execute(
        select(InvestigationPhase).where(
            InvestigationPhase.session_id == session_id,
            InvestigationPhase.phase_number == phase_number,
        )
    )
    phase = phase_result.scalar_one_or_none()
    if not phase:
        raise HTTPException(status_code=404, detail=f"Fase {phase_number} não encontrada.")
    if phase.status == "done":
        raise HTTPException(status_code=400, detail="Fase já executada — não é possível alterar comandos.")

    states: list[dict] = list(phase.command_states or [])
    # Find or create the command state entry
    target = next((cs for cs in states if cs.get("idx") == cmd_idx), None)
    if target is None:
        if 0 <= cmd_idx < len(phase.commands):
            target = {"idx": cmd_idx, "command": phase.commands[cmd_idx], "edited": None, "status": "pending"}
            states.append(target)
        else:
            raise HTTPException(status_code=404, detail=f"Comando índice {cmd_idx} não encontrado.")

    if body.status is not None:
        if body.status not in ("pending", "approved", "rejected"):
            raise HTTPException(status_code=400, detail="status deve ser pending, approved ou rejected.")
        target["status"] = body.status
    if body.edited is not None:
        target["edited"] = body.edited.strip() or None

    # Sort by idx to keep order consistent
    states.sort(key=lambda x: x.get("idx", 0))
    await db.execute(
        sql_update(InvestigationPhase)
        .where(InvestigationPhase.id == phase.id)
        .values(command_states=states)
    )
    await db.flush()
    return _session_read(await _reload_session(db, session_id))


@router.post("/{session_id}/message", response_model=dict)
async def send_message(
    session_id: UUID,
    body: ChatRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Send a follow-up message within an active investigation."""
    session = await _get_session(db, session_id, ctx.tenant.id)
    if session.status == "done":
        raise HTTPException(status_code=400, detail="Investigação encerrada. Inicie uma nova.")

    response = await svc.chat_in_investigation(db, session, body.message)
    await db.flush()
    return {"response": response, "cross_domain_detected": session.cross_domain_detected, "cross_domain_hint": session.cross_domain_hint}


@router.post("/{session_id}/continue", response_model=InvestigationRead)
async def continue_investigation(
    session_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> InvestigationRead:
    """Generate new investigation phases building on the existing findings."""
    session = await _get_session(db, session_id, ctx.tenant.id)
    pending = [p for p in session.phases if p.status == "pending"]
    if pending:
        raise HTTPException(
            status_code=400,
            detail=f"Execute as {len(pending)} fase(s) pendentes antes de continuar.",
        )
    if not session.phases:
        raise HTTPException(status_code=400, detail="Nenhuma fase executada ainda.")
    await svc.continue_investigation(db, session)
    await db.flush()

    reloaded = await _reload_session(db, session_id)
    new_phases = [p for p in reloaded.phases if p.status == "pending"]
    if not new_phases:
        raise HTTPException(
            status_code=500,
            detail="Não foi possível gerar novas fases de investigação. Tente novamente.",
        )
    await write_audit(
        db,
        action="investigation.continued",
        user_id=ctx.user.id,
        device_id=session.device_id,
        details={
            "session_id": str(session_id),
            "new_phases_count": len(new_phases),
            "new_phase_names": [p.phase_name for p in new_phases],
            "total_phases": len(reloaded.phases),
        },
    )
    return _session_read(reloaded)


@router.post("/{session_id}/synthesize", response_model=InvestigationRead)
async def synthesize(
    session_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> InvestigationRead:
    """Generate final synthesis after all phases are done."""
    session = await _get_session(db, session_id, ctx.tenant.id)
    await svc.synthesize_investigation(db, session)
    await db.flush()

    await write_audit(
        db,
        action="investigation.synthesized",
        user_id=ctx.user.id,
        device_id=session.device_id,
        details={
            "session_id": str(session_id),
            "phases_count": len(session.phases),
            "agent_type": session.agent_type,
            "cross_domain_detected": session.cross_domain_detected,
        },
    )
    return _session_read(await _reload_session(db, session_id))


@router.post("/{session_id}/export-runbook", response_model=dict)
async def export_runbook(
    session_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Export investigation as AI Assistant session pre-loaded with context."""
    session = await _get_session(db, session_id, ctx.tenant.id)
    assistant_session_id = await svc.export_to_assistant(
        db, session, user_id=ctx.user.id, tenant_id=ctx.tenant.id
    )
    await db.flush()

    await write_audit(
        db,
        action="investigation.runbook_exported",
        user_id=ctx.user.id,
        device_id=session.device_id,
        details={
            "session_id": str(session_id),
            "assistant_session_id": str(assistant_session_id),
            "agent_type": session.agent_type,
            "problem": session.problem_description[:200],
        },
    )
    return {"assistant_session_id": str(assistant_session_id)}


@router.delete("/{session_id}", status_code=204, response_class=Response)
async def delete_investigation(
    session_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    session = await _get_session(db, session_id, ctx.tenant.id)

    await write_audit(
        db,
        action="investigation.deleted",
        user_id=ctx.user.id,
        device_id=session.device_id,
        details={
            "session_id": str(session_id),
            "agent_type": session.agent_type,
            "problem": session.problem_description[:200],
            "phases_count": len(session.phases),
            "status": session.status,
        },
    )
    await db.delete(session)
    return Response(status_code=204)
