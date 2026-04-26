"""Audit API — review queue, policy management, and audit logs."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.operation import Operation
from app.models.user import User, UserRole
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


async def _require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return current_user


# ── Review queue ────────────────────────────────────────────────────────────────

@router.get("/pending", response_model=list[AuditOperationRead])
async def list_pending(
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AuditOperationRead]:
    return await audit_service.get_pending_operations(db)


@router.get("/pending/count")
async def pending_count(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    if current_user.role != UserRole.admin:
        return {"count": 0}
    count = await audit_service.get_pending_count(db)
    return {"count": count}


@router.get("/direct", response_model=list[AuditOperationRead])
async def list_direct(
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AuditOperationRead]:
    return await audit_service.get_direct_operations(db)


@router.get("/history", response_model=list[AuditOperationRead])
async def list_history(
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AuditOperationRead]:
    return await audit_service.get_history_operations(db)


@router.post("/{operation_id}/review", response_model=dict)
async def review_operation(
    operation_id: UUID,
    body: ReviewRequest,
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        operation = await audit_service.submit_review(
            db=db,
            reviewer=admin,
            operation_id=operation_id,
            approved=body.approved,
            comment=body.comment,
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


# ── Policy management ───────────────────────────────────────────────────────────

@router.get("/policy", response_model=list[AuditPolicyRead])
async def get_policies(
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AuditPolicyRead]:
    policies = await audit_service.get_all_policies(db)
    return [AuditPolicyRead.model_validate(p) for p in policies]


@router.put("/policy", response_model=AuditPolicyRead)
async def upsert_policy(
    body: AuditPolicyUpsert,
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuditPolicyRead:
    if body.scope_type not in ("role", "user"):
        raise HTTPException(400, "scope_type deve ser 'role' ou 'user'")
    policy = await audit_service.upsert_policy(
        db=db,
        updater=admin,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        intent=body.intent,
        requires_approval=body.requires_approval,
    )
    return AuditPolicyRead.model_validate(policy)


@router.delete("/policy/{scope_type}/{scope_id}/{intent}", status_code=204)
async def delete_policy(
    scope_type: str,
    scope_id: str,
    intent: str,
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await audit_service.delete_policy(db, scope_type, scope_id, intent)


@router.get("/users", response_model=list[UserForPolicyRead])
async def get_users_for_policy(
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserForPolicyRead]:
    result = await db.execute(
        select(User).where(User.role == UserRole.operator).order_by(User.name)
    )
    return [UserForPolicyRead.model_validate(u) for u in result.scalars().all()]


# ── Legacy audit log endpoint ───────────────────────────────────────────────────

@router.get("/logs", response_model=list[AuditLogRead])
async def get_audit_logs(
    device_id: UUID | None = Query(default=None),
    user_id: UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=200),
    _: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> list[AuditLogRead]:
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if device_id:
        query = query.where(AuditLog.device_id == device_id)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    logs = list(result.scalars().all())
    return [AuditLogRead.model_validate(l) for l in logs]
