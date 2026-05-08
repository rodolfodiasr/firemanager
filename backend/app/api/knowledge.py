"""API routes — Fase 19: Knowledge Base (upload, list, delete, search, reindex)."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_reviewer
from app.database import get_db

router = APIRouter()

_ALLOWED_TYPES = {"pdf", "docx", "md", "txt", "markdown"}
_MAX_FILE_MB = 20


# ── Schemas ───────────────────────────────────────────────────────────────────

class DocumentRead(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str | None
    file_type: str
    file_size: int | None
    status: str
    chunk_count: int
    is_active: bool
    module: str | None
    vendor: str | None
    error: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, d) -> "DocumentRead":
        return cls(
            id=str(d.id),
            tenant_id=str(d.tenant_id),
            name=d.name,
            description=d.description,
            file_type=d.file_type,
            file_size=d.file_size,
            status=d.status,
            chunk_count=d.chunk_count or 0,
            is_active=d.is_active if d.is_active is not None else True,
            module=d.module,
            vendor=d.vendor,
            error=d.error,
            created_at=d.created_at.isoformat(),
            updated_at=d.updated_at.isoformat(),
        )


class ToggleActivePayload(BaseModel):
    is_active: bool


class SearchResult(BaseModel):
    query: str
    context: str
    chunk_count: int


class StatsRead(BaseModel):
    total_documents: int
    total_chunks: int
    by_status: dict[str, int]


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post("", response_model=DocumentRead, status_code=201)
async def upload_document(
    file: Annotated[UploadFile, File(description="Arquivo PDF, DOCX, MD ou TXT")],
    name: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    module: Annotated[str | None, Form()] = None,
    vendor: Annotated[str | None, Form()] = None,
    ctx: Annotated[TenantContext, Depends(require_reviewer)] = None,
    db:  Annotated[AsyncSession, Depends(get_db)] = None,
) -> DocumentRead:
    # Validate file type
    filename = file.filename or "documento"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    if ext not in _ALLOWED_TYPES:
        raise HTTPException(400, f"Tipo de arquivo não suportado: .{ext}. Aceitos: {', '.join(sorted(_ALLOWED_TYPES))}")

    content_bytes = await file.read()
    size_mb = len(content_bytes) / (1024 * 1024)
    if size_mb > _MAX_FILE_MB:
        raise HTTPException(413, f"Arquivo muito grande ({size_mb:.1f} MB). Limite: {_MAX_FILE_MB} MB")

    # Extract text
    from app.services.knowledge_service import extract_text_from_bytes
    try:
        text_content = extract_text_from_bytes(content_bytes, ext)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    if not text_content.strip():
        raise HTTPException(422, "Nenhum texto extraído do arquivo")

    # Persist document
    from app.models.knowledge_document import KnowledgeDocument, KnowledgeDocumentStatus
    doc = KnowledgeDocument(
        tenant_id=ctx.tenant.id,
        name=name or filename,
        description=description,
        file_type=ext,
        file_size=len(content_bytes),
        content=text_content,
        status=KnowledgeDocumentStatus.pending,
        chunk_count=0,
        module=module or None,
        vendor=vendor or None,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    doc_id = str(doc.id)
    await db.commit()

    # Queue background indexing
    try:
        from app.workers.knowledge_worker import process_knowledge_document
        process_knowledge_document.delay(doc_id)
    except Exception:
        pass

    await db.refresh(doc)
    return DocumentRead.from_orm(doc)


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[DocumentRead])
async def list_documents(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[DocumentRead]:
    from app.models.knowledge_document import KnowledgeDocument
    result = await db.execute(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.tenant_id == ctx.tenant.id)
        .order_by(KnowledgeDocument.created_at.desc())
        .limit(200)
    )
    return [DocumentRead.from_orm(d) for d in result.scalars().all()]


# ── Get ───────────────────────────────────────────────────────────────────────

@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> DocumentRead:
    from app.models.knowledge_document import KnowledgeDocument
    doc = await db.get(KnowledgeDocument, document_id)
    if not doc or doc.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Documento não encontrado")
    return DocumentRead.from_orm(doc)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{document_id}")
async def delete_document(
    document_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    from app.models.knowledge_document import KnowledgeDocument
    doc = await db.get(KnowledgeDocument, document_id)
    if not doc or doc.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Documento não encontrado")
    await db.delete(doc)
    await db.commit()
    return Response(status_code=204)


# ── Toggle active ─────────────────────────────────────────────────────────────

@router.patch("/{document_id}/active", response_model=DocumentRead)
async def toggle_document_active(
    document_id: UUID,
    payload: ToggleActivePayload,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> DocumentRead:
    from app.models.knowledge_document import KnowledgeDocument
    doc = await db.get(KnowledgeDocument, document_id)
    if not doc or doc.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Documento não encontrado")
    doc.is_active = payload.is_active
    await db.commit()
    await db.refresh(doc)
    return DocumentRead.from_orm(doc)


# ── Reindex ───────────────────────────────────────────────────────────────────

@router.post("/{document_id}/reindex", response_model=DocumentRead)
async def reindex_document(
    document_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> DocumentRead:
    from app.models.knowledge_document import KnowledgeDocument, KnowledgeDocumentStatus
    doc = await db.get(KnowledgeDocument, document_id)
    if not doc or doc.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Documento não encontrado")
    if not doc.content:
        raise HTTPException(422, "Documento sem conteúdo — faça upload novamente")

    doc.status = KnowledgeDocumentStatus.pending
    doc.error = None
    await db.commit()

    try:
        from app.workers.knowledge_worker import process_knowledge_document
        process_knowledge_document.delay(str(document_id))
    except Exception:
        pass

    await db.refresh(doc)
    return DocumentRead.from_orm(doc)


# ── Search test ───────────────────────────────────────────────────────────────

@router.get("/search/test", response_model=SearchResult)
async def test_search(
    q: Annotated[str, Query(min_length=3, description="Consulta de busca semântica")],
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> SearchResult:
    from app.services.knowledge_service import semantic_search_documents
    from app.services.embedding_service import semantic_search

    # Search both BookStack and knowledge docs
    kb_ctx = await semantic_search_documents(db, ctx.tenant.id, q, top_k=5)
    bs_ctx = await semantic_search(db, ctx.tenant.id, q, top_k=5)

    parts = [p for p in [kb_ctx, bs_ctx] if p]
    combined = "\n\n---\n\n".join(parts)

    chunk_count = combined.count("## ") if combined else 0
    return SearchResult(query=q, context=combined or "", chunk_count=chunk_count)


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats/summary", response_model=StatsRead)
async def get_stats(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> StatsRead:
    from app.services.knowledge_service import get_stats
    stats = await get_stats(db, ctx.tenant.id)
    return StatsRead(**stats)
