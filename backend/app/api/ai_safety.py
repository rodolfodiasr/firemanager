"""API F33 — IA Safety & Governança: dual-approval, maintenance windows, erasure."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_module_reviewer
from app.database import get_db
from app.services import ai_safety_service as svc

router = APIRouter()
_require_admin = require_module_reviewer("compliance")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class WindowCreate(BaseModel):
    name: str
    description: str | None = None
    starts_at: object
    ends_at: object
    recurrence: str = "once"
    recurrence_day: int | None = None
    affected_devices: list | None = None
    block_ai_operations: bool = True
    block_bulk_jobs: bool = True
    is_active: bool = True


class WindowRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    starts_at: object
    ends_at: object
    recurrence: str
    affected_devices: list | None
    block_ai_operations: bool
    block_bulk_jobs: bool
    is_active: bool
    created_at: object
    model_config = {"from_attributes": True}


class ApprovalCreate(BaseModel):
    title: str
    description: str | None = None
    risk_level: str = "high"
    operation_context: dict | None = None
    requester_note: str | None = None
    requires_two_approvals: bool = True
    ttl_hours: int = 24


class ApprovalRead(BaseModel):
    id: UUID
    tenant_id: UUID
    title: str
    description: str | None
    risk_level: str
    operation_context: dict | None
    requester_id: UUID | None
    requester_note: str | None
    first_approver_id: UUID | None
    first_approved_at: object | None
    second_approver_id: UUID | None
    second_approved_at: object | None
    rejection_reason: str | None
    rejected_by: UUID | None
    rejected_at: object | None
    status: str
    requires_two_approvals: bool
    expires_at: object | None
    created_at: object
    model_config = {"from_attributes": True}


class RejectBody(BaseModel):
    reason: str


class ErasureCreate(BaseModel):
    target_user_email: str
    reason: str | None = None
    legal_basis: str | None = "Art. 18 LGPD — Direito à eliminação"


class ErasureRead(BaseModel):
    id: UUID
    tenant_id: UUID
    target_user_email: str
    reason: str | None
    legal_basis: str | None
    status: str
    rejection_reason: str | None
    affected_tables: list | None
    audit_summary: dict | None
    approved_by: UUID | None
    approved_at: object | None
    completed_at: object | None
    created_at: object
    model_config = {"from_attributes": True}


# ── Maintenance Windows ────────────────────────────────────────────────────────

@router.get("/maintenance-windows", response_model=list[WindowRead])
async def list_windows(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: bool = Query(default=False),
) -> list[WindowRead]:
    items = await svc.list_windows(db, ctx.tenant.id, active_only=active_only)
    return [WindowRead.model_validate(w) for w in items]


@router.post("/maintenance-windows", response_model=WindowRead, status_code=201)
async def create_window(
    body: WindowCreate,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WindowRead:
    data = body.model_dump()
    obj = await svc.create_window(db, ctx.tenant.id, data, created_by=ctx.user.id)
    return WindowRead.model_validate(obj)


@router.patch("/maintenance-windows/{window_id}", response_model=WindowRead)
async def update_window(
    window_id: UUID,
    body: WindowCreate,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WindowRead:
    obj = await svc.get_window(db, ctx.tenant.id, window_id)
    if not obj:
        raise HTTPException(404, "Janela de manutenção não encontrada")
    obj = await svc.update_window(db, obj, body.model_dump(exclude_unset=True))
    return WindowRead.model_validate(obj)


@router.delete("/maintenance-windows/{window_id}", status_code=204, response_model=None)
async def delete_window(
    window_id: UUID,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    obj = await svc.get_window(db, ctx.tenant.id, window_id)
    if not obj:
        raise HTTPException(404, "Janela de manutenção não encontrada")
    await db.delete(obj)
    await db.commit()


@router.get("/maintenance-windows/active", response_model=WindowRead | None)
async def get_active_window(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WindowRead | None:
    w = await svc.is_in_maintenance(db, ctx.tenant.id)
    return WindowRead.model_validate(w) if w else None


# ── Approval Requests ─────────────────────────────────────────────────────────

@router.get("/approvals", response_model=list[ApprovalRead])
async def list_approvals(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ApprovalRead]:
    items = await svc.list_approval_requests(db, ctx.tenant.id, status=status, limit=limit)
    return [ApprovalRead.model_validate(r) for r in items]


@router.post("/approvals", response_model=ApprovalRead, status_code=201)
async def create_approval(
    body: ApprovalCreate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApprovalRead:
    obj = await svc.create_approval_request(
        db,
        tenant_id=ctx.tenant.id,
        title=body.title,
        description=body.description,
        risk_level=body.risk_level,
        operation_context=body.operation_context,
        requester_id=ctx.user.id,
        requester_note=body.requester_note,
        requires_two=body.requires_two_approvals,
        ttl_hours=body.ttl_hours,
    )
    return ApprovalRead.model_validate(obj)


@router.post("/approvals/{request_id}/approve", response_model=ApprovalRead)
async def approve(
    request_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApprovalRead:
    obj = await svc.get_approval_request(db, ctx.tenant.id, request_id)
    if not obj:
        raise HTTPException(404, "Solicitação não encontrada")
    try:
        obj = await svc.approve_request(db, obj, ctx.user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ApprovalRead.model_validate(obj)


@router.post("/approvals/{request_id}/reject", response_model=ApprovalRead)
async def reject(
    request_id: UUID,
    body: RejectBody,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApprovalRead:
    obj = await svc.get_approval_request(db, ctx.tenant.id, request_id)
    if not obj:
        raise HTTPException(404, "Solicitação não encontrada")
    obj = await svc.reject_request(db, obj, ctx.user.id, body.reason)
    return ApprovalRead.model_validate(obj)


# ── Erasure Requests (LGPD) ───────────────────────────────────────────────────

@router.get("/erasure", response_model=list[ErasureRead])
async def list_erasure(
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(default=None),
) -> list[ErasureRead]:
    items = await svc.list_erasure_requests(db, ctx.tenant.id, status=status)
    return [ErasureRead.model_validate(r) for r in items]


@router.post("/erasure", response_model=ErasureRead, status_code=201)
async def create_erasure(
    body: ErasureCreate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ErasureRead:
    obj = await svc.create_erasure_request(
        db,
        tenant_id=ctx.tenant.id,
        target_email=body.target_user_email,
        reason=body.reason,
        legal_basis=body.legal_basis,
        requested_by=ctx.user.id,
    )
    return ErasureRead.model_validate(obj)


@router.post("/erasure/{request_id}/approve", response_model=ErasureRead)
async def approve_erasure(
    request_id: UUID,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ErasureRead:
    obj = await svc.get_erasure_request(db, ctx.tenant.id, request_id)
    if not obj:
        raise HTTPException(404, "Solicitação não encontrada")
    obj = await svc.approve_erasure(db, obj, ctx.user.id)
    return ErasureRead.model_validate(obj)


@router.post("/erasure/{request_id}/execute", response_model=ErasureRead)
async def execute_erasure(
    request_id: UUID,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ErasureRead:
    obj = await svc.get_erasure_request(db, ctx.tenant.id, request_id)
    if not obj:
        raise HTTPException(404, "Solicitação não encontrada")
    if obj.status not in ("in_progress", "approved"):
        raise HTTPException(400, f"Não é possível executar no status '{obj.status}'")
    obj = await svc.execute_erasure(db, obj)
    return ErasureRead.model_validate(obj)


@router.post("/erasure/{request_id}/reject", response_model=ErasureRead)
async def reject_erasure(
    request_id: UUID,
    body: RejectBody,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ErasureRead:
    obj = await svc.get_erasure_request(db, ctx.tenant.id, request_id)
    if not obj:
        raise HTTPException(404, "Solicitação não encontrada")
    obj = await svc.reject_erasure(db, obj, ctx.user.id, body.reason)
    return ErasureRead.model_validate(obj)
