"""Trust Score service — Eternity Trust Score + per-framework governance scores.

Data sources and methodology transparency:
  CIS Benchmark    — average score_pct across latest ComplianceReport per server
  NIST CSF         — CIS controls classified via official CIS→NIST crosswalk (cis_crosswalk.py);
                     gaps in Detect/Respond/Recover filled by audit log density and remediation data
  ISO 27001:2022   — CIS controls classified via official CIS→ISO crosswalk;
                     A.5 Access Control supplemented by real MFA adoption rate from user table
  Eternity Score   — weighted composite of 5 platform signals (no proxies, no inflated defaults)
"""
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.compliance import ComplianceReport
from app.models.device import Device
from app.models.operation import Operation, OperationStatus
from app.models.remediation import RemediationPlan, RemediationStatus
from app.models.trust_score import FrameworkEnum, TrustScore
from app.models.user import User
from app.models.user_tenant_role import UserTenantRole

_ETERNITY_WEIGHTS = {
    "server_compliance":    0.35,
    "operation_hygiene":    0.25,
    "remediation_velocity": 0.20,
    "audit_integrity":      0.10,
    "access_governance":    0.10,
}


# ── Raw data collectors ───────────────────────────────────────────────────────

async def _cis_data(db: AsyncSession, tenant_id: UUID) -> dict[str, Any]:
    """Latest CIS score per server, averaged across all servers."""
    subq = (
        select(
            ComplianceReport.server_id,
            func.max(ComplianceReport.created_at).label("latest"),
        )
        .where(
            ComplianceReport.tenant_id == tenant_id,
            ComplianceReport.server_id.isnot(None),
        )
        .group_by(ComplianceReport.server_id)
        .subquery()
    )
    result = await db.execute(
        select(ComplianceReport.score_pct)
        .join(
            subq,
            (ComplianceReport.server_id == subq.c.server_id)
            & (ComplianceReport.created_at == subq.c.latest),
        )
        .where(
            ComplianceReport.tenant_id == tenant_id,
            ComplianceReport.server_id.isnot(None),
        )
    )
    scores = [r[0] for r in result.fetchall()]
    avg = round(sum(scores) / len(scores), 1) if scores else 0.0
    return {"score": avg, "server_count": len(scores), "per_server_scores": scores}


async def _controls_data(db: AsyncSession, tenant_id: UUID) -> dict[str, Any]:
    """Fetch all control-level results from the latest compliance report per server.
    Each control is tagged with server_id and server_name for drill-down display."""
    from app.models.server import Server

    subq = (
        select(
            ComplianceReport.server_id,
            func.max(ComplianceReport.created_at).label("latest"),
        )
        .where(
            ComplianceReport.tenant_id == tenant_id,
            ComplianceReport.server_id.isnot(None),
        )
        .group_by(ComplianceReport.server_id)
        .subquery()
    )
    result = await db.execute(
        select(ComplianceReport.controls, ComplianceReport.server_id, Server.name)
        .join(
            subq,
            (ComplianceReport.server_id == subq.c.server_id)
            & (ComplianceReport.created_at == subq.c.latest),
        )
        .join(Server, ComplianceReport.server_id == Server.id)
        .where(
            ComplianceReport.tenant_id == tenant_id,
            ComplianceReport.server_id.isnot(None),
        )
    )
    rows = result.fetchall()

    all_controls: list[dict] = []
    server_ids: set = set()
    for controls_json, server_id, server_name in rows:
        server_ids.add(server_id)
        if isinstance(controls_json, list):
            for ctrl in controls_json:
                all_controls.append({
                    **ctrl,
                    "server_id":   str(server_id),
                    "server_name": server_name or str(server_id),
                })

    return {
        "all_controls": all_controls,
        "server_count": len(server_ids),
        "total_count": len(all_controls),
    }


async def _network_compliance_data(db: AsyncSession, tenant_id: UUID) -> dict[str, Any]:
    """Fetch latest network device compliance controls (firewalls + switches).

    Returns the latest report per device, combined into a single controls list.
    avg_score is the unweighted average score_pct across devices.
    """
    subq = (
        select(
            ComplianceReport.device_id,
            func.max(ComplianceReport.created_at).label("latest"),
        )
        .where(
            ComplianceReport.tenant_id == tenant_id,
            ComplianceReport.device_id.isnot(None),
        )
        .group_by(ComplianceReport.device_id)
        .subquery()
    )
    result = await db.execute(
        select(
            ComplianceReport.controls,
            ComplianceReport.score_pct,
            ComplianceReport.device_id,
            Device.name,
        )
        .join(
            subq,
            (ComplianceReport.device_id == subq.c.device_id)
            & (ComplianceReport.created_at == subq.c.latest),
        )
        .join(Device, ComplianceReport.device_id == Device.id)
        .where(
            ComplianceReport.tenant_id == tenant_id,
            ComplianceReport.device_id.isnot(None),
        )
    )
    rows = result.fetchall()

    all_controls: list[dict] = []
    scores: list[float] = []
    device_ids: set = set()

    for controls_json, score_pct, device_id, device_name in rows:
        device_ids.add(device_id)
        scores.append(score_pct)
        if isinstance(controls_json, list):
            for ctrl in controls_json:
                all_controls.append({
                    **ctrl,
                    "device_id":   str(device_id),
                    "device_name": device_name or str(device_id),
                })

    avg = round(sum(scores) / len(scores), 1) if scores else 0.0
    return {
        "all_controls": all_controls,
        "avg_score":    avg,
        "device_count": len(device_ids),
        "total_count":  len(all_controls),
        "per_device_scores": scores,
    }


async def _ops_data(db: AsyncSession, tenant_id: UUID) -> dict[str, Any]:
    """Ratio of completed firewall operations in the last 90 days."""
    cutoff = datetime.utcnow() - timedelta(days=90)

    total_r = await db.execute(
        select(func.count())
        .select_from(Operation)
        .join(Device, Operation.device_id == Device.id)
        .where(Device.tenant_id == tenant_id, Operation.created_at >= cutoff)
    )
    total = total_r.scalar() or 0

    completed_r = await db.execute(
        select(func.count())
        .select_from(Operation)
        .join(Device, Operation.device_id == Device.id)
        .where(
            Device.tenant_id == tenant_id,
            Operation.created_at >= cutoff,
            Operation.status == OperationStatus.completed,
        )
    )
    completed = completed_r.scalar() or 0

    # 0.0 when no operations — no data is not the same as 80% completion
    score = round(completed / total * 100, 1) if total > 0 else 0.0
    return {"score": score, "total_90d": total, "completed": completed}


async def _remediation_data(db: AsyncSession, tenant_id: UUID) -> dict[str, Any]:
    """Remediation plan completion rate in the last 60 days."""
    cutoff = datetime.utcnow() - timedelta(days=60)

    total_r = await db.execute(
        select(func.count())
        .select_from(RemediationPlan)
        .where(RemediationPlan.tenant_id == tenant_id, RemediationPlan.created_at >= cutoff)
    )
    total = total_r.scalar() or 0

    done_r = await db.execute(
        select(func.count())
        .select_from(RemediationPlan)
        .where(
            RemediationPlan.tenant_id == tenant_id,
            RemediationPlan.created_at >= cutoff,
            RemediationPlan.status == RemediationStatus.completed,
        )
    )
    done = done_r.scalar() or 0

    # 0.0 when no plans — absence of remediations is not a neutral signal
    score = round(done / total * 100, 1) if total > 0 else 0.0
    return {"score": score, "plans_60d": total, "completed": done}


async def _audit_data(db: AsyncSession, tenant_id: UUID) -> dict[str, Any]:
    """Platform audit log density for tenant devices in the last 30 days."""
    from app.models.audit_log import AuditLog

    cutoff = datetime.utcnow() - timedelta(days=30)
    count_r = await db.execute(
        select(func.count())
        .select_from(AuditLog)
        .join(Device, AuditLog.device_id == Device.id)
        .where(Device.tenant_id == tenant_id, AuditLog.created_at >= cutoff)
    )
    count = count_r.scalar() or 0
    # 5 events/day = 150/month as minimum expected baseline
    score = min(round(count / 150 * 100, 1), 100.0)
    return {"score": score, "events_30d": count, "events_per_day": round(count / 30, 1)}


async def _access_data(db: AsyncSession, tenant_id: UUID) -> dict[str, Any]:
    """Role separation quality in the tenant."""
    roles_r = await db.execute(
        select(UserTenantRole.role, func.count().label("cnt"))
        .where(UserTenantRole.tenant_id == tenant_id)
        .group_by(UserTenantRole.role)
    )
    role_counts: dict[str, int] = {str(row[0]): row[1] for row in roles_r.fetchall()}
    total = sum(role_counts.values())
    admin_count = role_counts.get("admin", 0)

    if total == 0:
        score = 50.0
    elif len(role_counts) >= 2 and admin_count < total:
        score = 90.0
    elif len(role_counts) >= 2 or admin_count < total:
        score = 70.0
    else:
        score = 50.0

    return {"score": score, "total_users": total, "roles": role_counts}


async def _wazuh_detect_data(db: AsyncSession, tenant_id: UUID) -> dict[str, Any] | None:
    """
    Wazuh-based NIST Detect signal: agent health + critical alert volume.
    Returns None if Wazuh is not configured — caller falls back to audit log density.

    Score components:
      agent_coverage (40%): active_agents / total_agents × 100
        — measures monitoring completeness (are all servers being watched?)
      alert_posture  (60%): 100 − (critical_alerts_30d / 30 × 100), floor 0
        — 0 critical alerts = 100, 30+ critical alerts = 0
        — measures: absence of active critical threats in the environment

    Rationale for the 30-alert baseline: a well-managed environment of typical MSSP
    size sees fewer than 1 critical alert/day as normal noise; 30/month already
    indicates elevated threat activity requiring attention.
    """
    from app.connectors.wazuh_platform import WazuhConnector
    from app.models.integration import IntegrationType
    from app.services.integration_service import resolve_integration

    cfg = await resolve_integration(db, IntegrationType.wazuh, tenant_id)
    if not cfg:
        return None

    try:
        connector = WazuhConnector(
            url=cfg.get("url", ""),
            username=cfg.get("username", ""),
            password=cfg.get("password", ""),
            version=cfg.get("version", "4"),
            verify_ssl=cfg.get("verify_ssl", False),
        )

        health = await connector.get_agents_health()
        alerts = await connector.get_critical_alerts_30d()

        total_agents  = health["total"]
        active_agents = health["active"]
        critical_count = alerts["critical_count_30d"]

        agent_score = round(active_agents / total_agents * 100, 1) if total_agents > 0 else 0.0
        alert_score = max(0.0, round(100 - critical_count / 30 * 100, 1))
        detect_score = round(agent_score * 0.4 + alert_score * 0.6, 1)

        return {
            "score": detect_score,
            "agent_coverage": agent_score,
            "alert_posture": alert_score,
            "total_agents": total_agents,
            "active_agents": active_agents,
            "disconnected_agents": health.get("disconnected", 0),
            "critical_alerts_30d": critical_count,
        }
    except Exception:
        return None


async def _mfa_data(db: AsyncSession, tenant_id: UUID) -> dict[str, Any]:
    """MFA adoption rate among users with access to this tenant."""
    total_r = await db.execute(
        select(func.count())
        .select_from(UserTenantRole)
        .where(UserTenantRole.tenant_id == tenant_id)
    )
    total = total_r.scalar() or 0

    if total == 0:
        return {"score": None, "mfa_enabled": 0, "total_users": 0}

    mfa_r = await db.execute(
        select(func.count())
        .select_from(UserTenantRole)
        .join(User, UserTenantRole.user_id == User.id)
        .where(
            UserTenantRole.tenant_id == tenant_id,
            User.mfa_enabled.is_(True),
        )
    )
    mfa_count = mfa_r.scalar() or 0
    return {
        "score": round(mfa_count / total * 100, 1),
        "mfa_enabled": mfa_count,
        "total_users": total,
    }


# ── Per-framework computers ───────────────────────────────────────────────────

async def compute_cis(db: AsyncSession, tenant_id: UUID) -> tuple[float, dict]:
    """CIS compliance average: server reports + network device reports (weighted by count)."""
    server = await _cis_data(db, tenant_id)
    network = await _network_compliance_data(db, tenant_id)

    s_count = server["server_count"]
    n_count = network["device_count"]

    if s_count > 0 and n_count > 0:
        total = s_count + n_count
        blended = round(
            server["score"] * (s_count / total) + network["avg_score"] * (n_count / total), 1
        )
    elif s_count > 0:
        blended = server["score"]
    elif n_count > 0:
        blended = network["avg_score"]
    else:
        blended = 0.0

    return blended, {
        **server,
        "network_devices": {
            "avg_score":    network["avg_score"],
            "device_count": n_count,
            "per_device_scores": network["per_device_scores"],
        },
        "blended": s_count > 0 and n_count > 0,
    }


async def compute_nist_csf(db: AsyncSession, tenant_id: UUID) -> tuple[float, dict]:
    """
    NIST CSF score via official CIS→NIST crosswalk + Wazuh real-time detection signal
    + network device compliance (firewalls/switches) blended into Protect and Detect.

    Blending order:
      1. Server CIS controls → classify by NIST function (section-based crosswalk)
      2. Network device controls → classify by NIST function (explicit ID mapping)
         Blend per-function: 60% server / 40% network when both have data
      3. Detect: Wazuh (real-time) overrides/supplements the blended CIS+network detect
      4. Respond/Recover: supplemented by remediation velocity when no covering controls

    Server weight 60% / Network 40%: servers have 10-50× more controls than network checks,
    so equal-count weighting would over-represent the sparser network data.
    """
    from app.services.cis_crosswalk import (
        score_by_nist, score_network_by_nist, blend_scores,
        aggregate_score, NIST_LABELS, classify_controls_by_nist,
    )

    # ── Step 1: Server CIS controls ───────────────────────────────────────────
    server_ctrl = await _controls_data(db, tenant_id)
    srv_functions = score_by_nist(server_ctrl["all_controls"])
    control_breakdown = classify_controls_by_nist(server_ctrl["all_controls"])

    # ── Step 2: Network device controls ───────────────────────────────────────
    net_ctrl = await _network_compliance_data(db, tenant_id)
    net_functions = score_network_by_nist(net_ctrl["all_controls"])

    # Blend per function
    functions = {
        f: blend_scores(srv_functions[f], net_functions[f], server_weight=0.60)
        for f in srv_functions
    }

    # ── Step 3: Detect — Wazuh-first, then blended CIS+net, then log density ─
    wazuh_detect = await _wazuh_detect_data(db, tenant_id)

    if wazuh_detect is not None:
        if functions["detect"] is not None:
            functions["detect"] = round(
                functions["detect"] * 0.5 + wazuh_detect["score"] * 0.5, 1
            )
        else:
            functions["detect"] = wazuh_detect["score"]
    elif functions["detect"] is None:
        audit = await _audit_data(db, tenant_id)
        functions["detect"] = audit["score"] if audit["score"] > 0 else None

    # ── Step 4: Respond/Recover — operational supplements ────────────────────
    if functions["respond"] is None:
        ops = await _ops_data(db, tenant_id)
        rem = await _remediation_data(db, tenant_id)
        candidates = [s for s in [ops["score"], rem["score"]] if s > 0]
        if candidates:
            functions["respond"] = round(sum(candidates) / len(candidates), 1)

    if functions["recover"] is None:
        rem = await _remediation_data(db, tenant_id)
        if rem["score"] > 0:
            functions["recover"] = rem["score"]

    overall = aggregate_score(functions)

    # ── Methodology notes ─────────────────────────────────────────────────────
    net_note = (
        f" Dispositivos de rede: {net_ctrl['device_count']} dispositivos, "
        f"{net_ctrl['total_count']} controles (blend 60% servidores / 40% rede)."
        if net_ctrl["device_count"] > 0 else ""
    )
    if wazuh_detect:
        detect_note = (
            f"Detect: Wazuh ({wazuh_detect['active_agents']}/{wazuh_detect['total_agents']} "
            f"agentes ativos, {wazuh_detect['critical_alerts_30d']} alertas críticos/30d)"
            + (" + controles CIS/rede (blend 50/50)" if server_ctrl["total_count"] > 0 or net_ctrl["total_count"] > 0 else "") + ". "
        )
    else:
        detect_note = (
            "Detect: controles CIS de auditoria + checks de syslog de rede"
            + (" (Wazuh não configurado)" if server_ctrl["total_count"] > 0 else " + densidade de logs da plataforma")
            + ". "
        )

    return overall or 0.0, {
        "nist_functions": functions,
        "nist_labels": NIST_LABELS,
        "control_breakdown": control_breakdown,
        "source": "cis_crosswalk",
        "wazuh_detect": wazuh_detect,
        "server_count": server_ctrl["server_count"],
        "device_count": net_ctrl["device_count"],
        "total_controls": server_ctrl["total_count"] + net_ctrl["total_count"],
        "methodology": (
            "Controles CIS Benchmark mapeados para funções NIST CSF via crosswalk oficial CIS Controls v8."
            + net_note + " "
            + detect_note
            + "Respond/Recover suplementados por velocidade de remediação quando ausentes nos relatórios CIS."
        ),
    }


async def compute_iso_27001(db: AsyncSession, tenant_id: UUID) -> tuple[float, dict]:
    """
    ISO 27001:2022 score via official CIS→ISO crosswalk + network device compliance.

    Network controls significantly enrich domains previously thin on server data:
      A.8_network  — firewall rule quality + SNMP + telnet checks (often missing from server CIS)
      A.8_logging  — device syslog + NTP (accurate timestamps for audit trail)
      A.5_access_auth — device admin accounts, VTY timeout, password policy + MFA (blend 70/30)
      A.8_crypto   — TLS version + strong crypto + password-encryption checks

    Blending: 60% server CIS / 40% network device per domain, same logic as NIST.
    """
    from app.services.cis_crosswalk import (
        score_by_iso, score_network_by_iso, blend_scores,
        aggregate_score, ISO_LABELS, classify_controls_by_iso,
    )

    # ── Server CIS controls ───────────────────────────────────────────────────
    server_ctrl = await _controls_data(db, tenant_id)
    srv_domains = score_by_iso(server_ctrl["all_controls"])
    control_breakdown = classify_controls_by_iso(server_ctrl["all_controls"])

    # ── Network device controls ───────────────────────────────────────────────
    net_ctrl = await _network_compliance_data(db, tenant_id)
    net_domains = score_network_by_iso(net_ctrl["all_controls"])

    # Blend per domain
    domains = {
        d: blend_scores(srv_domains[d], net_domains[d], server_weight=0.60)
        for d in srv_domains
    }

    # ── A.5 supplemented by MFA adoption (blend: 70% controls + 30% MFA) ─────
    mfa = await _mfa_data(db, tenant_id)
    if mfa["score"] is not None:
        if domains["A.5_access_auth"] is not None:
            domains["A.5_access_auth"] = round(
                domains["A.5_access_auth"] * 0.70 + mfa["score"] * 0.30, 1
            )
        else:
            domains["A.5_access_auth"] = mfa["score"]

    overall = aggregate_score(domains)

    net_note = (
        f" Dispositivos de rede: {net_ctrl['device_count']} dispositivos "
        f"contribuem para A.8_network, A.8_logging, A.5_access_auth e A.8_crypto "
        f"(blend 60% servidores / 40% rede)."
        if net_ctrl["device_count"] > 0 else ""
    )

    return overall or 0.0, {
        "iso_domains": domains,
        "iso_labels": ISO_LABELS,
        "control_breakdown": control_breakdown,
        "source": "cis_crosswalk",
        "server_count": server_ctrl["server_count"],
        "device_count": net_ctrl["device_count"],
        "total_controls": server_ctrl["total_count"] + net_ctrl["total_count"],
        "mfa_adoption": mfa,
        "methodology": (
            "Controles CIS Benchmark mapeados para domínios ISO 27001:2022 Annex A via "
            "crosswalk oficial CIS Controls v8."
            + net_note + " "
            "A.5 Controle de Acesso suplementado por taxa de adoção de MFA (blend 70/30). "
            "A.8.10/24 Criptografia derivada de controles CIS e verificações de TLS/criptografia em dispositivos de rede."
        ),
    }


async def compute_eternity(db: AsyncSession, tenant_id: UUID) -> tuple[float, dict]:
    """
    Composite Eternity Trust Score (C-level risk index, 0–100).
    Five components — server_compliance now includes network device compliance
    weighted by device count, making it a full compliance posture signal.
    """
    cis_server  = await _cis_data(db, tenant_id)
    cis_network = await _network_compliance_data(db, tenant_id)
    ops         = await _ops_data(db, tenant_id)
    rem         = await _remediation_data(db, tenant_id)
    audit       = await _audit_data(db, tenant_id)
    access      = await _access_data(db, tenant_id)

    # Blend server + network compliance by count (same logic as compute_cis)
    s_count = cis_server["server_count"]
    n_count = cis_network["device_count"]
    if s_count > 0 and n_count > 0:
        total = s_count + n_count
        compliance_score = round(
            cis_server["score"] * (s_count / total)
            + cis_network["avg_score"] * (n_count / total), 1
        )
    elif s_count > 0:
        compliance_score = cis_server["score"]
    elif n_count > 0:
        compliance_score = cis_network["avg_score"]
    else:
        compliance_score = 0.0

    components = {
        "server_compliance":    compliance_score,
        "operation_hygiene":    ops["score"],
        "remediation_velocity": rem["score"],
        "audit_integrity":      audit["score"],
        "access_governance":    access["score"],
    }
    overall = round(sum(components[k] * _ETERNITY_WEIGHTS[k] for k in components), 1)
    return overall, {
        "components": {k: round(v, 1) for k, v in components.items()},
        "weights": _ETERNITY_WEIGHTS,
        "details": {
            "server_compliance": {
                **cis_server,
                "network_devices": {
                    "avg_score":    cis_network["avg_score"],
                    "device_count": n_count,
                },
                "blended_score": compliance_score,
            },
            "operation_hygiene":    ops,
            "remediation_velocity": rem,
            "audit_integrity":      audit,
            "access_governance":    access,
        },
    }


# ── AI narrative ──────────────────────────────────────────────────────────────

_NARRATIVE_SYSTEM = """\
You are a senior cybersecurity analyst writing a governance scorecard for a CISO.
Given compliance scores across frameworks, write a concise executive narrative (3-4 paragraphs).
Focus on: overall risk posture, strongest and weakest areas, recommended top 3 priorities.
Write in professional English. Be specific about numbers. No markdown headers."""


async def _generate_narrative(
    eternity: float, cis: float, nist: float, iso: float, breakdown: dict
) -> str:
    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_NARRATIVE_SYSTEM,
            messages=[{"role": "user", "content": (
                f"Eternity Trust Score: {eternity}/100\n"
                f"CIS Benchmark: {cis}/100\n"
                f"NIST CSF: {nist}/100\n"
                f"ISO 27001: {iso}/100\n\n"
                f"Component breakdown: {breakdown}"
            )}],
        )
        return msg.content[0].text
    except Exception:
        return (
            f"Overall Eternity Trust Score: {eternity}/100. "
            f"CIS Benchmark: {cis}/100. NIST CSF: {nist}/100. ISO 27001: {iso}/100. "
            f"Review individual framework details for improvement recommendations."
        )


# ── Persistence and retrieval ─────────────────────────────────────────────────

async def compute_all(
    db: AsyncSession, tenant_id: UUID, save: bool = True
) -> list[TrustScore]:
    """Compute and optionally persist all 4 framework scores for a tenant."""
    cis_score,      cis_bd      = await compute_cis(db, tenant_id)
    nist_score,     nist_bd     = await compute_nist_csf(db, tenant_id)
    iso_score,      iso_bd      = await compute_iso_27001(db, tenant_id)
    eternity_score, eternity_bd = await compute_eternity(db, tenant_id)

    narrative = await _generate_narrative(
        eternity=eternity_score, cis=cis_score, nist=nist_score, iso=iso_score,
        breakdown=eternity_bd["components"],
    )

    records = [
        TrustScore(tenant_id=tenant_id, framework=FrameworkEnum.cis_benchmark,
                   score_pct=cis_score, breakdown=cis_bd, narrative=""),
        TrustScore(tenant_id=tenant_id, framework=FrameworkEnum.nist_csf,
                   score_pct=nist_score, breakdown=nist_bd, narrative=""),
        TrustScore(tenant_id=tenant_id, framework=FrameworkEnum.iso_27001,
                   score_pct=iso_score, breakdown=iso_bd, narrative=""),
        TrustScore(tenant_id=tenant_id, framework=FrameworkEnum.eternity,
                   score_pct=eternity_score, breakdown=eternity_bd, narrative=narrative),
    ]
    if save:
        for rec in records:
            db.add(rec)
            await db.flush()
            await db.refresh(rec)
    return records


async def get_latest(db: AsyncSession, tenant_id: UUID) -> list[TrustScore]:
    """Most recent score per framework for the tenant."""
    subq = (
        select(TrustScore.framework, func.max(TrustScore.computed_at).label("latest"))
        .where(TrustScore.tenant_id == tenant_id)
        .group_by(TrustScore.framework)
        .subquery()
    )
    result = await db.execute(
        select(TrustScore)
        .join(
            subq,
            (TrustScore.framework == subq.c.framework)
            & (TrustScore.computed_at == subq.c.latest),
        )
        .where(TrustScore.tenant_id == tenant_id)
    )
    return list(result.scalars().all())


async def get_history(
    db: AsyncSession, tenant_id: UUID, framework: FrameworkEnum, limit: int = 30
) -> list[TrustScore]:
    result = await db.execute(
        select(TrustScore)
        .where(TrustScore.tenant_id == tenant_id, TrustScore.framework == framework)
        .order_by(TrustScore.computed_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
