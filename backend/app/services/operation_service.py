import dataclasses
import re
from datetime import datetime, timezone
from uuid import UUID

# ANSI escape sequence pattern (for cleaning SSH terminal output)
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')

_SERVICE_EXCLUSION_CONFIG: dict[str, dict] = {
    "gateway-antivirus": {
        "show_cmd": "show gateway-antivirus",
        # Exclusion group line is on page 2+ of the show output (after --MORE--) — detection
        # will usually fall back to default. The configure command is confirmed working.
        "pattern": re.compile(r"exclusion\s+group\s+(\S+)", re.IGNORECASE),
        "default_group": "fm-excl-gateway-av",
        "config_cmds": lambda g: ["gateway-antivirus", f"exclusion group {g}", "exit"],
    },
    "anti-spyware": {
        "show_cmd": "show anti-spyware",
        # show: "exclusion address-object group GRP-EXCLUSION-SPYWARE"
        "pattern": re.compile(r"exclusion\s+address-object\s+group\s+(\S+)", re.IGNORECASE),
        "default_group": "fm-excl-anti-spyware",
        "config_cmds": lambda g: ["anti-spyware", f"exclusion address-object group {g}", "exit"],
    },
    "intrusion-prevention": {
        "show_cmd": "show intrusion-prevention",
        # show: "exclusion group GRP-EXCLUSION-IPS"
        "pattern": re.compile(r"exclusion\s+group\s+(\S+)", re.IGNORECASE),
        "default_group": "fm-excl-ips",
        "config_cmds": lambda g: ["intrusion-prevention", f"exclusion group {g}", "exit"],
    },
    "app-control": {
        "show_cmd": "show app-control",
        # show: "exclusion list object group GRP-EXCLUSION-APP-CONTROL"
        "pattern": re.compile(r"exclusion\s+list\s+object\s+group\s+(\S+)", re.IGNORECASE),
        "default_group": "fm-excl-app-control",
        "config_cmds": lambda g: ["app-control", f"exclusion list object group {g}", "exit"],
    },
    "geo-ip": {
        "show_cmd": "show geo-ip",
        # show: "exclude group GRP-EXCLUSION-GEO-IP"
        "pattern": re.compile(r"exclude\s+group\s+(\S+)", re.IGNORECASE),
        "default_group": "GRP-EXCLUSION-GEO-IP",
        "config_cmds": lambda g: ["geo-ip", f"exclude group {g}", "exit"],
    },
    "botnet": {
        "show_cmd": "show botnet",
        # Exclusion group info is on page 2+ (cut by pager). Show pattern left for future use.
        "pattern": re.compile(r"exclude\s+group\s+(\S+)", re.IGNORECASE),
        "default_group": "GRP-EXCLUSION-BOOTNET",
        # Both "block connections exclude group" and "exclude group" fail on this device —
        # adding the IP to the address-group is sufficient when the group is already
        # configured as botnet exclusion in the device. No service config cmd needed.
        "config_cmds": lambda g: [],
    },
    "dpi-ssl-client": {
        "show_cmd": "show dpi-ssl client",
        # show: "exclude address group <name>" (bypass/exclusion list, not the include list)
        "pattern": re.compile(r"exclude\s+address\s+group\s+(\S+)", re.IGNORECASE),
        "default_group": "fm-excl-dpi-ssl-client",
        "config_cmds": lambda g: ["dpi-ssl client", f"exclude address group {g}", "exit"],
    },
    "dpi-ssl-server": {
        "show_cmd": "show dpi-ssl server",
        "pattern": re.compile(r"exclude\s+address\s+group\s+(\S+)", re.IGNORECASE),
        "default_group": "fm-excl-dpi-ssl-server",
        "config_cmds": lambda g: ["dpi-ssl server", f"exclude address group {g}", "exit"],
    },
    "dpi-ssl": {
        "show_cmd": "show dpi-ssl client",
        "pattern": re.compile(r"exclude\s+address\s+group\s+(\S+)", re.IGNORECASE),
        "default_group": "fm-excl-dpi-ssl",
        "config_cmds": lambda g: ["dpi-ssl client", f"exclude address group {g}", "exit", "dpi-ssl server", f"exclude address group {g}", "exit"],
    },
}


def _build_service_exclusion_commands(
    ip_addresses: list[str],
    group_name: str,
    config_cmds: list[str],
    zone: str = "LAN",
) -> list[str]:
    """Build SSH commands to add IPs to an address group and link it to a service."""
    cmds: list[str] = []
    for ip in ip_addresses:
        obj_name = "fm-excl-" + ip.replace(".", "-")
        cmds += [f"address-object ipv4 {obj_name}", f"name {obj_name}", f"zone {zone}", f"host {ip}", "exit"]
    cmds.append(f"address-group ipv4 {group_name}")
    for ip in ip_addresses:
        cmds.append("address-object ipv4 " + "fm-excl-" + ip.replace(".", "-"))
    cmds.append("exit")
    cmds.extend(config_cmds)
    cmds.append("commit")
    return cmds


_SECURITY_SERVICE_LABELS: dict[str, str] = {
    "show gateway-antivirus":    "Gateway Anti-Virus",
    "show anti-spyware":         "Anti-Spyware",
    "show intrusion-prevention": "Intrusion Prevention (IPS)",
    "show app-control":          "App Control",
    "show geo-ip":               "Geo-IP Filter",
    "show botnet":               "Botnet Filter",
    "show dpi-ssl":              "DPI-SSL",
    "show dpi-ssl client":       "DPI-SSL (Client)",
    "show dpi-ssl server":       "DPI-SSL (Server)",
}


def _detect_service_enabled(cmd: str, section: str) -> bool | None:
    if "geo-ip" in cmd or "botnet" in cmd:
        if re.search(r'no\s+block\s+connections', section):
            return False
        if re.search(r'block\s+connections', section):
            return True
        return None
    no_m = re.search(r'^\s+no\s+enable\b', section, re.MULTILINE)
    yes_m = re.search(r'^\s+enable\b', section, re.MULTILINE)
    if no_m and yes_m:
        return yes_m.start() < no_m.start()
    if yes_m:
        return True
    if no_m:
        return False
    return None


def _parse_security_status(commands: list[str], raw_output: str) -> list[dict]:
    """Parse concatenated SSH show output into structured service status list."""
    clean = _ANSI_RE.sub('', raw_output).replace('\r', '')
    services = []
    for cmd in commands:
        label = _SECURITY_SERVICE_LABELS.get(cmd, cmd)
        start = clean.find(cmd)
        if start == -1:
            services.append({"service": label, "enabled": None})
            continue
        end = len(clean)
        for other_cmd in commands:
            if other_cmd == cmd:
                continue
            pos = clean.find(other_cmd, start + len(cmd))
            if 0 < pos < end:
                end = pos
        section = clean[start:end]
        services.append({"service": label, "enabled": _detect_service_enabled(cmd, section)})
    return services

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.agent import AgentSession
from app.agent.guardrails import GuardrailResult, check_action_plan, check_ssh_commands
from app.connectors.base import RuleSpec
from app.connectors.factory import CLI_VENDORS, get_connector, get_ssh_connector
from app.models.operation import Operation, OperationRisk, OperationStatus, classify_risk
from app.models.operation_step import OperationStep, StepStatus
from app.models.snapshot import Snapshot
from app.policy_engine.schemas import IntentType
from app.policy_engine.translator import translate_to_connector_spec
from app.policy_engine.validator import validate_action_plan
from app.services.bookstack_service import append_changelog, fetch_bookstack_context
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
    db: AsyncSession, user_id: UUID, operation_id: UUID | None, device_id: UUID, user_message: str,
    parent_operation_id: UUID | None = None,
) -> tuple[Operation, str]:
    device = await get_device(db, device_id)

    if operation_id is None:
        operation = Operation(
            user_id=user_id,
            device_id=device_id,
            natural_language_input=user_message,
            status=OperationStatus.pending,
            parent_operation_id=parent_operation_id,
        )
        db.add(operation)
        await db.flush()
        await db.refresh(operation)
        bookstack_context = await fetch_bookstack_context(db, device, query=user_message)
        session = AgentSession(device, bookstack_context=bookstack_context)
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
        intent_value = session.plan.intent.value
        operation.intent = intent_value
        operation.action_plan = session.plan.model_dump(mode="json")
        operation.status = OperationStatus.approved

        # Classify risk and set required approvals based on intent
        risk, req_approvals = classify_risk(intent_value)
        operation.risk_level = risk
        operation.required_approvals = req_approvals

        # Run guardrails on the generated plan
        guardrail_result = check_action_plan(
            operation.action_plan, user_message
        )
        if guardrail_result.blocked:
            operation.status = OperationStatus.failed
            operation.error_message = (
                f"[GUARDRAIL BLOCK] {guardrail_result.block_reason}"
            )
        elif guardrail_result.warnings:
            # Escalate critical intents detected by guardrails to require 2 approvals
            if risk != OperationRisk.critical:
                operation.required_approvals = max(req_approvals, 1)
            # Append warnings to action plan for display in UI
            if operation.action_plan:
                operation.action_plan = {
                    **operation.action_plan,
                    "_guardrail_warnings": guardrail_result.warnings,
                }

    await db.flush()
    await db.refresh(operation)
    return operation, response


async def execute_operation(db: AsyncSession, operation_id: UUID, mark_direct: bool = False) -> Operation:
    result = await db.execute(select(Operation).where(Operation.id == operation_id))
    operation = result.scalar_one_or_none()
    if not operation:
        raise OperationNotFoundError()

    if mark_direct:
        operation.executed_direct = True

    if not operation.action_plan:
        raise ValueError("Operation has no action plan")

    device = await get_device(db, operation.device_id)

    from app.policy_engine.schemas import ActionPlan
    plan = ActionPlan.model_validate(operation.action_plan)

    # ── CLI-only vendors: all execution goes through SSH ──────────────────────
    if device.vendor in CLI_VENDORS:
        ssh_show_cmds = plan.ssh_show_commands or []
        ssh_config_cmds = plan.ssh_commands or []

        # Show/read operations (list_vlans, list_ports, get_info — no config mode)
        if ssh_show_cmds:
            operation.status = OperationStatus.executing
            await db.flush()
            try:
                ssh_connector = get_ssh_connector(device)
                ssh_result = await ssh_connector.execute_show_commands(ssh_show_cmds)
                operation.action_plan = {
                    **(operation.action_plan or {}),
                    "result": {
                        "commands": ssh_show_cmds,
                        "output": ssh_result.output,
                    },
                }
                operation.status = OperationStatus.completed if ssh_result.success else OperationStatus.failed
                if not ssh_result.success:
                    operation.error_message = ssh_result.error
            except Exception as exc:
                operation.status = OperationStatus.failed
                operation.error_message = str(exc)
            await db.flush()
            await db.refresh(operation)
            return operation

        # Config/write operations
        if not ssh_config_cmds:
            operation.status = OperationStatus.failed
            operation.error_message = (
                f"Nenhum comando SSH foi gerado para o vendor '{device.vendor.value}'. "
                "Verifique o plano de ação ou use o Modo Técnico para inserir comandos manualmente."
            )
            await db.flush()
            await db.refresh(operation)
            return operation

        operation.status = OperationStatus.executing
        await db.flush()
        try:
            ssh_connector = get_ssh_connector(device)
            ssh_result = await ssh_connector.execute_commands(ssh_config_cmds)
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
        except Exception as exc:
            operation.status = OperationStatus.failed
            operation.error_message = str(exc)
        await db.flush()
        await db.refresh(operation)
        if operation.status == OperationStatus.completed:
            await append_changelog(db, device, operation)
        return operation
    # ── REST-API vendors (existing routing below) ─────────────────────────────

    connector = get_connector(device)

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
        elif plan.intent == IntentType.get_security_status:
            ssh_commands = plan.ssh_commands or [
                "show gateway-antivirus",
                "show anti-spyware",
                "show intrusion-prevention",
                "show app-control",
                "show geo-ip",
                "show botnet",
                "show dpi-ssl",
            ]
            ssh_connector = get_ssh_connector(device)
            ssh_result = await ssh_connector.execute_show_commands(ssh_commands)
            services = _parse_security_status(ssh_commands, ssh_result.output)
            operation.action_plan = {
                **(operation.action_plan or {}),
                "result": services,
            }
            if ssh_result.success:
                operation.status = OperationStatus.completed
            else:
                operation.status = OperationStatus.failed
                operation.error_message = ssh_result.error

        elif plan.intent == IntentType.add_security_exclusion:
            spec = plan.security_exclusion_spec
            if not spec or not spec.ip_addresses:
                raise ValueError("security_exclusion_spec com ip_addresses é obrigatório")
            services = spec.services or list(_SERVICE_EXCLUSION_CONFIG.keys())
            ssh_connector = get_ssh_connector(device)
            results = []
            all_success = True
            for svc_key in services:
                svc_config = _SERVICE_EXCLUSION_CONFIG.get(svc_key)
                if not svc_config:
                    results.append({"service": svc_key, "group": "", "ips": spec.ip_addresses, "success": False, "error": f"Serviço '{svc_key}' não reconhecido"})
                    all_success = False
                    continue
                group_name = spec.group if spec.group else svc_config["default_group"]
                show_result = await ssh_connector.execute_show_commands([svc_config["show_cmd"]])
                detected_group = False
                show_tail = ""
                if show_result.success:
                    clean_show = _ANSI_RE.sub('', show_result.output).replace('\r', '')
                    show_tail = clean_show[-600:]
                    m = svc_config["pattern"].search(clean_show)
                    if m:
                        group_name = m.group(1)
                        detected_group = True
                print(f"[EXCL-SHOW] {svc_key}: detected_group={detected_group} group={group_name!r} tail={show_tail!r}", flush=True)
                config_cmds = svc_config["config_cmds"](group_name)
                cmds = _build_service_exclusion_commands(spec.ip_addresses, group_name, config_cmds, spec.zone)
                print(f"[EXCL-CMDS] {svc_key}: {cmds}", flush=True)
                exec_result = await ssh_connector.execute_commands(cmds) if cmds else None
                exec_tail = (exec_result.output if exec_result else "") or ""
                exec_tail = exec_tail[-500:]
                # Detect SonicWall CLI errors that don't raise Python exceptions
                cli_error = None
                if exec_result and exec_result.success and "No matching command found" in (exec_result.output or ""):
                    cli_error = "SonicWall: No matching command found — check CLI syntax"
                svc_success = (exec_result.success if exec_result else True) and not cli_error
                print(f"[EXCL-RESULT] {svc_key}: success={svc_success} cli_error={cli_error!r} tail={exec_tail!r}", flush=True)
                results.append({"service": svc_key, "group": group_name, "detected": detected_group, "ips": spec.ip_addresses, "success": svc_success, "error": cli_error or (exec_result.error if exec_result else None)})
                if not exec_result.success:
                    all_success = False
            operation.action_plan = {**(operation.action_plan or {}), "result": results}
            if all_success:
                operation.status = OperationStatus.completed
            else:
                operation.status = OperationStatus.failed
                failed = [r["service"] for r in results if not r["success"]]
                operation.error_message = f"Falha na exclusão dos serviços: {', '.join(failed)}"

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
            IntentType.direct_ssh,
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

    if operation.status == OperationStatus.completed:
        await append_changelog(db, device, operation)

    return operation
