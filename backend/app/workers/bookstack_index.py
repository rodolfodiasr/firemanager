"""Celery task: index BookStack pages into pgvector embeddings."""
import asyncio
import re

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(
    name="app.workers.bookstack_index.run_bookstack_indexing",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def run_bookstack_indexing(self: object) -> dict[str, int]:
    """Periodic task: crawl BookStack and keep pgvector embeddings up to date."""
    return asyncio.get_event_loop().run_until_complete(_async_index())


async def _async_index() -> dict[str, int]:
    from sqlalchemy import delete, select
    from app.config import settings
    import app.models  # ensure all FK targets are registered
    from app.database import AsyncSessionLocal
    from app.models.bookstack_embedding import BookstackEmbedding
    from app.models.integration import Integration, IntegrationType
    from app.services.embedding_service import upsert_page_embeddings
    from app.utils.crypto import decrypt_credentials

    results = {"integrations": 0, "pages_checked": 0, "chunks_written": 0,
               "skipped": 0, "errors": 0}

    if not settings.openai_api_key:
        log.warning("bookstack_index_skipped", reason="openai_api_key_not_configured")
        return results

    async with AsyncSessionLocal() as db:
        bs_result = await db.execute(
            select(Integration).where(
                Integration.type == IntegrationType.bookstack,
                Integration.is_active.is_(True),
            )
        )
        integrations = list(bs_result.scalars().all())

        for intg in integrations:
            results["integrations"] += 1
            config = decrypt_credentials(intg.encrypted_config)
            tenant_id = intg.tenant_id
            book_id = config.get("book_id")

            if not book_id or not tenant_id:
                continue

            try:
                from app.connectors.bookstack import connector_from_config
                connector = connector_from_config(config)
                chapter_id = config.get("chapter_id")
                if chapter_id:
                    pages = await connector.list_pages_in_chapter(int(chapter_id))
                else:
                    pages = await connector.list_pages_in_book(int(book_id))
                live_page_ids: set[int] = set()

                for page in pages:
                    results["pages_checked"] += 1
                    try:
                        full = await connector.get_page(page.id)
                        content = full.markdown or _strip_html(full.html)
                        if not content.strip():
                            results["skipped"] += 1
                            continue

                        page_url = (
                            f"{config['base_url'].rstrip('/')}"
                            f"/books/{book_id}/pages/{page.slug}"
                        )
                        n = await upsert_page_embeddings(
                            db=db,
                            tenant_id=tenant_id,
                            integration_id=intg.id,
                            bs_page_id=page.id,
                            bs_page_name=page.name,
                            bs_page_url=page_url,
                            content=content,
                        )
                        live_page_ids.add(page.id)
                        results["chunks_written"] += n
                        if n:
                            log.debug("bs_page_indexed", page=page.name, chunks=n)
                        else:
                            results["skipped"] += 1

                    except Exception as exc:
                        results["errors"] += 1
                        log.warning("bs_page_error", page_id=page.id, error=str(exc))

                # Remove embeddings for pages deleted from BookStack
                if live_page_ids:
                    await db.execute(
                        delete(BookstackEmbedding).where(
                            BookstackEmbedding.integration_id == intg.id,
                            BookstackEmbedding.bs_page_id.notin_(live_page_ids),
                        )
                    )

            except Exception as exc:
                results["errors"] += 1
                log.warning("bs_integration_error", integration_id=str(intg.id), error=str(exc))

        await db.commit()

    log.info("bookstack_indexing_done", **results)
    return results


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()
