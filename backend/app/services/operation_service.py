import dataclasses
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
        await db.refresh(operation)
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
    await db.refresh(operation)
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
        await db.refresh(operation)
        return operation

    rule_spec, group_spec, nat_spec, route_spec = translate_to_connector_spec(plan, device)
    operation.status = OperationStatus.executing
    await db.flush()
    await db.refresh(operation)

    exec_result = None
    try:
        if plan.intent == IntentType.list_rules:
            rules = await connector.list_rules()
            src_zone = plan.raw_intent_data.get("src_zone")
            dst_zone = plan.raw_intent_data.get("dst_zone")
            filter_any = plan.raw_intent_data.get("filter_any", False)
            filter_action = plan.raw_intent_data.get("filter_action")
            filter_enabled = plan.raw_intent_data.get("filter_enabled")
            if src_zone:
                rules = [r for r in rules if r.raw.get("from", "").upper() == src_zone.upper()]
            if dst_zone:
                rules = [r for r in rules if r.raw.get("to", "").upper() == dst_zone.upper()]
            if filter_any:
                rules = [r for r in rules if r.src.lower() == "any" or r.dst.lower() == "any"]
            if filter_action:
                rules = [r for r in rules if r.action.lower() == filter_action.lower()]
            if filter_enabled is not None:
                rules = [r for r in rules if r.enabled == bool(filter_enabled)]
            operation.action_plan = {
                **(operation.action_plan or {}),
                "result": [dataclasses.asdict(r) for r in rules],
            }
            operation.status = OperationStatus.completed
        elif plan.intent == IntentType.create_rule and rule_spec:
            exec_result = await connector.create_rule(rule_spec)
        elif plan.intent == IntentType.delete_rule:
            rule_id = plan.raw_intent_data.get("rule_id", "")
            exec_result = await connector.delete_rule(str(rule_id))
        elif plan.intent == IntentType.edit_rule and rule_spec:
            rule_id = plan.raw_intent_data.get("rule_id", "")
            exec_result = await connector.edit_rule(str(rule_id), rule_spec)
        elif plan.intent == IntentType.create_group and group_spec:
            exec_result = await connector.create_group(group_spec)
        elif plan.intent == IntentType.list_nat_policies:
            policies = await connector.list_nat_policies()
            operation.action_plan = {
                **(operation.action_plan or {}),
                "result": [dataclasses.asdict(p) for p in policies],
            }
            operation.status = OperationStatus.completed
        elif plan.intent == IntentType.create_nat_policy and nat_spec:
            exec_result = await connector.create_nat_policy(nat_spec)
        elif plan.intent == IntentType.delete_nat_policy:
            rule_id = plan.raw_intent_data.get("rule_id", "")
            exec_result = await connector.delete_nat_policy(str(rule_id))
        elif plan.intent == IntentType.list_route_policies:
            routes = await connector.list_route_policies()
            operation.action_plan = {
                **(operation.action_plan or {}),
                "result": [dataclasses.asdict(r) for r in routes],
            }
            operation.status = OperationStatus.completed
        elif plan.intent == IntentType.create_route_policy and route_spec:
            exec_result = await connector.create_route_policy(route_spec)
        elif plan.intent == IntentType.delete_route_policy:
            rule_id = plan.raw_intent_data.get("rule_id", "")
            exec_result = await connector.delete_route_policy(str(rule_id))

        if exec_result is not None:
            if exec_result.success:
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
                operation.error_message = exec_result.error

    except Exception as exc:
        operation.status = OperationStatus.failed
        operation.error_message = str(exc)

    await db.flush()
    await db.refresh(operation)
    return operation
