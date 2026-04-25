import dataclasses
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.agent import AgentSession
from app.connectors.base import RuleSpec
from app.connectors.factory import get_connector, get_ssh_connector
from app.models.operation import Operation, OperationStatus
from app.models.operation_step import OperationStep, StepStatus
from app.models.snapshot import Snapshot
from app.policy_engine.schemas import IntentType
from app.policy_engine.translator import translate_to_connector_spec
from app.policy_engine.validator import validate_action_plan
from app.services.device_service import get_device
from app.utils.integrity import compute_record_hash

import hashlib

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


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
            filter_object = plan.raw_intent_data.get("filter_object")
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
            if filter_object:
                obj_lower = filter_object.lower()
                rules = [
                    r for r in rules
                    if obj_lower in r.src.lower() or obj_lower in r.dst.lower() or obj_lower in r.service.lower()
                ]
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
            if rule_id and not _UUID_RE.match(str(rule_id)):
                # rule_id is a name — resolve to UUID and fill missing fields from current rule
                all_rules = await connector.list_rules()
                matched = next((r for r in all_rules if r.name.lower() == str(rule_id).lower()), None)
                if matched:
                    rule_id = matched.rule_id
                    rule_spec = dataclasses.replace(
                        rule_spec,
                        src_address=rule_spec.src_address if rule_spec.src_address not in ("", "Any") else matched.src,
                        dst_address=rule_spec.dst_address if rule_spec.dst_address not in ("", "Any") else matched.dst,
                        service=rule_spec.service if rule_spec.service not in ("", "Any") else matched.service,
                        src_zone=rule_spec.src_zone if rule_spec.src_zone not in ("", "LAN") else matched.raw.get("from", "LAN"),
                        dst_zone=rule_spec.dst_zone if rule_spec.dst_zone not in ("", "WAN") else matched.raw.get("to", "WAN"),
                        action=rule_spec.action if rule_spec.action not in ("", "accept") else matched.action,
                    )
                else:
                    raise ValueError(f"Regra '{rule_id}' não encontrada")
            exec_result = await connector.edit_rule(str(rule_id), rule_spec)
        elif plan.intent == IntentType.create_group and group_spec:
            exec_result = await connector.create_group(group_spec)
        elif plan.intent == IntentType.list_nat_policies:
            policies = await connector.list_nat_policies()
            filter_object = plan.raw_intent_data.get("filter_object")
            filter_inbound = plan.raw_intent_data.get("filter_inbound")
            filter_outbound = plan.raw_intent_data.get("filter_outbound")
            filter_enabled = plan.raw_intent_data.get("filter_enabled")
            if filter_object:
                obj_lower = filter_object.lower()
                policies = [
                    p for p in policies
                    if obj_lower in p.source.lower()
                    or obj_lower in p.translated_source.lower()
                    or obj_lower in p.destination.lower()
                    or obj_lower in p.translated_destination.lower()
                    or obj_lower in p.service.lower()
                    or obj_lower in p.translated_service.lower()
                ]
            if filter_inbound:
                policies = [p for p in policies if p.inbound.upper() == filter_inbound.upper()]
            if filter_outbound:
                policies = [p for p in policies if p.outbound.upper() == filter_outbound.upper()]
            if filter_enabled is not None:
                policies = [p for p in policies if p.enabled == bool(filter_enabled)]
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
            filter_object = plan.raw_intent_data.get("filter_object")
            filter_interface = plan.raw_intent_data.get("filter_interface")
            filter_type = plan.raw_intent_data.get("filter_type")
            if filter_object:
                obj_lower = filter_object.lower()
                routes = [
                    r for r in routes
                    if obj_lower in r.source.lower()
                    or obj_lower in r.destination.lower()
                    or obj_lower in r.gateway.lower()
                ]
            if filter_interface:
                routes = [r for r in routes if r.interface.upper() == filter_interface.upper()]
            if filter_type:
                routes = [r for r in routes if r.route_type.lower() == filter_type.lower()]
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
        elif plan.intent in (
            IntentType.configure_content_filter,
            IntentType.toggle_gateway_av,
            IntentType.toggle_anti_spyware,
            IntentType.toggle_ips,
            IntentType.toggle_app_control,
            IntentType.toggle_geo_ip,
            IntentType.toggle_botnet,
            IntentType.toggle_dpi_ssl,
            IntentType.configure_app_rules,
            IntentType.add_security_exclusion,
        ):
            ssh_commands = plan.ssh_commands or []
            if not ssh_commands:
                raise ValueError(f"Nenhum comando SSH foi gerado pelo agente para {plan.intent.value}")
            ssh_connector = get_ssh_connector(device)
            ssh_result = await ssh_connector.execute_commands(ssh_commands)
            operation.action_plan = {
                **(operation.action_plan or {}),
                "result": {
                    "commands": ssh_result.commands_executed,
                    "output": ssh_result.output,
                },
            }
            if ssh_result.success:
                operation.status = OperationStatus.completed
            else:
                operation.status = OperationStatus.failed
                operation.error_message = ssh_result.error

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
