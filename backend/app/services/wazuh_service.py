"""Wazuh service — high-level helpers for AI enrichment."""
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

logger = logging.getLogger(__name__)


async def get_agent_recent_alerts(
    tenant_id: UUID,
    agent_identifier: str,
    hours: int = 24,
) -> str | None:
    """
    Return a plain-text summary of recent Wazuh alerts for an agent.

    Resolves the tenant's (or global) Wazuh integration, finds the agent by IP or
    name, then fetches recent alerts and vulnerability highlights.

    Returns None if there is no Wazuh integration configured or the agent is not
    found.
    """
    from app.connectors.wazuh_platform import WazuhConnector
    from app.database import AsyncSessionLocal
    from app.models.integration import IntegrationType
    from app.services.integration_service import resolve_integration

    async with AsyncSessionLocal() as db:
        config = await resolve_integration(db, IntegrationType.wazuh, tenant_id)

    if not config:
        return None

    connector = WazuhConnector(
        url=config.get("url", ""),
        username=config.get("username", ""),
        password=config.get("password", ""),
        version=config.get("version", "4"),
        verify_ssl=config.get("verify_ssl", False),
    )

    agent = await connector.find_agent_by_host(agent_identifier)
    if not agent:
        logger.debug("wazuh_agent_not_found identifier=%s", agent_identifier)
        return None

    agent_id   = agent.get("id", "")
    agent_name = agent.get("name", agent_identifier)
    agent_ip   = agent.get("ip", "—")
    status     = agent.get("status", "—")

    alerts = await _get_recent_alerts(connector, agent_id, hours)
    vulns  = await _get_vulns(connector, agent_id)

    return _format_summary(agent_name, agent_ip, status, alerts, vulns, hours)


# ── internal helpers ──────────────────────────────────────────────────────────

async def _get_recent_alerts(connector, agent_id: str, hours: int) -> list[dict]:
    """Fetch alerts for the agent filtered by time window in Python."""
    try:
        data = await connector._get(
            "/alerts",
            {
                "limit": 100,
                "sort": "-timestamp",
                "q": f"rule.level>=7,agent.id={agent_id}",
            },
        )
        alerts = data.get("data", {}).get("affected_items", [])
    except Exception:
        try:
            alerts = await connector.get_alerts(limit=100)
            alerts = [a for a in alerts if a.get("agent", {}).get("id") == agent_id]
        except Exception as exc:
            logger.debug("wazuh_alerts_failed agent=%s error=%s", agent_id, exc)
            return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    filtered: list[dict] = []
    for alert in alerts:
        ts_str = alert.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                filtered.append(alert)
        except Exception:
            filtered.append(alert)

    return filtered


async def _get_vulns(connector, agent_id: str) -> list[dict]:
    try:
        return await connector.get_agent_vulnerabilities(agent_id, limit=20)
    except Exception as exc:
        logger.debug("wazuh_vulns_failed agent=%s error=%s", agent_id, exc)
        return []


def _format_summary(
    agent_name: str,
    agent_ip: str,
    status: str,
    alerts: list[dict],
    vulns: list[dict],
    hours: int,
) -> str:
    lines: list[str] = [
        f"Agente Wazuh: {agent_name} (IP: {agent_ip}) | Status: {status} | Janela: últimas {hours}h"
    ]

    if alerts:
        lines.append(f"\nAlertas recentes ({len(alerts)}):")
        for alert in alerts[:20]:
            rule    = alert.get("rule", {})
            level   = rule.get("level", "?")
            desc    = rule.get("description", "—")
            ts      = alert.get("timestamp", "")
            ts_str  = ts[:19].replace("T", " ") if ts else "—"
            lines.append(f"  [Nível {level}] {desc} — {ts_str}")
    else:
        lines.append(f"\nNenhum alerta (nível ≥ 7) nas últimas {hours}h.")

    if vulns:
        crit  = [v for v in vulns if v.get("severity", "").lower() in ("critical", "high")]
        label = f"Vulnerabilidades críticas/altas ({len(crit)} de {len(vulns)} total):"
        lines.append(f"\n{label}")
        for vuln in crit[:10]:
            cve      = vuln.get("cve", "—")
            pkg      = vuln.get("name", "—")
            severity = vuln.get("severity", "—")
            lines.append(f"  {cve} [{severity}] em {pkg}")
        if not crit:
            lines.append("  Nenhuma vulnerabilidade crítica/alta detectada.")

    return "\n".join(lines)
