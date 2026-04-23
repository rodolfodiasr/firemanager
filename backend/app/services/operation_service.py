from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.agent import AgentSession
from app.connectors.factory import get_connector
from app.models.operation import Operation, OperationStatus
from app.models.operation_step import OperationStep, StepStatus
from app.models.snapshot import Snapshot
from app.policy_engine.schemas import IntentType
from app.policy_engine.translator import translate_to_connector_spec
from app.policy_engine.validator import validate_action_plan
from app.services.device_service import get_device
from app.utils.integrity import compute_record_hash

import hashlib


class OperationNotFoundError(Exception):
    status_code = 404
    default_message = "Operação não encontrada"


# In-memory sessions (for simplicity — in production use Redis)
_sessions: dict[UUID, AgentSession] = {}


async def start_or_continue_operation(
    db: AsyncSession, user_id: UUID, operation_id: UUID | None, device_id: UUID, user_message: str
) -> tuple[Operation, str]:
    device = await get_device(db, device_id)

    if operation_id is None:
        operation = Operation(
            user_id=user_id,
            device_id=device_id,
            natural_language_input=user_message,
            status=OperationStatus.pending,
        )
        db.add(operation)
        await db.flush()
        session = AgentSession(device)
        _sessions[operation.id] = session
    else:
        result = await db.execute(select(Operation).where(Operation.id == operation_id))
        operation = result.scalar_one_or_none()
        if not operation:
            raise OperationNotFoundError()
        session = _sessions.get(operation.id)
        if not session:
            session = AgentSession(device)
            _sessions[operation.id] = session

    response = await session.process(user_message)

    if session.ready_to_execute and session.plan:
        operation.intent = session.plan.intent.value
        operation.action_plan = session.plan.model_dump(mode="json")
        operation.status = OperationStatus.approved

    await db.flush()
    return operation, response


async def execute_operation(db: AsyncSession, operation_id: UUID) -> Operation:
    result = await db.execute(select(Operation).where(Operation.id == operation_id))
    operation = result.scalar_one_or_none()
    if not operation:
        raise OperationNotFoundError()

    if not operation.action_plan:
        raise ValueError("Operation has no action plan")

    device = await get_device(db, operation.device_id)
    connector = get_connector(device)

    from app.policy_engine.schemas import ActionPlan
    plan = ActionPlan.model_validate(operation.action_plan)

    try:
        validate_action_plan(plan)
    except Exception as exc:
        operation.status = OperationStatus.failed
        operation.error_message = str(exc)
        await db.flush()
        return operation

    rule_spec, group_spec = translate_to_connector_spec(plan, device)
    operation.status = OperationStatus.executing
    await db.flush()

    exec_result = None
    try:
        if plan.intent == IntentType.create_rule and rule_spec:
            exec_result = await connector.create_rule(rule_spec)
        elif plan.intent == IntentType.delete_rule:
            rule_id = plan.raw_intent_data.get("rule_id", "")
            exec_result = await connector.delete_rule(str(rule_id))
        elif plan.intent == IntentType.edit_rule and rule_spec:
            rule_id = plan.raw_intent_data.get("rule_id", "")
            exec_result = await connector.edit_rule(str(rule_id), rule_spec)
        elif plan.intent == IntentType.create_group and group_spec:
            exec_result = await connector.create_group(group_spec)

        if exec_result and exec_result.success:
            operation.status = OperationStatus.completed
            # Save config snapshot
            try:
                config_data = await connector.get_config_snapshot()
                snap = Snapshot(
                    device_id=device.id,
                    operation_id=operation.id,
                    config_data=config_data,
                    config_hash=hashlib.sha256(config_data.encode()).hexdigest(),
                    label=f"After operation {operation.id}",
                )
                db.add(snap)
            except Exception:
                pass  # snapshot failure is non-critical
        else:
            operation.status = OperationStatus.failed
            operation.error_message = exec_result.error if exec_result else "Unknown error"

    except Exception as exc:
        operation.status = OperationStatus.failed
        operation.error_message = str(exc)

    await db.flush()
    return operation
