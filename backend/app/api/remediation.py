from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.schemas.remediation import (
    CommandEdit,
    CommandReview,
    RemediationCommandRead,
    RemediationPlanRead,
    RemediationRequest,
    ReviewerComment,
)
from app.services import remediation_service

router = APIRouter()


@router.post("", response_model=RemediationPlanRead, status_code=201)
async def create_plan(
    data: RemediationRequest,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> RemediationPlanRead:
    try:
        plan = await remediation_service.generate_plan(
            db=db,
            tenant_id=ctx.tenant.id,
            server_id=data.server_id,
            request=data.request,
            session_id=data.session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar plano: {exc}")
    return RemediationPlanRead.model_validate(plan)


@router.get("", response_model=list[RemediationPlanRead])
async def list_plans(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[RemediationPlanRead]:
    plans = await remediation_service.list_plans(db, tenant_id=ctx.tenant.id)
    return [RemediationPlanRead.model_validate(p) for p in plans]


@router.get("/{plan_id}", response_model=RemediationPlanRead)
async def get_plan(
    plan_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> RemediationPlanRead:
    plan = await remediation_service.get_plan(db, tenant_id=ctx.tenant.id, plan_id=plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    return RemediationPlanRead.model_validate(plan)


@router.patch("/{plan_id}/commands/{command_id}", response_model=RemediationCommandRead)
async def update_command(
    plan_id: UUID,
    command_id: UUID,
    body: CommandEdit,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RemediationCommandRead:
    try:
        cmd = await remediation_service.update_command(
            db, ctx.tenant.id, plan_id, command_id,
            new_command=body.command,
            new_description=body.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RemediationCommandRead.model_validate(cmd)


@router.post("/{plan_id}/retry", response_model=RemediationPlanRead, status_code=201)
async def retry_plan(
    plan_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RemediationPlanRead:
    try:
        plan = await remediation_service.retry_plan(db, ctx.tenant.id, plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao retentar: {exc}")
    return RemediationPlanRead.model_validate(plan)


@router.post("/{plan_id}/commands/{command_id}/approve", response_model=dict)
async def approve_command(
    plan_id: UUID,
    command_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        cmd = await remediation_service.approve_command(db, ctx.tenant.id, plan_id, command_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"id": str(cmd.id), "status": cmd.status.value}


@router.post("/{plan_id}/commands/{command_id}/reject", response_model=dict)
async def reject_command(
    plan_id: UUID,
    command_id: UUID,
    body: CommandReview,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        cmd = await remediation_service.reject_command(
            db, ctx.tenant.id, plan_id, command_id, comment=body.comment
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"id": str(cmd.id), "status": cmd.status.value}


@router.post("/{plan_id}/execute", response_model=RemediationPlanRead)
async def execute_plan(
    plan_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> RemediationPlanRead:
    try:
        plan = await remediation_service.execute_plan(db, ctx.tenant.id, plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao executar: {exc}")
    return RemediationPlanRead.model_validate(plan)


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    plan = await remediation_service.get_plan(db, ctx.tenant.id, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    await db.delete(plan)
    await db.flush()
