from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.device import Device
from app.models.operation import Operation, OperationStatus
from app.models.user_tenant_role import TenantRole
from app.schemas.operation import ChatMessage, OperationCreate, OperationRead
from app.services.device_service import DeviceNotFoundError, get_device
from app.services.operation_service import (
    OperationNotFoundError,
    execute_operation,
    start_or_continue_operation,
)

router = APIRouter()


async def _chat_response(
    db: AsyncSession, ctx: TenantContext, operation: Operation, agent_response: str
) -> dict:
    ready = operation.status.value == "approved"
    requires_approval = False
    if ready and operation.intent:
        from app.services.audit_service import check_requires_approval
        requires_approval = await check_requires_approval(db, ctx.user, operation.intent)
    return {
        "operation_id": str(operation.id),
        "status": operation.status.value,
        "agent_message": agent_response,
        "ready_to_execute": ready,
        "requires_approval": requires_approval,
        "intent": operation.intent,
    }


async def _get_tenant_operation(db: AsyncSession, operation_id: UUID, tenant_id: UUID) -> Operation:
    result = await db.execute(
        select(Operation)
        .join(Device, Operation.device_id == Device.id)
        .where(Operation.id == operation_id, Device.tenant_id == tenant_id)
    )
    op = result.scalar_one_or_none()
    if not op:
        raise HTTPException(status_code=404, detail="Operação não encontrada")
    return op


@router.post("", response_model=dict, status_code=200)
async def chat_with_agent(
    data: OperationCreate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    # Validate device belongs to tenant
    try:
        await get_device(db, data.device_id, tenant_id=ctx.tenant.id)
    except DeviceNotFoundError:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")

    from app.services.variable_service import resolve_and_substitute
    resolved_input, _vars, _unresolved = await resolve_and_substitute(
        db, data.device_id, ctx.tenant.id, data.natural_language_input
    )

    operation, agent_response = await start_or_continue_operation(
        db=db,
        user_id=ctx.user.id,
        operation_id=None,
        device_id=data.device_id,
        user_message=resolved_input,
        parent_operation_id=data.parent_operation_id,
    )
    return await _chat_response(db, ctx, operation, agent_response)


@router.post("/{operation_id}/chat", response_model=dict)
async def continue_chat(
    operation_id: UUID,
    message: ChatMessage,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    operation = await _get_tenant_operation(db, operation_id, ctx.tenant.id)

    _, agent_response = await start_or_continue_operation(
        db=db,
        user_id=ctx.user.id,
        operation_id=operation_id,
        device_id=operation.device_id,
        user_message=message.content,
    )

    result2 = await db.execute(select(Operation).where(Operation.id == operation_id))
    updated_op = result2.scalar_one()
    return await _chat_response(db, ctx, updated_op, agent_response)


@router.post("/{operation_id}/execute", response_model=OperationRead)
async def execute_op(
    operation_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> OperationRead:
    operation = await _get_tenant_operation(db, operation_id, ctx.tenant.id)

    if ctx.role == TenantRole.analyst and operation.intent:
        from app.services.audit_service import check_requires_approval
        if await check_requires_approval(db, ctx.user, operation.intent):
            raise HTTPException(
                status_code=403,
                detail="Esta operação requer aprovação N2. Use 'Enviar para Revisão'.",
            )

    mark_direct = ctx.role == TenantRole.analyst
    try:
        operation = await execute_operation(db, operation_id, mark_direct=mark_direct)
    except OperationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    try:
        from app.workers.generate_documents import generate
        generate.delay(str(operation_id))
    except Exception:
        pass

    return OperationRead.model_validate(operation)


@router.post("/{operation_id}/submit-review", response_model=OperationRead)
async def submit_for_review(
    operation_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> OperationRead:
    await _get_tenant_operation(db, operation_id, ctx.tenant.id)
    from app.services.audit_service import submit_for_review as _submit
    try:
        operation = await _submit(db, operation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return OperationRead.model_validate(operation)


@router.get("", response_model=list[OperationRead])
async def list_operations(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[OperationRead]:
    result = await db.execute(
        select(Operation)
        .join(Device, Operation.device_id == Device.id)
        .where(Device.tenant_id == ctx.tenant.id)
        .order_by(Operation.created_at.desc())
        .limit(100)
    )
    ops = list(result.scalars().all())
    return [OperationRead.model_validate(o) for o in ops]


@router.get("/{operation_id}", response_model=OperationRead)
async def get_operation(
    operation_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> OperationRead:
    op = await _get_tenant_operation(db, operation_id, ctx.tenant.id)
    return OperationRead.model_validate(op)


class DirectSSHCreate(BaseModel):
    device_id: UUID
    description: str
    ssh_commands: list[str]
    parent_operation_id: UUID | None = None
    template_slug: str | None = None
    template_params: dict | None = None


@router.post("/direct-ssh", response_model=OperationRead)
async def create_direct_ssh_operation(
    data: DirectSSHCreate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> OperationRead:
    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão para criar operações.")
    if not data.ssh_commands:
        raise HTTPException(status_code=400, detail="Nenhum comando SSH fornecido.")

    try:
        await get_device(db, data.device_id, tenant_id=ctx.tenant.id)
    except DeviceNotFoundError:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado.")

    action_plan: dict = {
        "intent": "direct_ssh",
        "device_id": str(data.device_id),
        "steps": [],
        "execution_mode": "ssh",
        "ssh_commands": data.ssh_commands,
        "raw_intent_data": {"description": data.description},
    }
    if data.template_slug:
        action_plan["template_slug"] = data.template_slug
    if data.template_params:
        action_plan["template_params"] = data.template_params

    operation = Operation(
        user_id=ctx.user.id,
        device_id=data.device_id,
        natural_language_input=data.description,
        intent="direct_ssh",
        action_plan=action_plan,
        status=OperationStatus.approved,
        parent_operation_id=data.parent_operation_id,
    )
    db.add(operation)
    await db.commit()
    await db.refresh(operation)
    return OperationRead.model_validate(operation)


@router.get("/{operation_id}/tutorial")
async def get_tutorial(
    operation_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    op = await _get_tenant_operation(db, operation_id, ctx.tenant.id)

    if op.status not in (OperationStatus.completed, OperationStatus.failed):
        raise HTTPException(status_code=400, detail="Tutorial disponível apenas para operações concluídas.")

    if op.tutorial:
        return {"tutorial": op.tutorial}

    if not op.action_plan or not op.intent:
        raise HTTPException(status_code=400, detail="Plano de ação não disponível para gerar tutorial.")

    device_result = await db.execute(select(Device).where(Device.id == op.device_id))
    device = device_result.scalar_one_or_none()
    vendor = device.vendor.value if device else "sonicwall"

    from app.agent.tutorial_generator import generate_tutorial
    tutorial = await generate_tutorial(
        intent=op.intent,
        natural_language_input=op.natural_language_input,
        action_plan=op.action_plan,
        vendor=vendor,
    )
    op.tutorial = tutorial
    await db.commit()
    return {"tutorial": tutorial}
