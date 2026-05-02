"""Celery task: periodic BookStack snapshot for all devices."""
import asyncio
from datetime import datetime, timezone

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(name="app.workers.bookstack_snapshot.run_bookstack_snapshots", bind=True, max_retries=1)
def run_bookstack_snapshots(self: object) -> dict[str, int]:
    """Hourly task: publish snapshots for tenants whose snapshot_hour matches current UTC hour."""
    return asyncio.get_event_loop().run_until_complete(_async_run_snapshots())


async def _async_run_snapshots() -> dict[str, int]:
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.device import Device
    from app.models.integration import Integration, IntegrationType
    from app.services.bookstack_service import publish_device_snapshot
    from app.utils.crypto import decrypt_credentials

    results = {"processed": 0, "updated": 0, "skipped": 0, "errors": 0}
    current_hour = datetime.now(timezone.utc).hour

    async with AsyncSessionLocal() as db:
        bs_result = await db.execute(
            select(Integration).where(
                Integration.type == IntegrationType.bookstack,
                Integration.is_active.is_(True),
            )
        )
        integrations = list(bs_result.scalars().all())

        if not integrations:
            log.info("bookstack_snapshot_skipped", reason="no_active_integrations")
            return results

        eligible_tenant_ids: set = set()
        for intg in integrations:
            config = decrypt_credentials(intg.encrypted_config)
            snapshot_enabled = config.get("snapshot_enabled", True)
            # snapshot_enabled may be stored as bool or string "true"/"false"
            if isinstance(snapshot_enabled, str):
                snapshot_enabled = snapshot_enabled.lower() not in ("false", "0", "")
            if not snapshot_enabled:
                log.debug("bookstack_snapshot_disabled", tenant_id=str(intg.tenant_id))
                results["skipped"] += 1
                continue
            snapshot_hour = int(config.get("snapshot_hour", 2))
            if current_hour != snapshot_hour:
                results["skipped"] += 1
                continue
            if intg.tenant_id:
                eligible_tenant_ids.add(intg.tenant_id)

        if not eligible_tenant_ids:
            log.info("bookstack_snapshot_no_eligible", current_hour=current_hour)
            return results

        dev_result = await db.execute(
            select(Device).where(Device.tenant_id.in_(eligible_tenant_ids))
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
