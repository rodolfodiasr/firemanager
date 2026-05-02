"""Integration service — cascade resolution + connectivity testers."""
import asyncio
import time
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import Integration, IntegrationType
from app.utils.crypto import decrypt_credentials, encrypt_credentials


# ── Cascade resolution ────────────────────────────────────────────────────────

async def resolve_integration(
    db: AsyncSession,
    integration_type: IntegrationType,
    tenant_id: UUID,
) -> dict | None:
    """Return decrypted config for type, cascading tenant → global."""
    # 1. Tenant-specific
    row = await db.execute(
        select(Integration).where(
            Integration.type == integration_type,
            Integration.tenant_id == tenant_id,
            Integration.is_active.is_(True),
        )
    )
    intg = row.scalar_one_or_none()

    if not intg:
        # 2. Global fallback
        row = await db.execute(
            select(Integration).where(
                Integration.type == integration_type,
                Integration.tenant_id.is_(None),
                Integration.is_active.is_(True),
            )
        )
        intg = row.scalar_one_or_none()

    if not intg:
        return None
    return decrypt_credentials(intg.encrypted_config)


# ── CRUD helpers ──────────────────────────────────────────────────────────────

_SENSITIVE_KEYS = {"token_secret", "api_key", "password", "secret"}


def _sanitize_config(config: dict) -> dict:
    return {
        k: ("__masked__" if any(s in k.lower() for s in _SENSITIVE_KEYS) and v else v)
        for k, v in config.items()
    }


def _to_read(intg: Integration) -> dict:
    config = decrypt_credentials(intg.encrypted_config)
    return {
        "id": intg.id,
        "tenant_id": intg.tenant_id,
        "type": intg.type,
        "name": intg.name,
        "is_active": intg.is_active,
        "scope": "global" if intg.tenant_id is None else "tenant",
        "config_preview": _sanitize_config(config),
        "created_at": intg.created_at,
        "updated_at": intg.updated_at,
    }


async def list_integrations(
    db: AsyncSession,
    tenant_id: UUID | None,
    is_super_admin: bool,
) -> list[dict]:
    """List integrations visible to the caller.

    Super admin: all global integrations.
    Tenant user: global + their tenant's integrations.
    """
    if is_super_admin:
        result = await db.execute(
            select(Integration).where(Integration.tenant_id.is_(None)).order_by(Integration.type)
        )
        rows = list(result.scalars().all())
    else:
        result = await db.execute(
            select(Integration).where(
                (Integration.tenant_id == tenant_id) | Integration.tenant_id.is_(None)
            ).order_by(Integration.tenant_id.nullsfirst(), Integration.type)
        )
        rows = list(result.scalars().all())

    return [_to_read(r) for r in rows]


async def create_integration(
    db: AsyncSession,
    data_type: IntegrationType,
    name: str,
    config: dict,
    tenant_id: UUID | None,
    is_active: bool = True,
) -> dict:
    intg = Integration(
        type=data_type,
        name=name,
        tenant_id=tenant_id,
        encrypted_config=encrypt_credentials(config),
        is_active=is_active,
    )
    db.add(intg)
    await db.flush()
    await db.refresh(intg)
    return _to_read(intg)


async def update_integration(
    db: AsyncSession,
    integration_id: UUID,
    name: str | None,
    config: dict | None,
    is_active: bool | None,
    caller_tenant_id: UUID | None,
    is_super_admin: bool,
) -> dict:
    result = await db.execute(select(Integration).where(Integration.id == integration_id))
    intg = result.scalar_one_or_none()
    if not intg:
        raise ValueError("Integration not found")

    # Scope guard
    if not is_super_admin and intg.tenant_id != caller_tenant_id:
        raise PermissionError("No access")

    if name is not None:
        intg.name = name
    if config is not None:
        existing_config = decrypt_credentials(intg.encrypted_config)
        merged = {**existing_config}
        for k, v in config.items():
            # Keep existing value for masked/empty sensitive fields
            if v == "" or v == "__masked__":
                continue
            merged[k] = v
        intg.encrypted_config = encrypt_credentials(merged)
    if is_active is not None:
        intg.is_active = is_active

    await db.flush()
    await db.refresh(intg)
    return _to_read(intg)


async def delete_integration(
    db: AsyncSession,
    integration_id: UUID,
    caller_tenant_id: UUID | None,
    is_super_admin: bool,
) -> None:
    result = await db.execute(select(Integration).where(Integration.id == integration_id))
    intg = result.scalar_one_or_none()
    if not intg:
        raise ValueError("Integration not found")
    if not is_super_admin and intg.tenant_id != caller_tenant_id:
        raise PermissionError("No access")
    await db.delete(intg)
    await db.flush()


# ── Connectivity testers ──────────────────────────────────────────────────────

async def test_shodan(config: dict) -> dict:
    api_key = config.get("api_key", "")
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.shodan.io/api-info",
                params={"key": api_key},
            )
            latency = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                data = resp.json()
                plan = data.get("plan", "unknown")
                credits = data.get("query_credits", 0)
                return {"success": True, "message": f"Plan: {plan} | Query credits: {credits}", "latency_ms": latency}
            return {"success": False, "message": resp.json().get("error", f"HTTP {resp.status_code}"), "latency_ms": latency}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


async def test_wazuh(config: dict) -> dict:
    from app.connectors.wazuh_platform import WazuhConnector
    connector = WazuhConnector(
        url=config.get("url", ""),
        username=config.get("username", ""),
        password=config.get("password", ""),
        version=config.get("version", "4"),
        verify_ssl=config.get("verify_ssl", False),
    )
    start = time.monotonic()
    ok, message = await connector.ping()
    latency = (time.monotonic() - start) * 1000
    return {"success": ok, "message": message, "latency_ms": latency}


async def test_openvas(config: dict) -> dict:
    host = config.get("host", "")
    port = int(config.get("port", 9390))
    start = time.monotonic()
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=5.0
        )
        latency = (time.monotonic() - start) * 1000
        writer.close()
        await writer.wait_closed()
        return {"success": True, "message": f"Conexão TCP estabelecida em {host}:{port}", "latency_ms": latency}
    except asyncio.TimeoutError:
        return {"success": False, "message": f"Timeout ao conectar em {host}:{port}"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


async def test_nmap(config: dict) -> dict:
    binary = config.get("binary_path", "/usr/bin/nmap")
    start = time.monotonic()
    try:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                binary, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ),
            timeout=5.0,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        latency = (time.monotonic() - start) * 1000
        version_line = stdout.decode().split("\n")[0].strip()
        return {"success": True, "message": version_line or "nmap disponível", "latency_ms": latency}
    except FileNotFoundError:
        return {"success": False, "message": f"Binário não encontrado: {binary}"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


async def test_zabbix(config: dict) -> dict:
    from app.connectors.zabbix import ZabbixConnector
    connector = ZabbixConnector(
        url=config.get("url", ""),
        token=config.get("token", ""),
        version=config.get("version", "7"),
        verify_ssl=config.get("verify_ssl", False),
    )
    ok, message = await connector.ping()
    return {"success": ok, "message": message}


async def test_bookstack(config: dict) -> dict:
    from app.connectors.bookstack import connector_from_config
    connector = connector_from_config(config)
    start = time.monotonic()
    ok, message = await connector.ping()
    latency = (time.monotonic() - start) * 1000
    return {"success": ok, "message": message, "latency_ms": latency}


_TESTERS = {
    IntegrationType.shodan:     test_shodan,
    IntegrationType.wazuh:      test_wazuh,
    IntegrationType.openvas:    test_openvas,
    IntegrationType.nmap:       test_nmap,
    IntegrationType.zabbix:     test_zabbix,
    IntegrationType.bookstack:  test_bookstack,
}


async def test_integration(integration_type: IntegrationType, config: dict) -> dict:
    tester = _TESTERS.get(integration_type)
    if not tester:
        return {"success": False, "message": "Tipo de integração não suportado"}
    return await tester(config)
