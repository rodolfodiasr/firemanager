"""F23.ext — RMM Integration Service (multi-vendor)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rmm import RmmAgent, RmmIntegration
from app.utils.crypto import decrypt_credentials, encrypt_credentials


RMM_TYPES = ("tactical_rmm", "ninja_rmm", "atera", "connectwise_automate")


async def list_integrations(db: AsyncSession, tenant_id: UUID) -> list[RmmIntegration]:
    result = await db.execute(
        select(RmmIntegration)
        .where(RmmIntegration.tenant_id == tenant_id)
        .order_by(RmmIntegration.created_at)
    )
    return list(result.scalars().all())


async def get_integration(db: AsyncSession, integration_id: UUID, tenant_id: UUID) -> RmmIntegration | None:
    result = await db.execute(
        select(RmmIntegration).where(
            RmmIntegration.id == integration_id,
            RmmIntegration.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_integration(
    db: AsyncSession,
    tenant_id: UUID,
    name: str,
    rmm_type: str,
    base_url: str,
    credentials: dict,
    verify_ssl: bool = True,
) -> RmmIntegration:
    if rmm_type not in RMM_TYPES:
        raise ValueError(f"Tipo RMM inválido: {rmm_type}. Aceitos: {RMM_TYPES}")
    config_encrypted = encrypt_credentials(credentials)
    integration = RmmIntegration(
        tenant_id=tenant_id,
        name=name,
        rmm_type=rmm_type,
        base_url=base_url.rstrip("/"),
        config_encrypted=config_encrypted,
        verify_ssl=verify_ssl,
    )
    db.add(integration)
    await db.flush()
    await db.refresh(integration)
    return integration


async def update_integration(
    db: AsyncSession,
    integration: RmmIntegration,
    name: str | None,
    base_url: str | None,
    credentials: dict | None,
    verify_ssl: bool | None,
    is_active: bool | None,
) -> RmmIntegration:
    if name is not None:
        integration.name = name
    if base_url is not None:
        integration.base_url = base_url.rstrip("/")
    if credentials is not None:
        integration.config_encrypted = encrypt_credentials(credentials)
    if verify_ssl is not None:
        integration.verify_ssl = verify_ssl
    if is_active is not None:
        integration.is_active = is_active
    await db.flush()
    await db.refresh(integration)
    return integration


async def delete_integration(db: AsyncSession, integration: RmmIntegration) -> None:
    await db.delete(integration)


async def test_connection(integration: RmmIntegration) -> tuple[bool, str]:
    config = decrypt_credentials(integration.config_encrypted or "{}")
    config["base_url"] = integration.base_url
    config["verify_ssl"] = integration.verify_ssl

    if integration.rmm_type == "tactical_rmm":
        from app.services.tactical_rmm_service import test_connection as _test
        return await _test(config)
    elif integration.rmm_type == "ninja_rmm":
        from app.services.ninja_rmm_service import test_connection as _test
        return await _test(config)
    elif integration.rmm_type == "atera":
        from app.services.atera_service import test_connection as _test
        return await _test(config)
    elif integration.rmm_type == "connectwise_automate":
        from app.services.connectwise_automate_service import test_connection as _test
        return await _test(config)
    return False, f"Tipo RMM não suportado: {integration.rmm_type}"


async def sync_agents(db: AsyncSession, integration: RmmIntegration) -> int:
    config = decrypt_credentials(integration.config_encrypted or "{}")
    config["base_url"] = integration.base_url
    config["verify_ssl"] = integration.verify_ssl

    if integration.rmm_type == "tactical_rmm":
        from app.services.tactical_rmm_service import list_users
        raw_items = await list_users(config)
        normalized = [_normalize_tactical(r) for r in raw_items]
    elif integration.rmm_type == "ninja_rmm":
        from app.services.ninja_rmm_service import list_devices, normalize_device
        raw_items = await list_devices(config)
        normalized = [normalize_device(r) for r in raw_items]
    elif integration.rmm_type == "atera":
        from app.services.atera_service import list_devices, normalize_device
        raw_items = await list_devices(config)
        normalized = [normalize_device(r) for r in raw_items]
    elif integration.rmm_type == "connectwise_automate":
        from app.services.connectwise_automate_service import list_devices, normalize_device
        raw_items = await list_devices(config)
        normalized = [normalize_device(r) for r in raw_items]
    else:
        return 0

    existing_result = await db.execute(
        select(RmmAgent).where(RmmAgent.integration_id == integration.id)
    )
    existing = {a.external_id: a for a in existing_result.scalars().all()}

    synced_ids: set[str] = set()
    for item in normalized:
        ext_id = item["external_id"]
        if not ext_id:
            continue
        synced_ids.add(ext_id)
        if ext_id in existing:
            agent = existing[ext_id]
            for k, v in item.items():
                if k != "external_id":
                    setattr(agent, k, v)
            agent.synced_at = datetime.now(timezone.utc)
        else:
            agent = RmmAgent(
                integration_id=integration.id,
                tenant_id=integration.tenant_id,
                external_id=ext_id,
                **{k: v for k, v in item.items() if k != "external_id"},
            )
            db.add(agent)

    stale_ids = set(existing.keys()) - synced_ids
    if stale_ids:
        await db.execute(
            delete(RmmAgent).where(
                RmmAgent.integration_id == integration.id,
                RmmAgent.external_id.in_(stale_ids),
            )
        )

    integration.agent_count = len(synced_ids)
    integration.last_sync_at = datetime.now(timezone.utc)
    integration.last_sync_status = "ok"
    integration.last_sync_message = f"{len(synced_ids)} agente(s) sincronizados"
    await db.flush()
    return len(synced_ids)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _normalize_tactical(raw: dict) -> dict:
    # Extrai primeiro IP da lista local_ips ou ip_addresses
    ips = raw.get("local_ips") or raw.get("ip_addresses") or ""
    if isinstance(ips, list):
        ip = ips[0] if ips else None
    else:
        ip = ips.split(",")[0].strip() if ips else None

    return {
        "external_id": str(raw.get("agent_id") or raw.get("id", "")),
        "hostname": raw.get("hostname") or raw.get("computername", ""),
        "os_name": raw.get("operating_system") or raw.get("os_name", ""),
        "ip_address": ip,
        "status": "online" if raw.get("status") == "online" else "offline",
        "last_seen": _parse_dt(raw.get("last_seen")),
        "patches_pending": raw.get("patches_pending") or raw.get("pending_actions_count"),
        "alerts_count": raw.get("alerts_count", 0),
        "raw_data": raw,
    }


async def list_agents(
    db: AsyncSession,
    tenant_id: UUID,
    integration_id: UUID | None = None,
) -> list[RmmAgent]:
    q = select(RmmAgent).where(RmmAgent.tenant_id == tenant_id)
    if integration_id:
        q = q.where(RmmAgent.integration_id == integration_id)
    result = await db.execute(q.order_by(RmmAgent.hostname))
    return list(result.scalars().all())
