"""F37 — Normalização e processamento de alertas SIEM."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.siem import SiemAlert, SiemConnector


# ── Normalizadores por SIEM ───────────────────────────────────────────────────

def normalize_wazuh(payload: dict) -> dict:
    """Normaliza alerta Wazuh (manager → agent webhook format)."""
    rule = payload.get("rule", {})
    agent = payload.get("agent", {})
    data = payload.get("data", {})

    level = int(rule.get("level", 3))
    if level >= 12:
        severity = "critical"
    elif level >= 9:
        severity = "high"
    elif level >= 6:
        severity = "medium"
    else:
        severity = "low"

    return {
        "source_rule_id": str(rule.get("id", "")),
        "severity": severity,
        "title": rule.get("description", "Wazuh Alert"),
        "description": f"Rule {rule.get('id')}: {rule.get('description')} (level {level})",
        "affected_host": agent.get("name") or agent.get("ip", ""),
        "source_ip": agent.get("ip", ""),
    }


def normalize_splunk(payload: dict) -> dict:
    """Normaliza alerta Splunk (webhook savedsearch alert action)."""
    result = payload.get("result", {})
    search_name = payload.get("search_name", "Splunk Alert")

    severity_map = {"1": "critical", "2": "high", "3": "medium", "4": "low", "5": "info"}
    severity = severity_map.get(str(result.get("urgency", "3")), "medium")

    return {
        "source_rule_id": payload.get("sid", ""),
        "severity": severity,
        "title": search_name,
        "description": result.get("_raw", ""),
        "affected_host": result.get("host", result.get("dest", "")),
        "source_ip": result.get("src_ip", result.get("src", "")),
    }


def normalize_sentinel(payload: dict) -> dict:
    """Normaliza alerta Microsoft Sentinel (Logic Apps webhook)."""
    props = payload.get("properties", {})
    entities = props.get("relatedEntities", [])

    severity_map = {
        "High": "high",
        "Medium": "medium",
        "Low": "low",
        "Informational": "info",
    }
    severity = severity_map.get(props.get("severity", "Medium"), "medium")

    host = next(
        (e.get("properties", {}).get("hostName", e.get("properties", {}).get("address", ""))
         for e in entities if e.get("kind") in ("Host", "Ip")),
        "",
    )
    ip = next(
        (e.get("properties", {}).get("address", "") for e in entities if e.get("kind") == "Ip"),
        "",
    )

    return {
        "source_rule_id": payload.get("id", ""),
        "severity": severity,
        "title": props.get("title", "Sentinel Alert"),
        "description": props.get("description", ""),
        "affected_host": host,
        "source_ip": ip,
    }


def normalize_generic(payload: dict) -> dict:
    """Fallback para formatos desconhecidos — extrai campos comuns."""
    severity_raw = str(payload.get("severity") or payload.get("level") or "medium").lower()
    if severity_raw in ("critical", "high", "medium", "low", "info"):
        severity = severity_raw
    elif severity_raw in ("1", "fatal", "emergency"):
        severity = "critical"
    elif severity_raw in ("2", "error"):
        severity = "high"
    elif severity_raw in ("3", "warning", "warn"):
        severity = "medium"
    else:
        severity = "low"

    return {
        "source_rule_id": str(payload.get("rule_id") or payload.get("id") or ""),
        "severity": severity,
        "title": str(payload.get("title") or payload.get("name") or payload.get("message") or "Alert"),
        "description": str(payload.get("description") or payload.get("details") or ""),
        "affected_host": str(payload.get("host") or payload.get("hostname") or payload.get("dest") or ""),
        "source_ip": str(payload.get("src_ip") or payload.get("source_ip") or payload.get("src") or ""),
    }


_NORMALIZERS = {
    "wazuh":    normalize_wazuh,
    "splunk":   normalize_splunk,
    "sentinel": normalize_sentinel,
    "log360":   normalize_generic,
    "qradar":   normalize_generic,
}


async def process_inbound_alert(
    db: AsyncSession,
    connector: SiemConnector,
    payload: dict[str, Any],
) -> SiemAlert:
    """Normaliza e persiste alerta. Avalia triggers SOAR se houver match."""
    normalizer = _NORMALIZERS.get(connector.siem_type, normalize_generic)
    normalized = normalizer(payload)

    alert = SiemAlert(
        id=uuid4(),
        tenant_id=connector.tenant_id,
        connector_id=connector.id,
        source_rule_id=normalized["source_rule_id"] or None,
        severity=normalized["severity"],
        title=normalized["title"],
        description=normalized["description"] or None,
        affected_host=normalized["affected_host"] or None,
        source_ip=normalized["source_ip"] or None,
        raw_payload=payload,
    )
    db.add(alert)

    # Atualiza last_event_at no connector
    connector.last_event_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(alert)

    # Avalia triggers SOAR
    try:
        from app.services.soar_service import evaluate_trigger
        context = {
            "severity":      normalized["severity"],
            "title":         normalized["title"],
            "affected_host": normalized["affected_host"],
            "source_ip":     normalized["source_ip"],
            "siem_type":     connector.siem_type,
        }
        executions = await evaluate_trigger(db, connector.tenant_id, "siem_alert", context)
        if executions:
            alert.playbook_triggered = True
            await db.flush()
    except Exception:
        pass   # SOAR falhou — alerta ainda persiste

    await db.commit()
    return alert
