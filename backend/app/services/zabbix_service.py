"""Zabbix service — high-level helpers for AI enrichment."""
import logging
from datetime import datetime, timezone
from uuid import UUID

logger = logging.getLogger(__name__)


async def get_host_recent_summary(
    tenant_id: UUID,
    host_identifier: str,
    hours: int = 24,
) -> str | None:
    """
    Return a plain-text summary of recent Zabbix triggers and metrics for a host.

    Resolves the tenant's (or global) Zabbix integration, finds the host by IP or
    name, then fetches active triggers and the most-recent item values.

    Returns None if there is no Zabbix integration configured or the host is not
    found in Zabbix.
    """
    from app.connectors.zabbix import ZabbixConnector
    from app.database import AsyncSessionLocal
    from app.models.integration import IntegrationType
    from app.services.integration_service import resolve_integration

    async with AsyncSessionLocal() as db:
        config = await resolve_integration(db, IntegrationType.zabbix, tenant_id)

    if not config:
        return None

    connector = ZabbixConnector(
        url=config.get("url", ""),
        token=config.get("token", ""),
        version=config.get("version", "7"),
        verify_ssl=config.get("verify_ssl", False),
    )

    host = await _find_host(connector, host_identifier)
    if not host:
        logger.debug("zabbix_host_not_found identifier=%s", host_identifier)
        return None

    host_id   = host["hostid"]
    host_name = host.get("name") or host.get("host", host_id)

    triggers = await _get_active_triggers(connector, host_id)
    items    = await connector.get_host_items(host_id, limit=20)

    return _format_summary(host_name, triggers, items, hours)


# ── internal helpers ──────────────────────────────────────────────────────────

async def _find_host(connector, identifier: str) -> dict | None:
    """Find a Zabbix host matching the given IP or name (case-insensitive substring)."""
    try:
        hosts = await connector.get_hosts(limit=500)
    except Exception as exc:
        logger.warning("zabbix_get_hosts_failed error=%s", exc)
        return None

    identifier_lower = identifier.lower()
    for host in hosts:
        interfaces = host.get("interfaces", [])
        for iface in interfaces:
            if iface.get("ip", "") == identifier:
                return host
        if identifier_lower in host.get("host", "").lower():
            return host
        if identifier_lower in host.get("name", "").lower():
            return host
    return None


async def _get_active_triggers(connector, host_id: str) -> list[dict]:
    try:
        return await connector.get_triggers(host_id=host_id, limit=30)
    except Exception as exc:
        logger.debug("zabbix_triggers_failed host=%s error=%s", host_id, exc)
        return []


_PRIORITY_LABELS = {
    "0": "Not classified",
    "1": "Information",
    "2": "Warning",
    "3": "Average",
    "4": "High",
    "5": "Disaster",
}


def _format_summary(host_name: str, triggers: list[dict], items: list[dict], hours: int) -> str:
    lines: list[str] = [f"Host Zabbix: {host_name} | Janela: últimas {hours}h"]

    if triggers:
        lines.append(f"\nTriggers ativos ({len(triggers)}):")
        for t in triggers:
            prio  = _PRIORITY_LABELS.get(str(t.get("priority", "0")), "?")
            desc  = t.get("description", "—")
            ts    = t.get("lastchange", "")
            ts_str = _fmt_ts(ts)
            lines.append(f"  [{prio}] {desc} — última ocorrência: {ts_str}")
    else:
        lines.append("\nNenhum trigger ativo.")

    if items:
        lines.append(f"\nMétricas recentes ({len(items)}):")
        for item in items[:15]:
            name  = item.get("name", "—")
            value = item.get("lastvalue", "—")
            units = item.get("units", "")
            ts    = item.get("lastclock", "")
            ts_str = _fmt_ts(ts)
            lines.append(f"  {name}: {value}{(' ' + units) if units else ''} ({ts_str})")

    return "\n".join(lines)


def _fmt_ts(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(ts) if ts else "—"
