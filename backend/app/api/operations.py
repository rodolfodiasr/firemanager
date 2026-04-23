from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models.operation import Operation
from app.models.user import User
from app.schemas.operation import ChatMessage, OperationCreate, OperationRead
from app.services.operation_service import (
    OperationNotFoundError,
    execute_operation,
    start_or_continue_operation,
)

router = APIRouter()


@router.post("", response_model=dict, status_code=200)
async def chat_with_agent(
    data: OperationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Start or continue a conversation with the AI agent for a new operation."""
    operation, agent_response = await start_or_continue_operation(
        db=db,
        user_id=current_user.id,
        operation_id=None,
        device_id=data.device_id,
        user_message=data.natural_language_input,
    )
    return {
        "operation_id": str(operation.id),
        "status": operation.status.value,
        "agent_message": agent_response,
        "ready_to_execute": operation.status.value == "approved",
    }


@router.post("/{operation_id}/chat", response_model=dict)
async def continue_chat(
    operation_id: UUID,
    message: ChatMessage,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Continue an ongoing agent conversation."""
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

    return {
        "operation_id": str(operation_id),
        "status": updated_op.status.value,
        "agent_message": agent_response,
        "ready_to_execute": updated_op.status.value == "approved",
    }


@router.post("/{operation_id}/execute", response_model=OperationRead)
async def execute_op(
    operation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OperationRead:
    """Execute an approved operation on the target device."""
    try:
        operation = await execute_operation(db, operation_id)
    except OperationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Trigger async document generation
    from app.workers.generate_documents import generate
    generate.delay(str(operation_id))

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
