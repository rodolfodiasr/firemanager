"""Embedding service — text chunking, OpenAI embedding generation, pgvector search."""
from __future__ import annotations

import hashlib
import re
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

_CHUNK_SIZE = 1500     # characters ≈ 375 tokens (text-embedding-3-small)
_CHUNK_OVERLAP = 150   # characters
_TOP_K = 5             # semantic search: max chunks returned
_MAX_CTX_CHARS = 3000  # cap on combined context returned to the AI


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks, preferring paragraph boundaries."""
    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + _CHUNK_SIZE, len(text))

        # Prefer splitting at a paragraph boundary near the end
        if end < len(text):
            break_pos = text.rfind("\n\n", start + _CHUNK_SIZE // 2, end)
            if break_pos != -1:
                end = break_pos

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - _CHUNK_OVERLAP if end < len(text) else len(text)

    return chunks


# ── Embedding generation ──────────────────────────────────────────────────────

async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Call OpenAI text-embedding-3-small to generate embedding vectors."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]


# ── Upsert ────────────────────────────────────────────────────────────────────

async def upsert_page_embeddings(
    db: AsyncSession,
    tenant_id: UUID,
    integration_id: UUID,
    bs_page_id: int,
    bs_page_name: str,
    bs_page_url: str,
    content: str,
) -> int:
    """Chunk, embed, and upsert a BookStack page into bookstack_embeddings.

    Returns the number of chunks written (0 = page was unchanged).
    """
    from app.models.bookstack_embedding import BookstackEmbedding

    content_hash = hashlib.sha256(content.encode()).hexdigest()

    # Skip if already indexed with identical content
    existing = await db.execute(
        select(BookstackEmbedding).where(
            BookstackEmbedding.integration_id == integration_id,
            BookstackEmbedding.bs_page_id == bs_page_id,
            BookstackEmbedding.chunk_index == 0,
        )
    )
    first = existing.scalar_one_or_none()
    if first and first.content_hash == content_hash:
        return 0

    # Remove stale chunks for this page
    await db.execute(
        delete(BookstackEmbedding).where(
            BookstackEmbedding.integration_id == integration_id,
            BookstackEmbedding.bs_page_id == bs_page_id,
        )
    )

    chunks = chunk_text(content)
    if not chunks:
        return 0

    vectors = await generate_embeddings(chunks)

    for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
        db.add(BookstackEmbedding(
            tenant_id=tenant_id,
            integration_id=integration_id,
            bs_page_id=bs_page_id,
            bs_page_name=bs_page_name,
            bs_page_url=bs_page_url,
            chunk_index=i,
            chunk_text=chunk,
            content_hash=content_hash,
            embedding=vector,
        ))

    return len(chunks)


# ── Semantic search ───────────────────────────────────────────────────────────

async def semantic_search(
    db: AsyncSession,
    tenant_id: UUID,
    query: str,
    top_k: int = _TOP_K,
    exclude_page_ids: set[int] | None = None,
) -> str:
    """Return the most semantically relevant BookStack chunks for a query.

    Returns empty string if OpenAI key is not configured or no results found.
    Never raises — failures are silenced.
    """
    if not query.strip() or not settings.openai_api_key:
        return ""

    try:
        from app.models.bookstack_embedding import BookstackEmbedding

        query_vectors = await generate_embeddings([query])
        query_vector = query_vectors[0]

        stmt = (
            select(BookstackEmbedding)
            .where(BookstackEmbedding.tenant_id == tenant_id)
            .order_by(BookstackEmbedding.embedding.cosine_distance(query_vector))
            .limit(top_k)
        )
        if exclude_page_ids:
            stmt = stmt.where(BookstackEmbedding.bs_page_id.notin_(exclude_page_ids))

        result = await db.execute(stmt)
        rows = list(result.scalars().all())

        if not rows:
            return ""

        # Group chunks by page, preserving result order
        pages: dict[int, list[str]] = {}
        page_names: dict[int, str] = {}
        for row in rows:
            pages.setdefault(row.bs_page_id, []).append(row.chunk_text)
            page_names[row.bs_page_id] = row.bs_page_name

        parts = [
            f"## {page_names[pid]}\n\n" + "\n\n".join(chunks)
            for pid, chunks in pages.items()
        ]
        return "\n\n---\n\n".join(parts)[:_MAX_CTX_CHARS]

    except Exception:
        return ""


def strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()
