from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogRead

router = APIRouter()


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
