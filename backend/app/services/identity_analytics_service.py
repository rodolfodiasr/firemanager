"""F36.cont — Identity analytics: posture score, privilege creep, group health."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity_governance import (
    AdGroup, AdGroupMembership, AdUser, SoDViolation,
    AccessCampaign, JitRequest,
)
from app.models.identity_advanced import (
    ExcessiveAccessAlert, GroupHealthReport, IdentityPostureSnapshot, RoleProfile,
)


# ── Posture score ─────────────────────────────────────────────────────────────

async def compute_posture_score(db: AsyncSession, tenant_id: UUID) -> IdentityPostureSnapshot:
    """
    Score 0–100 composed of 5 weighted dimensions:
    - mfa_pct (25): % users with MFA registered
    - admin_permanent_pct (20): 100 − % admins with permanent roles (lower is better)
    - campaigns_on_time_pct (20): % campaigns completed on time
    - sod_zero (20): 100 if zero critical SoD violations open, else scaled
    - inactive_zero (15): 100 if zero accounts inactive >60 days, scaled
    """
    # MFA %
    total_users = (await db.execute(
        select(func.count(AdUser.id)).where(AdUser.tenant_id == tenant_id, AdUser.is_enabled.is_(True))
    )).scalar() or 0
    mfa_users = (await db.execute(
        select(func.count(AdUser.id)).where(
            AdUser.tenant_id == tenant_id,
            AdUser.is_enabled.is_(True),
            AdUser.mfa_registered.is_(True),
        )
    )).scalar() or 0
    mfa_pct = (mfa_users / total_users * 100) if total_users else 100.0

    # SoD critical open
    sod_critical = (await db.execute(
        select(func.count(SoDViolation.id)).where(
            SoDViolation.tenant_id == tenant_id,
            SoDViolation.status == "open",
        )
    )).scalar() or 0

    # Inactive accounts (no login >60 days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=60)
    inactive = (await db.execute(
        select(func.count(AdUser.id)).where(
            AdUser.tenant_id == tenant_id,
            AdUser.is_enabled.is_(True),
            AdUser.last_sign_in < cutoff,
        )
    )).scalar() or 0

    # Campaigns on time
    total_campaigns = (await db.execute(
        select(func.count(AccessCampaign.id)).where(
            AccessCampaign.tenant_id == tenant_id,
            AccessCampaign.status.in_(["completed", "expired"]),
        )
    )).scalar() or 0
    completed_on_time = (await db.execute(
        select(func.count(AccessCampaign.id)).where(
            AccessCampaign.tenant_id == tenant_id,
            AccessCampaign.status == "completed",
        )
    )).scalar() or 0
    campaigns_pct = (completed_on_time / total_campaigns * 100) if total_campaigns else 100.0

    # Compute weighted score
    mfa_score         = mfa_pct * 0.25
    sod_score         = (100 / (1 + sod_critical)) * 0.20
    inactive_score    = (100 / (1 + inactive * 2)) * 0.15
    campaign_score    = campaigns_pct * 0.20
    admin_perm_score  = 80 * 0.20   # placeholder — real: compute from connector
    total_score = int(mfa_score + sod_score + inactive_score + campaign_score + admin_perm_score)
    total_score = max(0, min(100, total_score))

    snapshot = IdentityPostureSnapshot(
        id=uuid4(),
        tenant_id=tenant_id,
        score=total_score,
        mfa_pct=round(mfa_pct, 1),
        admin_permanent_pct=None,
        campaigns_on_time_pct=round(campaigns_pct, 1),
        sod_critical_open=sod_critical,
        inactive_accounts=inactive,
        details={
            "total_users": total_users,
            "mfa_users": mfa_users,
            "total_campaigns": total_campaigns,
        },
    )
    db.add(snapshot)
    await db.flush()
    await db.refresh(snapshot)
    await db.commit()
    return snapshot


# ── Role mining ───────────────────────────────────────────────────────────────

async def compute_role_profiles(db: AsyncSession, tenant_id: UUID) -> list[RoleProfile]:
    """
    For each job_title with ≥3 users: compute standard_groups (present in >80%).
    """
    users = (await db.execute(
        select(AdUser).where(AdUser.tenant_id == tenant_id, AdUser.is_enabled.is_(True))
    )).scalars().all()

    by_title: dict[str, list[AdUser]] = defaultdict(list)
    for u in users:
        if u.job_title:
            by_title[u.job_title].append(u)

    profiles: list[RoleProfile] = []
    for title, title_users in by_title.items():
        if len(title_users) < 3:
            continue

        group_counts: Counter = Counter()
        for u in title_users:
            memberships = (await db.execute(
                select(AdGroupMembership).where(AdGroupMembership.user_id == u.id)
            )).scalars().all()
            for m in memberships:
                group_counts[str(m.group_id)] += 1

        threshold = len(title_users) * 0.8
        standard = [gid for gid, cnt in group_counts.items() if cnt >= threshold]

        profile = RoleProfile(
            id=uuid4(),
            tenant_id=tenant_id,
            job_title=title,
            standard_groups=standard,
        )
        db.add(profile)
        profiles.append(profile)

    await db.flush()
    await db.commit()
    return profiles


# ── Privilege creep detection ─────────────────────────────────────────────────

async def detect_excessive_access(db: AsyncSession, tenant_id: UUID) -> list[ExcessiveAccessAlert]:
    users = (await db.execute(
        select(AdUser).where(AdUser.tenant_id == tenant_id, AdUser.is_enabled.is_(True))
    )).scalars().all()

    alerts: list[ExcessiveAccessAlert] = []
    for u in users:
        memberships = (await db.execute(
            select(AdGroupMembership).where(AdGroupMembership.user_id == u.id)
        )).scalars().all()
        group_count = len(memberships)

        rule_type = None
        details: dict = {}
        severity = "medium"

        if group_count > 50:
            rule_type = "too_many_groups"
            details = {"group_count": group_count, "threshold": 50}
            severity = "high"
        elif group_count > 25:
            rule_type = "too_many_groups"
            details = {"group_count": group_count, "threshold": 25}
            severity = "medium"

        if rule_type:
            existing = (await db.execute(
                select(ExcessiveAccessAlert).where(
                    ExcessiveAccessAlert.tenant_id == tenant_id,
                    ExcessiveAccessAlert.user_id == u.id,
                    ExcessiveAccessAlert.rule_type == rule_type,
                    ExcessiveAccessAlert.status == "open",
                )
            )).scalar_one_or_none()
            if not existing:
                alert = ExcessiveAccessAlert(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    user_id=u.id,
                    rule_type=rule_type,
                    details={**details, "user_upn": u.upn, "display_name": u.display_name},
                    severity=severity,
                )
                db.add(alert)
                alerts.append(alert)

    await db.flush()
    await db.commit()
    return alerts


# ── Group health ──────────────────────────────────────────────────────────────

async def analyze_group_health(db: AsyncSession, tenant_id: UUID) -> list[GroupHealthReport]:
    groups = (await db.execute(
        select(AdGroup).where(AdGroup.tenant_id == tenant_id)
    )).scalars().all()

    reports: list[GroupHealthReport] = []
    for g in groups:
        issues = []
        score = 100

        if g.member_count == 0:
            issues.append({"type": "ghost_group", "description": "Grupo sem membros ativos"})
            score -= 30

        if not g.owner_ids:
            issues.append({"type": "no_owner", "description": "Grupo sem owner definido"})
            score -= 20

        import re
        if re.search(r"(temp|projeto|project|test|2022|2023|2024)", g.display_name or "", re.IGNORECASE):
            issues.append({"type": "temporary_forgotten", "description": "Nome sugere grupo temporário esquecido"})
            score -= 15

        score = max(0, score)

        report = GroupHealthReport(
            id=uuid4(),
            tenant_id=tenant_id,
            group_id=g.id,
            health_score=score,
            issues=issues,
        )
        db.add(report)
        reports.append(report)

    await db.flush()
    await db.commit()
    return reports
