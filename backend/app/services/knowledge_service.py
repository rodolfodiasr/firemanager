"""Fase 19 — Knowledge Base service.

Handles text extraction from uploaded files (PDF, DOCX, Markdown, TXT),
chunking, embedding generation (OpenAI text-embedding-3-small), and
storage in knowledge_chunks (pgvector).
"""
from __future__ import annotations

import hashlib
import io
import logging
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embedding_service import chunk_text, generate_embeddings

log = logging.getLogger(__name__)


# ── Text extraction ────────────────────────────────────────────────────────────

def extract_text_from_bytes(file_bytes: bytes, file_type: str) -> str:
    """Extract plain text from uploaded file bytes."""
    ft = file_type.lower().lstrip(".")

    if ft in ("txt", "md", "markdown"):
        return _decode(file_bytes)

    if ft == "docx":
        return _extract_docx(file_bytes)

    if ft == "pdf":
        return _extract_pdf(file_bytes)

    # Fallback: try raw UTF-8 decode
    return _decode(file_bytes)


def _decode(data: bytes) -> str:
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _extract_docx(data: bytes) -> str:
    try:
        import docx
        doc = docx.Document(io.BytesIO(data))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as exc:
        raise ValueError(f"Falha ao extrair texto do DOCX: {exc}") from exc


def _extract_pdf(data: bytes) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(data))
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text and text.strip():
                pages.append(text.strip())
        if not pages:
            raise ValueError("PDF sem texto extraível (pode ser escaneado/imagem)")
        return "\n\n".join(pages)
    except ImportError:
        raise ValueError("pypdf não instalado — PDF não suportado neste ambiente")
    except Exception as exc:
        if "sem texto" in str(exc) or "escaneado" in str(exc):
            raise
        raise ValueError(f"Falha ao extrair texto do PDF: {exc}") from exc


# ── Indexing ──────────────────────────────────────────────────────────────────

async def index_document(db: AsyncSession, document_id: UUID) -> int:
    """Chunk, embed, and store a document's content in knowledge_chunks.

    Returns the number of chunks written. Updates document status/chunk_count/error.
    Raises ValueError if document not found or has no content.
    """
    from app.models.knowledge_document import KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentStatus

    doc = await db.get(KnowledgeDocument, document_id)
    if not doc:
        raise ValueError(f"Documento {document_id} não encontrado")

    if not doc.content or not doc.content.strip():
        doc.status = KnowledgeDocumentStatus.failed
        doc.error = "Documento sem conteúdo de texto"
        await db.commit()
        raise ValueError(doc.error)

    doc.status = KnowledgeDocumentStatus.indexing
    doc.error = None
    await db.flush()

    try:
        # Remove existing chunks (re-index scenario)
        await db.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)
        )

        chunks = chunk_text(doc.content)
        if not chunks:
            raise ValueError("Nenhum chunk gerado — conteúdo muito curto")

        vectors = await generate_embeddings(chunks)
        content_hash = hashlib.sha256(doc.content.encode()).hexdigest()

        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            db.add(KnowledgeChunk(
                tenant_id=doc.tenant_id,
                document_id=document_id,
                chunk_index=i,
                chunk_text=chunk,
                content_hash=content_hash,
                embedding=vector,
            ))

        doc.status = KnowledgeDocumentStatus.indexed
        doc.chunk_count = len(chunks)
        await db.commit()
        log.info("knowledge_indexed document=%s chunks=%d", document_id, len(chunks))
        return len(chunks)

    except Exception as exc:
        doc.status = KnowledgeDocumentStatus.failed
        doc.error = str(exc)[:500]
        doc.chunk_count = 0
        await db.commit()
        log.exception("knowledge_index_failed document=%s: %s", document_id, exc)
        raise


# ── Semantic search over knowledge_chunks ─────────────────────────────────────

async def semantic_search_documents(
    db: AsyncSession,
    tenant_id: UUID,
    query: str,
    top_k: int = 5,
) -> str:
    """Return the most relevant knowledge document chunks for a query.

    Returns empty string if OpenAI key is not configured or no results found.
    Never raises.
    """
    from app.config import settings

    if not query.strip() or not settings.openai_api_key:
        return ""

    try:
        from app.models.knowledge_document import KnowledgeChunk, KnowledgeDocument

        vectors = await generate_embeddings([query])
        query_vector = vectors[0]

        stmt = (
            select(KnowledgeChunk, KnowledgeDocument.name)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeChunk.tenant_id == tenant_id)
            .where(KnowledgeDocument.is_active.is_(True))
            .order_by(KnowledgeChunk.embedding.cosine_distance(query_vector))
            .limit(top_k)
        )
        result = await db.execute(stmt)
        rows = result.all()

        if not rows:
            return ""

        docs: dict[str, list[str]] = {}
        for chunk, doc_name in rows:
            docs.setdefault(doc_name, []).append(chunk.chunk_text)

        parts = [
            f"## {name}\n\n" + "\n\n".join(chunks)
            for name, chunks in docs.items()
        ]
        return "\n\n---\n\n".join(parts)[:3000]

    except Exception:
        return ""


# ── Document CRUD helpers ──────────────────────────────────────────────────────

async def delete_document(db: AsyncSession, document_id: UUID) -> None:
    """Delete a document and all its chunks."""
    from app.models.knowledge_document import KnowledgeDocument

    doc = await db.get(KnowledgeDocument, document_id)
    if doc:
        await db.delete(doc)
        await db.commit()


async def get_stats(db: AsyncSession, tenant_id: UUID) -> dict:
    """Return knowledge base stats for a tenant."""
    from app.models.knowledge_document import KnowledgeDocument, KnowledgeDocumentStatus
    from sqlalchemy import func as sqlfunc

    result = await db.execute(
        select(
            sqlfunc.count(KnowledgeDocument.id).label("total"),
            sqlfunc.sum(KnowledgeDocument.chunk_count).label("total_chunks"),
        ).where(KnowledgeDocument.tenant_id == tenant_id)
    )
    row = result.one()

    status_result = await db.execute(
        select(KnowledgeDocument.status, sqlfunc.count(KnowledgeDocument.id))
        .where(KnowledgeDocument.tenant_id == tenant_id)
        .group_by(KnowledgeDocument.status)
    )
    by_status = {s: c for s, c in status_result.all()}

    return {
        "total_documents": row.total or 0,
        "total_chunks": row.total_chunks or 0,
        "by_status": by_status,
    }
