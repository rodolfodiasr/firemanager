from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models.operation import Operation, OperationStatus
from app.models.user import User, UserRole
from app.schemas.operation import ChatMessage, OperationCreate, OperationRead
from app.services.operation_service import (
    OperationNotFoundError,
    execute_operation,
    start_or_continue_operation,
)

router = APIRouter()


async def _chat_response(db: AsyncSession, user: User, operation: Operation, agent_response: str) -> dict:
    """Build the unified chat response dict, including audit policy check."""
    ready = operation.status.value == "approved"
    requires_approval = False
    if ready and operation.intent:
        from app.services.audit_service import check_requires_approval
        requires_approval = await check_requires_approval(db, user, operation.intent)
    return {
        "operation_id": str(operation.id),
        "status": operation.status.value,
        "agent_message": agent_response,
        "ready_to_execute": ready,
        "requires_approval": requires_approval,
        "intent": operation.intent,
    }


@router.post("", response_model=dict, status_code=200)
async def chat_with_agent(
    data: OperationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    operation, agent_response = await start_or_continue_operation(
        db=db,
        user_id=current_user.id,
        operation_id=None,
        device_id=data.device_id,
        user_message=data.natural_language_input,
    )
    return await _chat_response(db, current_user, operation, agent_response)


@router.post("/{operation_id}/chat", response_model=dict)
async def continue_chat(
    operation_id: UUID,
    message: ChatMessage,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(select(Operation).where(Operation.id == operation_id))
    operation = result.scalar_one_or_none()
    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")

    _, agent_response = await start_or_continue_operation(
        db=db,
        user_id=current_user.id,
        operation_id=operation_id,
        device_id=operation.device_id,
        user_message=message.content,
    )

    result2 = await db.execute(select(Operation).where(Operation.id == operation_id))
    updated_op = result2.scalar_one()
    return await _chat_response(db, current_user, updated_op, agent_response)


@router.post("/{operation_id}/execute", response_model=OperationRead)
async def execute_op(
    operation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OperationRead:
    """Execute an approved operation. Operators are blocked if the intent requires N2 approval."""
    result = await db.execute(select(Operation).where(Operation.id == operation_id))
    operation = result.scalar_one_or_none()
    if not operation:
        raise HTTPException(status_code=404, detail="Operação não encontrada")

    # Enforce audit policy for operators
    if current_user.role == UserRole.operator and operation.intent:
        from app.services.audit_service import check_requires_approval
        if await check_requires_approval(db, current_user, operation.intent):
            raise HTTPException(
                status_code=403,
                detail="Esta operação requer aprovação N2. Use 'Enviar para Revisão'.",
            )

    mark_direct = current_user.role == UserRole.operator
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
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OperationRead:
    """Move an approved operation into the N2 review queue."""
    from app.services.audit_service import submit_for_review as _submit
    try:
        operation = await _submit(db, operation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return OperationRead.model_validate(operation)


@router.get("", response_model=list[OperationRead])
async def list_operations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[OperationRead]:
    result = await db.execute(
        select(Operation).order_by(Operation.created_at.desc()).limit(100)
    )
    ops = list(result.scalars().all())
    return [OperationRead.model_validate(o) for o in ops]


@router.get("/{operation_id}", response_model=OperationRead)
async def get_operation(
    operation_id: UUID,
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OperationRead:
    result = await db.execute(select(Operation).where(Operation.id == operation_id))
    op = result.scalar_one_or_none()
    if not op:
        raise HTTPException(status_code=404, detail="Operation not found")
    return OperationRead.model_validate(op)


@router.get("/{operation_id}/tutorial")
async def get_tutorial(
    operation_id: UUID,
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Return a step-by-step manual tutorial for an executed operation. Cached after first generation."""
    result = await db.execute(select(Operation).where(Operation.id == operation_id))
    op = result.scalar_one_or_none()
    if not op:
        raise HTTPException(status_code=404, detail="Operation not found")

    if op.status not in (OperationStatus.completed, OperationStatus.failed):
        raise HTTPException(status_code=400, detail="Tutorial disponível apenas para operações concluídas.")

    if op.tutorial:
        return {"tutorial": op.tutorial}

    if not op.action_plan or not op.intent:
        raise HTTPException(status_code=400, detail="Plano de ação não disponível para gerar tutorial.")

    from app.agent.tutorial_generator import generate_tutorial
    tutorial = await generate_tutorial(
        intent=op.intent,
        natural_language_input=op.natural_language_input,
        action_plan=op.action_plan,
    )

    op.tutorial = tutorial
    await db.commit()

    return {"tutorial": tutorial}
