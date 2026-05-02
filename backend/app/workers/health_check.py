import asyncio
from datetime import datetime, timezone

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(name="app.workers.health_check.run_health_checks", bind=True, max_retries=3)
def run_health_checks(self: object) -> dict[str, int]:
    """Periodic task: checks connectivity for all active devices."""
    return asyncio.get_event_loop().run_until_complete(_async_health_checks())


async def _async_health_checks() -> dict[str, int]:
    import app.models  # ensure all models are registered in SQLAlchemy metadata
    from app.database import AsyncSessionLocal
    from app.models.device import Device, DeviceStatus
    from app.connectors.factory import CLI_VENDORS, get_connector, get_ssh_connector
    from sqlalchemy import select

    results = {"checked": 0, "online": 0, "offline": 0, "error": 0}

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Device))
        devices = list(result.scalars().all())

        for device in devices:
            try:
                if device.vendor in CLI_VENDORS:
                    connector = get_ssh_connector(device)
                else:
                    connector = get_connector(device)
                check_result = await connector.test_connection()
                if check_result.success:
                    device.status = DeviceStatus.online
                    fw = getattr(check_result, "firmware_version", None)
                    if fw:
                        device.firmware_version = fw
                    results["online"] += 1
                else:
                    device.status = DeviceStatus.offline
                    results["offline"] += 1
                device.last_seen = datetime.now(timezone.utc)
            except Exception as exc:
                device.status = DeviceStatus.error
                results["error"] += 1
                log.warning("health_check_failed", device_id=str(device.id), error=str(exc))

            results["checked"] += 1

        await db.commit()

    log.info("health_checks_completed", **results)
    return results
