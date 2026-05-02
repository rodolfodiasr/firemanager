"""Server Operations API — review queue and history for server Modo Técnico."""
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_reviewer
from app.database import get_db
from app.models.server import Server
from app.models.server_operation import ServerOperation, ServerOpStatus
from app.schemas.server_operation import ReviewRequest, ServerOperationRead

router = APIRouter()


@router.get("/pending", response_model=list[ServerOperationRead])
async def list_pending(
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[ServerOperationRead]:
    result = await db.execute(
        select(ServerOperation)
        .where(
            ServerOperation.tenant_id == ctx.tenant.id,
            ServerOperation.status == ServerOpStatus.pending_review,
        )
        .order_by(desc(ServerOperation.created_at))
    )
    return [ServerOperationRead.model_validate(op) for op in result.scalars().all()]


@router.get("/pending/count")
async def pending_count(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    from app.models.user_tenant_role import TenantRole
    if ctx.role == TenantRole.readonly:
        return {"count": 0}
    result = await db.execute(
        select(ServerOperation)
        .where(
            ServerOperation.tenant_id == ctx.tenant.id,
            ServerOperation.status == ServerOpStatus.pending_review,
        )
    )
    return {"count": len(result.scalars().all())}


@router.get("/history", response_model=list[ServerOperationRead])
async def list_history(
    ctx:   Annotated[TenantContext, Depends(require_reviewer)],
    db:    Annotated[AsyncSession, Depends(get_db)],
    limit: int = 100,
) -> list[ServerOperationRead]:
    result = await db.execute(
        select(ServerOperation)
        .where(
            ServerOperation.tenant_id == ctx.tenant.id,
            ServerOperation.status.in_([
                ServerOpStatus.completed,
                ServerOpStatus.failed,
                ServerOpStatus.rejected,
            ]),
        )
        .order_by(desc(ServerOperation.created_at))
        .limit(limit)
    )
    return [ServerOperationRead.model_validate(op) for op in result.scalars().all()]


@router.post("/{op_id}/review")
async def review_server_operation(
    op_id: UUID,
    body:  ReviewRequest,
    ctx:   Annotated[TenantContext, Depends(require_reviewer)],
    db:    Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(
        select(ServerOperation).where(
            ServerOperation.id == op_id,
            ServerOperation.tenant_id == ctx.tenant.id,
        )
    )
    op = result.scalar_one_or_none()
    if not op:
        raise HTTPException(status_code=404, detail="Operação não encontrada")
    if op.status != ServerOpStatus.pending_review:
        raise HTTPException(status_code=400, detail="Operação não está em revisão")

    op.reviewer_id = ctx.user.id
    op.reviewed_at = datetime.now(timezone.utc)
    op.review_comment = body.comment or None

    if not body.approved:
        op.status = ServerOpStatus.rejected
        await db.flush()
        return {"approved": False, "status": "rejected", "message": "Operação rejeitada."}

    # Approved → execute now
    srv_result = await db.execute(
        select(Server).where(Server.id == op.server_id)
    )
    server = srv_result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Servidor não encontrado")

    op.status = ServerOpStatus.executing
    await db.flush()

    from app.api.servers import _build_connector
    connector = await _build_connector(server)
    output, success = await connector.run_commands(list(op.commands))

    op.output = output
    op.status = ServerOpStatus.completed if success else ServerOpStatus.failed
    if not success:
        op.error_message = "Execução com erros — verifique o output."

    await db.flush()
    return {
        "approved": True,
        "status": op.status.value,
        "message": "Operação executada." if success else "Execução falhou.",
    }
