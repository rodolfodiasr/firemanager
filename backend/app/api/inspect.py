import dataclasses
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

_SECURITY_COMMANDS = [
    "show gateway-antivirus",
    "show anti-spyware",
    "show intrusion-prevention",
    "show app-control",
    "show geo-ip",
    "show botnet",
    "show dpi-ssl",
]


@router.get("/{device_id}/inspect")
async def inspect_device(
    device_id: UUID,
    resource: str = Query(...),
    _: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> dict:
    """Fetch live configuration data directly from the device, bypassing the LLM/operation flow."""
    if resource not in ("rules", "nat", "routes", "security"):
        raise HTTPException(status_code=400, detail="resource deve ser: rules, nat, routes ou security.")

    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado.")

    try:
        if resource == "security":
            ssh = get_ssh_connector(device)
            ssh_result = await ssh.execute_show_commands(_SECURITY_COMMANDS)
            if not ssh_result.success:
                raise HTTPException(status_code=502, detail=f"Falha na conexão SSH: {ssh_result.error}")
            from app.services.operation_service import _parse_security_status
            items = _parse_security_status(_SECURITY_COMMANDS, ssh_result.output)
            return {"resource": resource, "items": items}

        connector = get_connector(device)

        if resource == "rules":
            items = await connector.list_rules()
        elif resource == "nat":
            items = await connector.list_nat_policies()
        else:
            items = await connector.list_route_policies()

        return {"resource": resource, "items": [dataclasses.asdict(i) for i in items]}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar dispositivo: {exc}")
