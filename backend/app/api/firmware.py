"""Fase 40 — Firmware Intelligence API."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.device import Device
from app.models.firmware import DeviceFirmwareVersion, FirmwareCVE, DeviceFirmwareVulnerability
from app.schemas.firmware import (
    DeviceFirmwareSummary,
    FirmwareCVERead,
    FirmwareRiskSummary,
    FirmwareVersionRead,
    FirmwareVulnAccept,
    FirmwareVulnRead,
)

router = APIRouter()

CtxDep = Annotated[TenantContext, Depends(get_tenant_context)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


def _assert_device_tenant(device: Device | None, tenant_id: UUID) -> Device:
    if not device or device.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Device não encontrado")
    return device


# ── Per-device endpoints ──────────────────────────────────────────────────────

@router.get("/devices/{device_id}/firmware/summary", response_model=DeviceFirmwareSummary)
async def get_device_firmware_summary(device_id: UUID, db: DbDep, ctx: CtxDep):
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = _assert_device_tenant(result.scalar_one_or_none(), ctx.tenant.id)

    from app.services.firmware_service import get_device_firmware_summary
    return await get_device_firmware_summary(db, device.id)


@router.get("/devices/{device_id}/firmware/versions", response_model=list[FirmwareVersionRead])
async def list_firmware_versions(device_id: UUID, db: DbDep, ctx: CtxDep):
    result = await db.execute(select(Device).where(Device.id == device_id))
    _assert_device_tenant(result.scalar_one_or_none(), ctx.tenant.id)

    r2 = await db.execute(
        select(DeviceFirmwareVersion)
        .where(DeviceFirmwareVersion.device_id == device_id)
        .order_by(DeviceFirmwareVersion.read_at.desc())
        .limit(20)
    )
    return r2.scalars().all()


@router.get("/devices/{device_id}/firmware/vulnerabilities", response_model=list[FirmwareVulnRead])
async def list_device_vulnerabilities(
    device_id: UUID, db: DbDep, ctx: CtxDep, status: str = "open"
):
    result = await db.execute(select(Device).where(Device.id == device_id))
    _assert_device_tenant(result.scalar_one_or_none(), ctx.tenant.id)

    r2 = await db.execute(
        select(DeviceFirmwareVulnerability).where(
            and_(
                DeviceFirmwareVulnerability.device_id == device_id,
                DeviceFirmwareVulnerability.status == status,
            )
        ).order_by(DeviceFirmwareVulnerability.detected_at.desc())
    )
    vulns = r2.scalars().all()

    # Enrich with CVE data
    cve_ids = [v.cve_id for v in vulns]
    cve_map: dict[str, FirmwareCVE] = {}
    if cve_ids:
        r3 = await db.execute(select(FirmwareCVE).where(FirmwareCVE.cve_id.in_(cve_ids)))
        for cve in r3.scalars():
            cve_map[cve.cve_id] = cve

    results = []
    for vuln in vulns:
        cve_obj = cve_map.get(vuln.cve_id)
        vuln_dict = {
            "id": vuln.id,
            "device_id": vuln.device_id,
            "cve_id": vuln.cve_id,
            "device_version": vuln.device_version,
            "detected_at": vuln.detected_at,
            "status": vuln.status,
            "accepted_by": vuln.accepted_by,
            "accepted_reason": vuln.accepted_reason,
            "patched_at": vuln.patched_at,
            "cve": FirmwareCVERead.model_validate(cve_obj) if cve_obj else None,
        }
        results.append(FirmwareVulnRead(**vuln_dict))
    return results


@router.post("/devices/{device_id}/firmware/refresh")
async def trigger_firmware_refresh(device_id: UUID, db: DbDep, ctx: CtxDep):
    """Enqueue a firmware version read + CVE correlation for a single device."""
    result = await db.execute(select(Device).where(Device.id == device_id))
    _assert_device_tenant(result.scalar_one_or_none(), ctx.tenant.id)

    from app.workers.firmware_tasks import refresh_device_firmware
    task = refresh_device_firmware.delay(str(device_id))
    return {"task_id": task.id, "status": "queued"}


@router.patch("/firmware/vulnerabilities/{vuln_id}/accept")
async def accept_risk(vuln_id: UUID, body: FirmwareVulnAccept, db: DbDep, ctx: CtxDep):
    """Mark a vulnerability as accepted risk (analyst decision)."""
    result = await db.execute(
        select(DeviceFirmwareVulnerability).where(DeviceFirmwareVulnerability.id == vuln_id)
    )
    vuln = result.scalar_one_or_none()
    if not vuln:
        raise HTTPException(status_code=404, detail="Vulnerabilidade não encontrada")

    # Verify device belongs to tenant
    result2 = await db.execute(select(Device).where(Device.id == vuln.device_id))
    _assert_device_tenant(result2.scalar_one_or_none(), ctx.tenant.id)

    vuln.status = "accepted"
    vuln.accepted_by = ctx.user.id
    vuln.accepted_reason = body.reason
    db.add(vuln)
    await db.commit()
    await db.refresh(vuln)
    return {"status": "accepted"}


# ── Tenant-wide endpoints ─────────────────────────────────────────────────────

@router.post("/firmware/refresh-all")
async def trigger_refresh_all(db: DbDep, ctx: CtxDep):
    """Enqueue firmware version read + CVE correlation for ALL devices of this tenant."""
    from app.workers.firmware_tasks import refresh_all_devices
    task = refresh_all_devices.delay(str(ctx.tenant.id))
    return {"task_id": task.id, "status": "queued", "message": "Refresh enfileirado para todos os devices do tenant"}


@router.get("/firmware/risk-summary", response_model=FirmwareRiskSummary)
async def get_firmware_risk_summary(db: DbDep, ctx: CtxDep):
    from app.services.firmware_service import get_firmware_risk_summary
    return await get_firmware_risk_summary(db, ctx.tenant.id)


@router.get("/firmware/cves", response_model=list[FirmwareCVERead])
async def list_cves(
    db: DbDep, ctx: CtxDep, vendor: str | None = None, severity: str | None = None
):
    query = select(FirmwareCVE)
    if vendor:
        query = query.where(FirmwareCVE.vendor == vendor)
    if severity:
        query = query.where(FirmwareCVE.severity == severity)
    query = query.order_by(FirmwareCVE.cvss_v3.desc().nullslast()).limit(200)
    result = await db.execute(query)
    return result.scalars().all()
