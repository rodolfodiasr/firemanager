"""Celery task: daily automated compliance scan for all tenants.

For each tenant:
  1. Run server compliance checks (Wazuh SCA preferred, SSH fallback) for all servers
  2. Run network device compliance checks (REST/SSH) for all firewalls + switches
  3. Recompute Trust Scores (CIS / NIST / ISO / Eternity)
  4. Alert tenant admins by email if Eternity score drops ≥ 5 pts or falls below 60

Design decisions:
  - Per-item isolation: one failing device/server does not block the rest
  - Skip recently scanned: servers/devices with a report in the last 20h are skipped
    (prevents duplicate scans if the task runs twice due to worker restart)
  - Network devices in offline/error status are skipped (connection would fail anyway)
  - Trust Scores are always recomputed after the scan, even if no new reports were generated
"""
import asyncio
from datetime import datetime, timedelta, timezone

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger()

_SKIP_IF_SCANNED_WITHIN_H = 20   # skip if a report exists from the last N hours
_SCORE_DROP_ALERT_THRESHOLD = 5.0  # alert if Eternity drops this many points
_SCORE_LOW_ALERT_THRESHOLD  = 60.0  # alert if Eternity is below this value


@celery_app.task(
    name="app.workers.compliance_scan.run_compliance_scan",
    bind=True,
    soft_time_limit=3600,   # 1 hour soft limit
    time_limit=3900,        # 65 min hard limit
)
def run_compliance_scan(self: object) -> dict:
    """Entry point for Celery. Runs the async scan synchronously."""
    return asyncio.run(_async_compliance_scan())


async def _async_compliance_scan() -> dict:
    import app.models  # ensure all models registered
    from app.database import AsyncSessionLocal

    summary: dict = {
        "tenants": 0,
        "servers_scanned": 0,
        "devices_scanned": 0,
        "errors": 0,
        "scores_computed": 0,
        "alerts_sent": 0,
    }

    from app.models.tenant import Tenant
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        tenants_result = await db.execute(select(Tenant))
        tenants = list(tenants_result.scalars().all())

    log.info("compliance_scan_start", tenant_count=len(tenants))

    for tenant in tenants:
        try:
            tenant_result = await _scan_tenant(tenant.id, tenant.name)
            summary["tenants"]         += 1
            summary["servers_scanned"] += tenant_result.get("servers_scanned", 0)
            summary["devices_scanned"] += tenant_result.get("devices_scanned", 0)
            summary["errors"]          += tenant_result.get("errors", 0)
            summary["scores_computed"] += 1
            summary["alerts_sent"]     += tenant_result.get("alert_sent", 0)
        except Exception as exc:
            summary["errors"] += 1
            log.error("tenant_scan_failed", tenant_id=str(tenant.id), error=str(exc))

    log.info("compliance_scan_done", **summary)
    return summary


async def _scan_tenant(tenant_id, tenant_name: str) -> dict:
    from app.database import AsyncSessionLocal

    result = {
        "servers_scanned": 0,
        "devices_scanned": 0,
        "errors": 0,
        "alert_sent": 0,
    }

    async with AsyncSessionLocal() as db:
        # ── 1. Snapshot existing Trust Scores (for drop detection later) ──────
        from app.services import trust_score_service
        prev_scores = await trust_score_service.get_latest(db, tenant_id)
        prev_map = {s.framework: s.score_pct for s in prev_scores}

        # ── 2. Server compliance scan ─────────────────────────────────────────
        srv_result = await _scan_servers(db, tenant_id)
        result["servers_scanned"] += srv_result["scanned"]
        result["errors"]          += srv_result["errors"]

        # ── 3. Network device compliance scan ─────────────────────────────────
        dev_result = await _scan_devices(db, tenant_id)
        result["devices_scanned"] += dev_result["scanned"]
        result["errors"]          += dev_result["errors"]

        # ── 4. Recompute Trust Scores ─────────────────────────────────────────
        new_scores = await trust_score_service.compute_all(db, tenant_id, save=True)
        new_map = {s.framework: s.score_pct for s in new_scores}

        # ── 5. Alert if needed ────────────────────────────────────────────────
        new_e  = new_map.get("eternity", 0.0)
        prev_e = prev_map.get("eternity")
        drop   = round((prev_e - new_e), 1) if prev_e is not None else 0.0

        should_alert = (
            (prev_e is not None and drop >= _SCORE_DROP_ALERT_THRESHOLD)
            or new_e < _SCORE_LOW_ALERT_THRESHOLD
        )

        if should_alert:
            admin_emails = await _get_admin_emails(db, tenant_id)
            if admin_emails:
                _send_alert(
                    to_emails=admin_emails,
                    tenant_name=tenant_name,
                    prev_map=prev_map,
                    new_map=new_map,
                    scan_summary={
                        "servers_scanned": result["servers_scanned"],
                        "devices_scanned": result["devices_scanned"],
                        "errors":          result["errors"],
                    },
                )
                result["alert_sent"] = 1
                log.info("score_alert_sent",
                         tenant=tenant_name, prev=prev_e, new=new_e, drop=drop,
                         recipients=len(admin_emails))

    log.info("tenant_scan_done", tenant=tenant_name, **result)
    return result


async def _scan_servers(db, tenant_id) -> dict:
    """Scan all servers for the tenant. Returns {scanned, errors}."""
    from app.models.server import Server
    from app.models.compliance import ComplianceReport
    from app.services import compliance_service
    from sqlalchemy import select, and_

    result = {"scanned": 0, "errors": 0}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_SKIP_IF_SCANNED_WITHIN_H)

    servers_r = await db.execute(select(Server).where(Server.tenant_id == tenant_id))
    servers = list(servers_r.scalars().all())

    for server in servers:
        # Skip if recently scanned
        recent_r = await db.execute(
            select(ComplianceReport.id)
            .where(
                and_(
                    ComplianceReport.tenant_id == tenant_id,
                    ComplianceReport.server_id == server.id,
                    ComplianceReport.created_at >= cutoff,
                )
            )
            .limit(1)
        )
        if recent_r.scalar():
            log.debug("server_scan_skipped_recent", server=server.name)
            continue

        try:
            await compliance_service.generate_report(
                db=db,
                tenant_id=tenant_id,
                server_id=server.id,
            )
            result["scanned"] += 1
            log.info("server_scanned", server=server.name, tenant_id=str(tenant_id))
        except Exception as exc:
            result["errors"] += 1
            log.warning("server_scan_failed", server=server.name, error=str(exc))

    return result


async def _scan_devices(db, tenant_id) -> dict:
    """Scan all non-offline network devices for the tenant. Returns {scanned, errors}."""
    from app.models.device import Device, DeviceCategory, DeviceStatus
    from app.models.compliance import ComplianceReport
    from app.services import network_compliance_service
    from sqlalchemy import select, and_, or_

    result = {"scanned": 0, "errors": 0}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_SKIP_IF_SCANNED_WITHIN_H)

    # Only scan network-relevant categories; skip offline devices
    devices_r = await db.execute(
        select(Device).where(
            and_(
                Device.tenant_id == tenant_id,
                Device.category.in_([
                    DeviceCategory.firewall,
                    DeviceCategory.switch,
                    DeviceCategory.routing,
                ]),
                Device.status.in_([
                    DeviceStatus.online,
                    DeviceStatus.unknown,  # not yet health-checked
                ]),
            )
        )
    )
    devices = list(devices_r.scalars().all())

    for device in devices:
        # Skip if recently scanned
        recent_r = await db.execute(
            select(ComplianceReport.id)
            .where(
                and_(
                    ComplianceReport.tenant_id == tenant_id,
                    ComplianceReport.device_id == device.id,
                    ComplianceReport.created_at >= cutoff,
                )
            )
            .limit(1)
        )
        if recent_r.scalar():
            log.debug("device_scan_skipped_recent", device=device.name)
            continue

        try:
            await network_compliance_service.generate_report(
                db=db,
                tenant_id=tenant_id,
                device_id=device.id,
            )
            result["scanned"] += 1
            log.info("device_scanned", device=device.name, vendor=device.vendor.value)
        except Exception as exc:
            result["errors"] += 1
            log.warning("device_scan_failed", device=device.name, error=str(exc))

    return result


async def _get_admin_emails(db, tenant_id) -> list[str]:
    """Return email addresses of all admin-role users in the tenant."""
    from app.models.user import User
    from app.models.user_tenant_role import UserTenantRole
    from sqlalchemy import select

    result = await db.execute(
        select(User.email)
        .join(UserTenantRole, UserTenantRole.user_id == User.id)
        .where(
            UserTenantRole.tenant_id == tenant_id,
            UserTenantRole.role == "admin",
        )
    )
    return [row[0] for row in result.fetchall() if row[0]]


def _send_alert(
    to_emails: list[str],
    tenant_name: str,
    prev_map: dict,
    new_map: dict,
    scan_summary: dict,
) -> None:
    from app.utils.email import send_score_alert_email
    from app.config import settings

    def _pair(fw: str) -> dict:
        return {"prev": prev_map.get(fw), "new": new_map.get(fw, 0.0)}

    send_score_alert_email(
        to_emails=to_emails,
        tenant_name=tenant_name,
        scores={
            "eternity": _pair("eternity"),
            "cis":      _pair("cis_benchmark"),
            "nist":     _pair("nist_csf"),
            "iso":      _pair("iso_27001"),
        },
        scan_summary=scan_summary,
        frontend_url=getattr(settings, "frontend_url", "http://localhost:5173"),
    )
