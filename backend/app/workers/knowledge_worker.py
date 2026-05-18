"""Celery worker — Fase 19: Knowledge document indexing."""
import asyncio
import logging

from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.knowledge_worker.process_knowledge_document",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def process_knowledge_document(self, document_id: str) -> dict:
    """Index a knowledge document in background (chunk + embed + store)."""
    return asyncio.run(_async_process(document_id))


async def _async_process(document_id: str) -> dict:
    import app.models  # noqa: F401 — register all FK targets
    from uuid import UUID

    from app.database import AsyncSessionLocal
    from app.services.knowledge_service import index_document

    async with AsyncSessionLocal() as db:
        try:
            n = await index_document(db, UUID(document_id))
            log.info("knowledge_worker done document=%s chunks=%d", document_id, n)
            return {"document_id": document_id, "chunks": n, "status": "indexed"}
        except Exception as exc:
            log.exception("knowledge_worker failed document=%s: %s", document_id, exc)
            return {"document_id": document_id, "chunks": 0, "status": "failed", "error": str(exc)}
