import dataclasses
import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.connectors.factory import get_connector, get_ssh_connector
from app.database import get_db
from app.models.device import Device
from app.models.user import User

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
    _: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> dict:
    """Fetch live configuration data directly from the device, bypassing the LLM/operation flow."""
    if resource not in _VALID_RESOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"resource deve ser: {', '.join(_VALID_RESOURCES)}.",
        )

    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado.")

    try:
        # ── SSH-based resources ───────────────────────────────────────────────
        if resource == "security":
            ssh = get_ssh_connector(device)
            ssh_result = await ssh.execute_show_commands(_SECURITY_COMMANDS)
            if not ssh_result.success:
                raise HTTPException(status_code=502, detail=f"Falha na conexão SSH: {ssh_result.error}")
            from app.services.operation_service import _parse_security_status
            items = _parse_security_status(_SECURITY_COMMANDS, ssh_result.output)
            return {"resource": resource, "items": items}

        if resource == "content_filter":
            ssh = get_ssh_connector(device)
            ssh_result = await ssh.execute_show_commands(["show content-filter"])
            if not ssh_result.success:
                raise HTTPException(status_code=502, detail=f"Falha na conexão SSH: {ssh_result.error}")
            items = _parse_named_blocks(
                ssh_result.output,
                ["profile", "policy", "uri-list-object", "cfs-object", "object"],
            )
            if not items:
                # Fallback: return raw output so the operator can see what the device returns
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
