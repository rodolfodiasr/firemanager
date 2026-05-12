"""Firmware Intelligence — orchestration layer: refresh, CVE sync, correlation."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.firmware import DeviceFirmwareVersion, FirmwareCVE, DeviceFirmwareVulnerability
from app.schemas.firmware import DeviceFirmwareSummary, FirmwareRiskSummary
from app.services.nvd_service import (
    VENDOR_NVD_MAP,
    fetch_cves_for_vendor,
    version_is_affected,
)

log = structlog.get_logger()

_SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}


# ── Firmware version refresh for a single device ──────────────────────────────

async def refresh_device_firmware(db: AsyncSession, device: Device) -> DeviceFirmwareVersion | None:
    from app.services.firmware_reader import read_firmware

    info = await read_firmware(device)
    if not info:
        return None

    record = DeviceFirmwareVersion(
        device_id=device.id,
        version=info.version,
        vendor_label=info.vendor_label,
        model=info.model,
        build=info.build,
        read_method=info.read_method,
        raw_output=info.raw,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)

    # Also update the device's cached firmware_version field
    device.firmware_version = info.version  # type: ignore[assignment]
    db.add(device)
    await db.flush()

    return record


# ── NVD sync ──────────────────────────────────────────────────────────────────

async def sync_nvd_cves(db: AsyncSession, vendor_key: str) -> int:
    """Fetch CVEs for a vendor from NVD and upsert into firmware_cves."""
    cves = await fetch_cves_for_vendor(vendor_key)
    upserted = 0

    for cve_data in cves:
        cve_id = cve_data["cve_id"]
        result = await db.execute(select(FirmwareCVE).where(FirmwareCVE.cve_id == cve_id))
        existing = result.scalar_one_or_none()

        if existing:
            for field, value in cve_data.items():
                setattr(existing, field, value)
            db.add(existing)
        else:
            db.add(FirmwareCVE(**cve_data))

        upserted += 1

    await db.flush()
    log.info("nvd_sync_done", vendor=vendor_key, count=upserted)
    return upserted


async def sync_all_nvd_cves(db: AsyncSession) -> dict[str, int]:
    """Run NVD sync for all supported vendors."""
    results: dict[str, int] = {}
    for vendor_key in VENDOR_NVD_MAP:
        try:
            count = await sync_nvd_cves(db, vendor_key)
            results[vendor_key] = count
        except Exception as exc:
            log.error("nvd_sync_failed", vendor=vendor_key, error=str(exc))
            results[vendor_key] = 0
    await db.commit()
    return results


# ── CVE correlation ───────────────────────────────────────────────────────────

async def correlate_device(db: AsyncSession, device: Device) -> int:
    """Compare device's current firmware version against CVE database. Returns vuln count."""
    vendor_key = device.vendor.value if hasattr(device.vendor, "value") else str(device.vendor)
    mapping = VENDOR_NVD_MAP.get(vendor_key)
    if not mapping:
        return 0

    # Get latest firmware version for this device
    result = await db.execute(
        select(DeviceFirmwareVersion)
        .where(DeviceFirmwareVersion.device_id == device.id)
        .order_by(DeviceFirmwareVersion.read_at.desc())
        .limit(1)
    )
    fw_record = result.scalar_one_or_none()
    if not fw_record:
        return 0

    device_version = fw_record.version

    # Get all CVEs for this vendor/product
    result = await db.execute(
        select(FirmwareCVE).where(
            and_(
                FirmwareCVE.vendor == mapping["vendor"],
                FirmwareCVE.product == mapping["product"],
            )
        )
    )
    cves = result.scalars().all()

    detected = 0
    for cve in cves:
        if not version_is_affected(device_version, cve.affected_versions):
            continue

        # Upsert vulnerability record
        result2 = await db.execute(
            select(DeviceFirmwareVulnerability).where(
                and_(
                    DeviceFirmwareVulnerability.device_id == device.id,
                    DeviceFirmwareVulnerability.cve_id == cve.cve_id,
                )
            )
        )
        vuln = result2.scalar_one_or_none()
        if not vuln:
            vuln = DeviceFirmwareVulnerability(
                device_id=device.id,
                cve_id=cve.cve_id,
                device_version=device_version,
                status="open",
            )
            db.add(vuln)
            detected += 1
        else:
            # Update version if device was upgraded
            if vuln.device_version != device_version and vuln.status == "open":
                vuln.device_version = device_version
                db.add(vuln)

    await db.flush()
    return detected


async def correlate_all_devices(db: AsyncSession) -> dict[str, int]:
    """Run correlation for all devices that have firmware version records."""
    result = await db.execute(
        select(Device).where(Device.firmware_version.isnot(None))
    )
    devices = result.scalars().all()

    results: dict[str, int] = {}
    for device in devices:
        try:
            count = await correlate_device(db, device)
            results[str(device.id)] = count
        except Exception as exc:
            log.error("correlate_failed", device_id=str(device.id), error=str(exc))
    await db.commit()
    return results


# ── Query helpers ─────────────────────────────────────────────────────────────

async def get_device_firmware_summary(
    db: AsyncSession, device_id: UUID
) -> DeviceFirmwareSummary:
    # Latest version
    result = await db.execute(
        select(DeviceFirmwareVersion)
        .where(DeviceFirmwareVersion.device_id == device_id)
        .order_by(DeviceFirmwareVersion.read_at.desc())
        .limit(1)
    )
    fw = result.scalar_one_or_none()

    # Vulnerability counts by severity
    result2 = await db.execute(
        select(DeviceFirmwareVulnerability.cve_id)
        .where(
            and_(
                DeviceFirmwareVulnerability.device_id == device_id,
                DeviceFirmwareVulnerability.status == "open",
            )
        )
    )
    open_cve_ids = [row[0] for row in result2.fetchall()]
    open_count = len(open_cve_ids)

    critical = high = 0
    worst = "UNKNOWN"
    if open_cve_ids:
        result3 = await db.execute(
            select(FirmwareCVE.severity).where(FirmwareCVE.cve_id.in_(open_cve_ids))
        )
        severities = [row[0] for row in result3.fetchall()]
        critical = sum(1 for s in severities if s == "CRITICAL")
        high = sum(1 for s in severities if s == "HIGH")
        if severities:
            worst = max(severities, key=lambda s: _SEVERITY_ORDER.get(s, 0))

    return DeviceFirmwareSummary(
        device_id=device_id,
        current_version=fw.version if fw else None,
        last_read_at=fw.read_at if fw else None,
        open_cves=open_count,
        critical_cves=critical,
        high_cves=high,
        worst_severity=worst,
    )


async def get_firmware_risk_summary(
    db: AsyncSession, tenant_id: UUID
) -> FirmwareRiskSummary:
    # Devices in tenant
    result = await db.execute(
        select(Device.id).where(Device.tenant_id == tenant_id)
    )
    device_ids = [row[0] for row in result.fetchall()]

    if not device_ids:
        return FirmwareRiskSummary(
            devices_with_vulns=0, total_open_cves=0,
            critical_cves=0, high_cves=0, top_affected=[],
        )

    # Open vulns across all devices
    result2 = await db.execute(
        select(
            DeviceFirmwareVulnerability.device_id,
            DeviceFirmwareVulnerability.cve_id,
        ).where(
            and_(
                DeviceFirmwareVulnerability.device_id.in_(device_ids),
                DeviceFirmwareVulnerability.status == "open",
            )
        )
    )
    vuln_rows = result2.fetchall()

    if not vuln_rows:
        return FirmwareRiskSummary(
            devices_with_vulns=0, total_open_cves=0,
            critical_cves=0, high_cves=0, top_affected=[],
        )

    cve_ids = list({row[1] for row in vuln_rows})
    result3 = await db.execute(
        select(FirmwareCVE.cve_id, FirmwareCVE.severity).where(
            FirmwareCVE.cve_id.in_(cve_ids)
        )
    )
    severity_map = {row[0]: row[1] for row in result3.fetchall()}

    total_open = len(vuln_rows)
    critical = sum(1 for _, cid in vuln_rows if severity_map.get(cid) == "CRITICAL")
    high = sum(1 for _, cid in vuln_rows if severity_map.get(cid) == "HIGH")

    # Devices that have vulns
    devices_with_vulns = len({row[0] for row in vuln_rows})

    # Top 5 most affected devices
    from collections import Counter
    device_cve_counts: Counter = Counter(row[0] for row in vuln_rows)
    top_device_ids = [did for did, _ in device_cve_counts.most_common(5)]

    top_affected = []
    for did in top_device_ids:
        summary = await get_device_firmware_summary(db, did)
        top_affected.append(summary)

    return FirmwareRiskSummary(
        devices_with_vulns=devices_with_vulns,
        total_open_cves=total_open,
        critical_cves=critical,
        high_cves=high,
        top_affected=top_affected,
    )
