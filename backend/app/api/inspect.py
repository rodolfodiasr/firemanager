import dataclasses
import logging
import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.connectors.factory import get_connector, get_ssh_connector
from app.database import get_db
from app.models.device import Device, VendorEnum
from app.services.device_service import DeviceNotFoundError, get_device

router = APIRouter()

_VALID_RESOURCES = ("rules", "nat", "routes", "security", "content_filter", "app_rules")

_SECURITY_COMMANDS = [
    "show gateway-antivirus",
    "show anti-spyware",
    "show intrusion-prevention",
    "show app-control",
    "show geo-ip",
    "show botnet",
    "show dpi-ssl",
]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _parse_sonicwall_ssh_rules(raw: str) -> list[dict]:
    """Parse SonicWall Gen6 configure-mode 'show access-rules' into structured rule dicts.

    Each rule block looks like:
        access-rule ipv4 from WAN to LAN action allow service name "X" destination ...
            uuid <uuid>
            name <name>   | no name
            enable        | no enable
            source address any | name "X" | group "X"
            service any   | name "X" | group X
            destination address any | name "X" | group "X"
            priority manual <n>
            comment "X"   | no comment
            exit
    """
    clean = _ANSI_RE.sub("", raw).replace("\r", "")
    rules: list[dict] = []

    blocks = re.split(r"(?=^access-rule\s+ipv4\s+from)", clean, flags=re.MULTILINE)
    for block in blocks:
        block = block.strip()
        if not block.startswith("access-rule"):
            continue

        header = re.match(r"access-rule\s+ipv4\s+from\s+(\S+)\s+to\s+(\S+)", block)
        if not header:
            continue
        from_zone, to_zone = header.group(1), header.group(2)

        def field(pattern: str, default: str = "") -> str:
            m = re.search(pattern, block, re.MULTILINE | re.IGNORECASE)
            return m.group(1).strip().strip('"') if m else default

        uuid = field(r"^\s+uuid\s+(\S+)")
        no_name = bool(re.search(r"^\s+no\s+name\b", block, re.MULTILINE))
        name = "" if no_name else field(r'^\s+name\s+"?([^"\n]+)"?')
        enabled = not bool(re.search(r"^\s+no\s+enable\b", block, re.MULTILINE))

        action_m = re.search(r"^\s+action\s+(allow|deny|discard)\b", block, re.MULTILINE)
        action = action_m.group(1) if action_m else "allow"

        src = "Any" if re.search(r"^\s+source\s+address\s+any\b", block, re.MULTILINE) \
            else field(r'^\s+source\s+address\s+(?:name|group)\s+"?([^"\n]+)"?', "Any")

        dst = "Any" if re.search(r"^\s+destination\s+address\s+any\b", block, re.MULTILINE) \
            else field(r'^\s+destination\s+address\s+(?:name|group)\s+"?([^"\n]+)"?', "Any")

        svc = "Any" if re.search(r"^\s+service\s+any\b", block, re.MULTILINE) \
            else field(r'^\s+service\s+(?:name|group)\s+"?([^"\n]+)"?', "Any")

        prio_m = re.search(r"^\s+priority\s+manual\s+(\d+)", block, re.MULTILINE)
        priority = int(prio_m.group(1)) if prio_m else 0

        no_comment = bool(re.search(r"^\s+no\s+comment\b", block, re.MULTILINE))
        comment = "" if no_comment else field(r'^\s+comment\s+"([^"]+)"')

        rules.append({
            "rule_id": uuid,
            "name": name or comment or f"Rule #{priority}",
            "src": src,
            "dst": dst,
            "service": svc,
            "action": action,
            "enabled": enabled,
            "src_zone": from_zone,
            "dst_zone": to_zone,
            "comment": comment,
            "priority": priority,
            "raw": {},
        })

    return rules


def _parse_sonicwall_security_section(raw: str) -> dict:
    """Parse one SonicWall security service configure sub-mode output into structured dict."""
    clean = _ANSI_RE.sub("", raw).replace("\r", "")

    no_m = re.search(r"^\s+no\s+enable\b", clean, re.MULTILINE)
    yes_m = re.search(r"^\s+enable\b", clean, re.MULTILINE)
    if no_m and yes_m:
        enabled: bool | None = yes_m.start() < no_m.start()
    elif yes_m:
        enabled = True
    elif no_m:
        enabled = False
    else:
        enabled = None

    protocols  = re.findall(r"^\s+protocol\s+(\S+)", clean, re.MULTILINE)
    prev_m     = re.search(r"^\s+prevention-group\s+(.+)", clean, re.MULTILINE)
    det_m      = re.search(r"^\s+detection-group\s+(.+)", clean, re.MULTILINE)
    excl_m     = re.search(r"^\s+exclusion\s+(?:address-object\s+)?group\s+(.+)", clean, re.MULTILINE)

    return {
        "enabled":          enabled,
        "protocols":        protocols or None,
        "prevention_group": prev_m.group(1).strip() if prev_m else None,
        "detection_group":  det_m.group(1).strip()  if det_m  else None,
        "exclusion_group":  excl_m.group(1).strip() if excl_m else None,
        "raw":              clean.strip(),
    }


def _parse_named_blocks(output: str, block_keywords: list[str]) -> list[dict]:
    """Generic SSH show parser — extracts named blocks delimited by '!'."""
    items: list[dict] = []
    clean = _ANSI_RE.sub("", output)
    pattern = re.compile(
        r"^(" + "|".join(re.escape(k) for k in block_keywords) + r')\s+"?([^"!\n]+?)"?\s*$',
        re.IGNORECASE,
    )
    current: dict | None = None

    for line in clean.splitlines():
        stripped = line.strip()
        m = pattern.match(stripped)
        if m:
            if current:
                items.append(current)
            current = {"type": m.group(1).capitalize(), "name": m.group(2).strip(), "_lines": []}
            continue
        if stripped == "!" and current:
            items.append(current)
            current = None
            continue
        if current and stripped:
            current["_lines"].append(stripped)

    if current:
        items.append(current)

    for item in items:
        item["details"] = "\n".join(item.pop("_lines"))

    return items


@router.get("/{device_id}/inspect")
async def inspect_device(
    device_id: UUID,
    resource: str = Query(...),
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = None,
    db:  Annotated[AsyncSession, Depends(get_db)] = None,
) -> dict:
    """Fetch live configuration data directly from the device, bypassing the LLM/operation flow."""
    if resource not in _VALID_RESOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"resource deve ser: {', '.join(_VALID_RESOURCES)}.",
        )

    try:
        device = await get_device(db, device_id, tenant_id=ctx.tenant.id)
    except DeviceNotFoundError:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado.")

    try:
        # ── SSH-based resources ───────────────────────────────────────────────
        if resource == "security":
            ssh = get_ssh_connector(device)

            if device.vendor == VendorEnum.sonicwall:
                from app.services.operation_service import _parse_security_status

                # 3 main services — via configure sub-mode (richer structured data)
                raw_data = await ssh.collect_security_services()
                _SW_LABELS = {
                    "gateway_antivirus":    "Gateway Anti-Virus",
                    "anti_spyware":         "Anti-Spyware",
                    "intrusion_prevention": "Intrusion Prevention (IPS)",
                }
                items = []
                for key, label in _SW_LABELS.items():
                    parsed = _parse_sonicwall_security_section(raw_data.get(key, ""))
                    enabled = parsed.pop("enabled")
                    items.append({"service": label, "enabled": enabled, "details": parsed})

                # Remaining services — flat SSH show commands from top level
                _EXTRA_CMDS = [
                    "show app-control",
                    "show geo-ip",
                    "show botnet",
                    "show dpi-ssl",
                ]
                extra_result = await ssh.execute_show_commands(_EXTRA_CMDS)
                if extra_result.success:
                    items.extend(_parse_security_status(_EXTRA_CMDS, extra_result.output))

                return {"resource": resource, "items": items}

            # Fallback for other vendors
            ssh_result = await ssh.execute_show_commands(_SECURITY_COMMANDS)
            if not ssh_result.success:
                raise HTTPException(status_code=502, detail=f"Falha na conexão SSH: {ssh_result.error}")
            from app.services.operation_service import _parse_security_status
            items = _parse_security_status(_SECURITY_COMMANDS, ssh_result.output)
            return {"resource": resource, "items": items}

        if resource == "content_filter":
            ssh = get_ssh_connector(device)
            # Must use full-page reader — show content-filter is multi-page
            ssh_result = await ssh.execute_show_commands_full(["show content-filter"])
            if not ssh_result.success:
                raise HTTPException(status_code=502, detail=f"Falha na conexão SSH: {ssh_result.error}")
            items = _parse_named_blocks(
                ssh_result.output,
                ["profile", "policy", "uri-list-object", "uri-list-group",
                 "action", "reputation-object"],
            )
            if not items:
                clean = _ANSI_RE.sub("", ssh_result.output).strip()
                items = [{"type": "Raw", "name": "show content-filter", "details": clean or "(sem output)"}]
            return {"resource": resource, "items": items}

        if resource == "app_rules":
            ssh = get_ssh_connector(device)
            ssh_result = await ssh.execute_show_commands(["show app-rules"])
            if not ssh_result.success:
                raise HTTPException(status_code=502, detail=f"Falha na conexão SSH: {ssh_result.error}")
            items = _parse_named_blocks(ssh_result.output, ["policy", "match-object", "action-object"])
            if not items:
                clean = _ANSI_RE.sub("", ssh_result.output).strip()
                items = [{"type": "Raw", "name": "show app-rules", "details": clean or "(sem output)"}]
            return {"resource": resource, "items": items}

        # ── REST API resources ────────────────────────────────────────────────
        # SonicWall: REST first (Gen7 structured data); fall back to SSH+pagination for Gen6 (HTTP 406)
        if device.vendor == VendorEnum.sonicwall:
            try:
                connector = get_connector(device)
                if resource == "rules":
                    items_data = await connector.list_rules()
                elif resource == "nat":
                    items_data = await connector.list_nat_policies()
                else:
                    items_data = await connector.list_route_policies()
                return {"resource": resource, "items": [dataclasses.asdict(i) for i in items_data]}
            except Exception as exc_rest:
                logger.warning("inspect REST failed for %s/%s (%s), trying SSH fallback", device_id, resource, exc_rest)
                _SW_SSH_CMD = {
                    "rules":  "show access-rules",
                    "nat":    "show nat-policies",
                    "routes": "show route",
                }
                ssh = get_ssh_connector(device)
                # rules and nat need configure mode for detailed config-block output (Gen6)
                if resource in ("rules", "nat"):
                    ssh_result = await ssh.execute_show_in_configure([_SW_SSH_CMD[resource]])
                else:
                    ssh_result = await ssh.execute_show_commands_full([_SW_SSH_CMD[resource]])
                if ssh_result.success and ssh_result.output:
                    raw = _ANSI_RE.sub("", ssh_result.output).strip()
                    if resource == "rules":
                        parsed = _parse_sonicwall_ssh_rules(raw)
                        if parsed:
                            return {"resource": resource, "items": parsed}
                    return {
                        "resource": resource,
                        "items": [{"type": "Raw", "name": _SW_SSH_CMD[resource], "details": raw}],
                    }
                raise HTTPException(status_code=502, detail=f"Falha REST ({exc_rest}) e SSH: {ssh_result.error}")

        connector = get_connector(device)

        if resource == "rules":
            items_data = await connector.list_rules()
        elif resource == "nat":
            items_data = await connector.list_nat_policies()
        else:
            items_data = await connector.list_route_policies()

        return {"resource": resource, "items": [dataclasses.asdict(i) for i in items_data]}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar dispositivo: {exc}")
