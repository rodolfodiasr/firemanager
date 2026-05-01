"""Audit API — review queue, policy management, and audit logs."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_reviewer, require_tenant_admin
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.device import Device
from app.models.operation import Operation
from app.models.user import User
from app.models.user_tenant_role import TenantRole, UserTenantRole
from app.schemas.audit import (
    AuditLogRead,
    AuditOperationRead,
    AuditPolicyRead,
    AuditPolicyUpsert,
    ReviewRequest,
    UserForPolicyRead,
)
from app.services import audit_service

router = APIRouter()


# ── Review queue ──────────────────────────────────────────────────────────────

@router.get("/pending", response_model=list[AuditOperationRead])
async def list_pending(
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[AuditOperationRead]:
    return await audit_service.get_pending_operations(
        db, tenant_id=ctx.tenant.id, reviewer_role=ctx.role,
    )


@router.get("/pending/count")
async def pending_count(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    if ctx.role == TenantRole.readonly:
        return {"count": 0}
    count = await audit_service.get_pending_count(
        db, tenant_id=ctx.tenant.id, reviewer_role=ctx.role,
    )
    return {"count": count}


@router.get("/direct", response_model=list[AuditOperationRead])
async def list_direct(
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[AuditOperationRead]:
    return await audit_service.get_direct_operations(db, tenant_id=ctx.tenant.id)


@router.get("/history", response_model=list[AuditOperationRead])
async def list_history(
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[AuditOperationRead]:
    return await audit_service.get_history_operations(db, tenant_id=ctx.tenant.id)


@router.post("/{operation_id}/review", response_model=dict)
async def review_operation(
    operation_id: UUID,
    body: ReviewRequest,
    ctx:  Annotated[TenantContext, Depends(require_reviewer)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        operation = await audit_service.submit_review(
            db=db,
            reviewer=ctx.user,
            operation_id=operation_id,
            approved=body.approved,
            comment=body.comment,
            reviewer_tenant_role=ctx.role,
            tenant_id=ctx.tenant.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if body.approved:
        try:
            from app.workers.generate_documents import generate
            generate.delay(str(operation_id))
        except Exception:
            pass

    return {
        "approved": body.approved,
        "status": operation.status.value,
        "message": "Operação aprovada e executada." if body.approved else "Operação negada.",
    }


# ── Policy management ─────────────────────────────────────────────────────────

@router.get("/policy", response_model=list[AuditPolicyRead])
async def get_policies(
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[AuditPolicyRead]:
    policies = await audit_service.get_all_policies(db)
    return [AuditPolicyRead.model_validate(p) for p in policies]


@router.put("/policy", response_model=AuditPolicyRead)
async def upsert_policy(
    body: AuditPolicyUpsert,
    ctx:  Annotated[TenantContext, Depends(require_tenant_admin)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> AuditPolicyRead:
    if body.scope_type not in ("role", "user"):
        raise HTTPException(400, "scope_type deve ser 'role' ou 'user'")
    policy = await audit_service.upsert_policy(
        db=db,
        updater=ctx.user,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        intent=body.intent,
        requires_approval=body.requires_approval,
    )
    return AuditPolicyRead.model_validate(policy)


@router.delete("/policy/{scope_type}/{scope_id}/{intent}", status_code=204)
async def delete_policy(
    scope_type: str,
    scope_id:   str,
    intent:     str,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await audit_service.delete_policy(db, scope_type, scope_id, intent)


@router.get("/users", response_model=list[UserForPolicyRead])
async def get_users_for_policy(
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[UserForPolicyRead]:
    result = await db.execute(
        select(User)
        .join(UserTenantRole, UserTenantRole.user_id == User.id)
        .where(UserTenantRole.tenant_id == ctx.tenant.id)
        .order_by(User.name)
    )
    return [UserForPolicyRead.model_validate(u) for u in result.scalars().all()]


# ── Audit logs ────────────────────────────────────────────────────────────────

@router.get("/logs", response_model=list[AuditLogRead])
async def get_audit_logs(
    device_id: UUID | None = Query(default=None),
    user_id:   UUID | None = Query(default=None),
    skip:  int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=200),
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = None,
    db:  Annotated[AsyncSession, Depends(get_db)] = None,
) -> list[AuditLogRead]:
    query = (
        select(AuditLog)
        .join(Device, AuditLog.device_id == Device.id)
        .where(Device.tenant_id == ctx.tenant.id)
        .order_by(AuditLog.created_at.desc())
    )
    if device_id:
        query = query.where(AuditLog.device_id == device_id)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    logs = list(result.scalars().all())
    return [AuditLogRead.model_validate(l) for l in logs]
