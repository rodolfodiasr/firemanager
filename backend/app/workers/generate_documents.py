import asyncio
from uuid import UUID

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(name="app.workers.generate_documents.generate", bind=True)
def generate(self: object, operation_id: str) -> dict[str, int]:
    return asyncio.get_event_loop().run_until_complete(_async_generate(UUID(operation_id)))


async def _async_generate(operation_id: UUID) -> dict[str, int]:
    import app.models  # ensure all FK targets are registered
    from app.database import AsyncSessionLocal
    from app.services.document_service import generate_documents_for_operation

    async with AsyncSessionLocal() as db:
        docs = await generate_documents_for_operation(db, operation_id)
        await db.commit()
        log.info("documents_generated", operation_id=str(operation_id), count=len(docs))
        return {"operation_id": str(operation_id), "documents_generated": len(docs)}
