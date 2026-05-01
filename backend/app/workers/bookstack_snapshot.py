"""Celery task: periodic BookStack snapshot for all devices."""
import asyncio

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(name="app.workers.bookstack_snapshot.run_bookstack_snapshots", bind=True, max_retries=1)
def run_bookstack_snapshots(self: object) -> dict[str, int]:
    """Daily task: publish a snapshot of each device's current state to BookStack."""
    return asyncio.get_event_loop().run_until_complete(_async_run_snapshots())


async def _async_run_snapshots() -> dict[str, int]:
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.device import Device
    from app.models.integration import Integration, IntegrationType
    from app.services.bookstack_service import publish_device_snapshot

    results = {"processed": 0, "updated": 0, "skipped": 0, "errors": 0}

    async with AsyncSessionLocal() as db:
        # Only process tenants that have an active BookStack integration
        bs_result = await db.execute(
            select(Integration.tenant_id).where(
                Integration.type == IntegrationType.bookstack,
                Integration.is_active.is_(True),
            )
        )
        tenant_ids = {row.tenant_id for row in bs_result}

        if not tenant_ids:
            log.info("bookstack_snapshot_skipped", reason="no_active_integrations")
            return results

        # Load all devices belonging to those tenants
        dev_result = await db.execute(
            select(Device).where(Device.tenant_id.in_(tenant_ids))
        )
        devices = list(dev_result.scalars().all())

        for device in devices:
            results["processed"] += 1
            try:
                snapshot_page_id_before = device.bookstack_snapshot_page_id
                await publish_device_snapshot(db, device)
                results["updated"] += 1
                log.info(
                    "bookstack_snapshot_ok",
                    device_id=str(device.id),
                    device_name=device.name,
                    created=device.bookstack_snapshot_page_id != snapshot_page_id_before,
                )
            except Exception as exc:
                results["errors"] += 1
                log.warning(
                    "bookstack_snapshot_error",
                    device_id=str(device.id),
                    device_name=device.name,
                    error=str(exc),
                )

        await db.commit()

    log.info("bookstack_snapshots_completed", **results)
    return results
