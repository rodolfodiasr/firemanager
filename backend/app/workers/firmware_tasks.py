"""Celery tasks for Firmware Intelligence (F40)."""
from __future__ import annotations

import asyncio

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger()


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@celery_app.task(name="app.workers.firmware_tasks.sync_nvd_all_vendors", bind=True, max_retries=2)
def sync_nvd_all_vendors(self):
    """Daily task: fetch CVEs from NVD for all supported vendors and upsert into DB."""
    async def _inner():
        from app.database import AsyncSessionLocal
        from app.services.firmware_service import sync_all_nvd_cves
        async with AsyncSessionLocal() as db:
            results = await sync_all_nvd_cves(db)
            log.info("nvd_sync_complete", totals=results)
            return results

    try:
        return _run(_inner())
    except Exception as exc:
        log.error("nvd_sync_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="app.workers.firmware_tasks.correlate_all", bind=True, max_retries=2)
def correlate_all(self):
    """Daily task: correlate all managed devices against the CVE database."""
    async def _inner():
        from app.database import AsyncSessionLocal
        from app.services.firmware_service import correlate_all_devices
        async with AsyncSessionLocal() as db:
            results = await correlate_all_devices(db)
            log.info("firmware_correlate_complete", device_count=len(results))
            return results

    try:
        return _run(_inner())
    except Exception as exc:
        log.error("correlate_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="app.workers.firmware_tasks.refresh_all_devices")
def refresh_all_devices(tenant_id: str | None = None):
    """Read firmware from every managed device and run correlation. Optionally scoped to a tenant."""
    async def _inner():
        from uuid import UUID
        from sqlalchemy import select
        from app.database import AsyncSessionLocal
        from app.models.device import Device
        from app.services.firmware_service import refresh_device_firmware as _refresh, correlate_device

        async with AsyncSessionLocal() as db:
            query = select(Device)
            if tenant_id:
                query = query.where(Device.tenant_id == UUID(tenant_id))

            result = await db.execute(query)
            devices = result.scalars().all()

            refreshed = 0
            for device in devices:
                try:
                    record = await _refresh(db, device)
                    if record:
                        await correlate_device(db, device)
                        refreshed += 1
                except Exception as exc:
                    log.warning("refresh_device_failed", device_id=str(device.id), error=str(exc))

            await db.commit()
            log.info("refresh_all_done", total=len(devices), refreshed=refreshed)
            return {"total": len(devices), "refreshed": refreshed}

    return _run(_inner())


@celery_app.task(name="app.workers.firmware_tasks.refresh_device_firmware")
def refresh_device_firmware(device_id: str):
    """On-demand task: read firmware version from a single device."""
    async def _inner():
        from uuid import UUID
        from sqlalchemy import select
        from app.database import AsyncSessionLocal
        from app.models.device import Device
        from app.services.firmware_service import refresh_device_firmware as _refresh, correlate_device
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Device).where(Device.id == UUID(device_id)))
            device = result.scalar_one_or_none()
            if not device:
                log.warning("refresh_firmware_device_not_found", device_id=device_id)
                return None
            record = await _refresh(db, device)
            if record:
                await correlate_device(db, device)
            await db.commit()
            return record.version if record else None

    return _run(_inner())
