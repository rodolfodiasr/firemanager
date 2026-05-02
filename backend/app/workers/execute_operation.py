import asyncio
from uuid import UUID

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(name="app.workers.execute_operation.execute", bind=True, max_retries=1)
def execute(self: object, operation_id: str) -> dict[str, str]:
    return asyncio.get_event_loop().run_until_complete(_async_execute(UUID(operation_id)))


async def _async_execute(operation_id: UUID) -> dict[str, str]:
    import app.models  # ensure all FK targets are registered
    from app.database import AsyncSessionLocal
    from app.services.operation_service import execute_operation

    async with AsyncSessionLocal() as db:
        operation = await execute_operation(db, operation_id)
        await db.commit()
        log.info("operation_executed", operation_id=str(operation_id), status=operation.status.value)
        return {"operation_id": str(operation_id), "status": operation.status.value}
