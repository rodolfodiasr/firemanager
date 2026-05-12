"""DocPublisher — orquestra extração, sanitização e publicação no BookStack."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import AssistantMessage, AssistantSession
from app.models.doc_draft import AssistantDocDraft
from app.services import doc_extractor, doc_sanitizer
from app.services.integration_service import resolve_integration
from app.models.integration import IntegrationType

log = logging.getLogger(__name__)


# ── Geração de rascunho ───────────────────────────────────────────────────────

async def generate_draft(
    db: AsyncSession,
    session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
) -> AssistantDocDraft:
    """Lê a sessão, extrai conhecimento, sanitiza e persiste como draft."""
    # Carrega sessão
    result = await db.execute(
        select(AssistantSession).where(
            AssistantSession.id == session_id,
            AssistantSession.tenant_id == tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise ValueError("Sessão não encontrada.")

    # Carrega mensagens
    result = await db.execute(
        select(AssistantMessage)
        .where(AssistantMessage.session_id == session_id)
        .order_by(AssistantMessage.created_at)
    )
    messages = list(result.scalars().all())

    # Extrai conhecimento via Claude
    data = await doc_extractor.extract_knowledge(session, messages)
    raw_content = doc_extractor.render_markdown(data, session)

    # Sanitiza
    sanitized_content, warnings = doc_sanitizer.sanitize(raw_content)

    # Busca documentos similares no BookStack (não bloqueia em caso de falha)
    similar = await _find_similar_docs(db, tenant_id, sanitized_content)

    # Persiste draft
    draft = AssistantDocDraft(
        session_id=session_id,
        tenant_id=tenant_id,
        created_by=user_id,
        title=data.get("title") or session.title or "Documentação Técnica",
        content=sanitized_content,
        status="draft",
        review_deadline=datetime.now(timezone.utc) + timedelta(hours=48),
        sanitizer_warnings=warnings,
        similar_docs=similar,
    )
    db.add(draft)
    await db.flush()
    await db.refresh(draft)
    return draft


# ── Publicação no BookStack ───────────────────────────────────────────────────

async def publish_draft(
    db: AsyncSession,
    draft_id: UUID,
    tenant_id: UUID,
) -> AssistantDocDraft:
    """Publica o draft aprovado no BookStack e atualiza status para 'published'."""
    result = await db.execute(
        select(AssistantDocDraft).where(
            AssistantDocDraft.id == draft_id,
            AssistantDocDraft.tenant_id == tenant_id,
        )
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise ValueError("Rascunho não encontrado.")
    if draft.status == "published":
        raise ValueError("Rascunho já publicado.")

    config = await resolve_integration(db, IntegrationType.bookstack, tenant_id)
    if not config:
        raise ValueError("Integração BookStack não configurada para este tenant.")

    from app.connectors.bookstack import connector_from_config
    connector = connector_from_config(config)

    book_id = int(config.get("book_id", 0))
    if not book_id:
        raise ValueError("book_id não configurado na integração BookStack.")

    chapter_id = config.get("doc_chapter_id")
    if chapter_id:
        chapter_id = int(chapter_id)

    page = await connector.create_page(
        book_id=book_id,
        name=draft.title,
        markdown=draft.content,
        chapter_id=chapter_id,
    )

    draft.bookstack_page_id = page.id
    draft.bookstack_page_url = f"{config['base_url']}/books/{book_id}/page/{page.slug}"
    draft.status = "published"

    await db.flush()
    await db.refresh(draft)

    # Dispara reindexação do RAG em background
    _schedule_rag_reindex(tenant_id, page.id)

    return draft


def _schedule_rag_reindex(tenant_id: UUID, page_id: int) -> None:
    """Enfileira task Celery para reindexar a página publicada no RAG (F19)."""
    try:
        from app.workers.bookstack_index import reindex_single_page
        reindex_single_page.delay(str(tenant_id), page_id)
    except Exception:
        # Worker indisponível não bloqueia a publicação
        pass


# ── Aprovação e rejeição ──────────────────────────────────────────────────────

async def approve_draft(
    db: AsyncSession,
    draft_id: UUID,
    tenant_id: UUID,
) -> AssistantDocDraft:
    draft = await _get_draft(db, draft_id, tenant_id)
    draft.status = "approved"
    await db.flush()
    await db.refresh(draft)
    return draft


async def reject_draft(
    db: AsyncSession,
    draft_id: UUID,
    tenant_id: UUID,
) -> AssistantDocDraft:
    draft = await _get_draft(db, draft_id, tenant_id)
    draft.status = "rejected"
    await db.flush()
    await db.refresh(draft)
    return draft


async def update_draft_content(
    db: AsyncSession,
    draft_id: UUID,
    tenant_id: UUID,
    title: str | None,
    content: str | None,
) -> AssistantDocDraft:
    draft = await _get_draft(db, draft_id, tenant_id)
    if draft.status == "published":
        raise ValueError("Não é possível editar um rascunho já publicado.")
    if title is not None:
        draft.title = title.strip()
    if content is not None:
        sanitized, warnings = doc_sanitizer.sanitize(content)
        draft.content = sanitized
        draft.sanitizer_warnings = warnings
    await db.flush()
    await db.refresh(draft)
    return draft


# ── Listagem ──────────────────────────────────────────────────────────────────

async def list_drafts(
    db: AsyncSession,
    tenant_id: UUID,
    status: str | None = None,
) -> list[AssistantDocDraft]:
    q = select(AssistantDocDraft).where(
        AssistantDocDraft.tenant_id == tenant_id
    ).order_by(AssistantDocDraft.created_at.desc())
    if status:
        q = q.where(AssistantDocDraft.status == status)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_draft(
    db: AsyncSession,
    draft_id: UUID,
    tenant_id: UUID,
) -> AssistantDocDraft | None:
    result = await db.execute(
        select(AssistantDocDraft).where(
            AssistantDocDraft.id == draft_id,
            AssistantDocDraft.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


# ── Similaridade semântica ────────────────────────────────────────────────────

_SIMILARITY_THRESHOLD = 0.75
_SIMILARITY_TOP_K = 3


async def _find_similar_docs(
    db: AsyncSession,
    tenant_id: UUID,
    content: str,
) -> list[dict]:
    """Busca páginas similares no BookStack via pgvector (cosine similarity).

    Retorna lista de {bs_page_id, title, url, similarity} ordenada por relevância.
    Retorna [] silenciosamente se OpenAI não estiver configurado ou tabela vazia.
    """
    try:
        from app.services.embedding_service import generate_embeddings
        from app.models.bookstack_embedding import BookstackEmbedding

        # Trunca conteúdo para economizar tokens (~2000 chars é suficiente para capturar o tema)
        text = content[:2000]
        vectors = await generate_embeddings([text])
        query_vector = vectors[0]

        stmt = (
            select(
                BookstackEmbedding.bs_page_id,
                BookstackEmbedding.bs_page_name,
                BookstackEmbedding.bs_page_url,
                BookstackEmbedding.embedding.cosine_distance(query_vector).label("distance"),
            )
            .where(BookstackEmbedding.tenant_id == tenant_id)
            .order_by(BookstackEmbedding.embedding.cosine_distance(query_vector))
            .limit(_SIMILARITY_TOP_K * 5)  # busca mais chunks para deduplicar por página
        )

        rows = (await db.execute(stmt)).all()

        # Deduplica por bs_page_id mantendo a maior similaridade do chunk mais próximo
        seen: dict[int, dict] = {}
        for row in rows:
            sim = round(1.0 - float(row.distance), 3)
            if sim < _SIMILARITY_THRESHOLD:
                continue
            if row.bs_page_id not in seen or sim > seen[row.bs_page_id]["similarity"]:
                seen[row.bs_page_id] = {
                    "bs_page_id": row.bs_page_id,
                    "title": row.bs_page_name or f"Página {row.bs_page_id}",
                    "url": row.bs_page_url or "",
                    "similarity": sim,
                }

        return sorted(seen.values(), key=lambda x: x["similarity"], reverse=True)[:_SIMILARITY_TOP_K]

    except Exception as exc:
        log.debug("Similarity check ignorado: %s", exc)
        return []


# ── Helper ────────────────────────────────────────────────────────────────────

async def _get_draft(
    db: AsyncSession,
    draft_id: UUID,
    tenant_id: UUID,
) -> AssistantDocDraft:
    draft = await get_draft(db, draft_id, tenant_id)
    if not draft:
        raise ValueError("Rascunho não encontrado.")
    return draft
