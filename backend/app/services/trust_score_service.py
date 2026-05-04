"""Trust Score service — Eternity Trust Score + per-framework governance scores."""
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
    """Latest CIS score per server, then average across all servers."""
    subq = (
        select(
            ComplianceReport.server_id,
            func.max(ComplianceReport.created_at).label("latest"),
        )
        .where(ComplianceReport.tenant_id == tenant_id)
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
        .where(ComplianceReport.tenant_id == tenant_id)
    )
    scores = [r[0] for r in result.fetchall()]
    avg = round(sum(scores) / len(scores), 1) if scores else 0.0
    return {"score": avg, "server_count": len(scores), "per_server_scores": scores}


async def _ops_data(db: AsyncSession, tenant_id: UUID) -> dict[str, Any]:
    """Ratio of completed operations in the last 90 days (via device tenant join)."""
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

    score = round(completed / total * 100, 1) if total > 0 else 80.0
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

    score = round(done / total * 100, 1) if total > 0 else 70.0
    return {"score": score, "plans_60d": total, "completed": done}


async def _audit_data(db: AsyncSession, tenant_id: UUID) -> dict[str, Any]:
    """Audit log density for tenant devices in the last 30 days."""
    from app.models.audit_log import AuditLog

    cutoff = datetime.utcnow() - timedelta(days=30)
    count_r = await db.execute(
        select(func.count())
        .select_from(AuditLog)
        .join(Device, AuditLog.device_id == Device.id)
        .where(Device.tenant_id == tenant_id, AuditLog.created_at >= cutoff)
    )
    count = count_r.scalar() or 0
    # 5 events/day = 150/month expected minimum; floor at 20 (P3 immutability guarantees infra exists)
    score = min(round(count / 150 * 100, 1), 100.0)
    score = max(score, 20.0)
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


# ── Per-framework computers ───────────────────────────────────────────────────

async def compute_cis(db: AsyncSession, tenant_id: UUID) -> tuple[float, dict]:
    d = await _cis_data(db, tenant_id)
    return d["score"], d


async def compute_nist_csf(db: AsyncSession, tenant_id: UUID) -> tuple[float, dict]:
    """NIST CSF score derived from CIS + operational posture across 5 functions."""
    cis   = await _cis_data(db, tenant_id)
    ops   = await _ops_data(db, tenant_id)
    audit = await _audit_data(db, tenant_id)
    rem   = await _remediation_data(db, tenant_id)

    funcs = {
        "identify": round(min(cis["score"] * 0.8 + 20, 100), 1),
        "protect":  round(cis["score"], 1),
        "detect":   round(audit["score"], 1),
        "respond":  round(ops["score"] * 0.6 + rem["score"] * 0.4, 1),
        "recover":  round(rem["score"], 1),
    }
    overall = round(sum(funcs.values()) / 5, 1)
    return overall, {"nist_functions": funcs}


async def compute_iso_27001(db: AsyncSession, tenant_id: UUID) -> tuple[float, dict]:
    """ISO 27001 score from Security Hardening evidence (P1–P6) + CIS compliance data."""
    cis    = await _cis_data(db, tenant_id)
    ops    = await _ops_data(db, tenant_id)
    access = await _access_data(db, tenant_id)
    audit  = await _audit_data(db, tenant_id)

    # P1=A.10 Crypto, P2=A.9 Access, P3=A.8.15 Logging, P4-P5=A.8.6 Ops, P6=A.9.4 System Access
    controls = {
        "A.10_cryptography":   100.0,
        "A.9_access_control":  access["score"],
        "A.8.15_logging":      audit["score"],
        "A.8.6_operations":    ops["score"],
        "A.9.4_system_access": min(ops["score"] * 0.7 + 30, 100),
        "A.12_compliance":     cis["score"],
    }
    overall = round(min(sum(controls.values()) / len(controls), 100.0), 1)
    return overall, {
        "iso_controls": {k: round(v, 1) for k, v in controls.items()},
        "based_on": ["P1", "P2", "P3", "P4", "P5", "P6"],
    }


async def compute_eternity(db: AsyncSession, tenant_id: UUID) -> tuple[float, dict]:
    """Composite Eternity Trust Score — C-level risk index."""
    cis    = await _cis_data(db, tenant_id)
    ops    = await _ops_data(db, tenant_id)
    rem    = await _remediation_data(db, tenant_id)
    audit  = await _audit_data(db, tenant_id)
    access = await _access_data(db, tenant_id)

    components = {
        "server_compliance":    cis["score"],
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
            "server_compliance":    cis,
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
        for rec in records:
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
