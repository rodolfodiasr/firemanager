"""F40-A: Endpoints para geração, revisão e publicação de documentação a partir de sessões do AI Assistant."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.services import doc_publisher

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class SimilarDocRead(BaseModel):
    bs_page_id: int
    title: str
    url: str
    similarity: float


class DocDraftRead(BaseModel):
    id: str
    session_id: str
    tenant_id: str
    created_by: str | None
    title: str
    content: str
    status: str
    review_deadline: str | None
    sanitizer_warnings: list[dict]
    similar_docs: list[SimilarDocRead]
    bookstack_page_id: int | None
    bookstack_page_url: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, d) -> "DocDraftRead":
        return cls(
            id=str(d.id),
            session_id=str(d.session_id),
            tenant_id=str(d.tenant_id),
            created_by=str(d.created_by) if d.created_by else None,
            title=d.title,
            content=d.content,
            status=d.status,
            review_deadline=d.review_deadline.isoformat() if d.review_deadline else None,
            sanitizer_warnings=d.sanitizer_warnings or [],
            similar_docs=[SimilarDocRead(**s) for s in (d.similar_docs or [])],
            bookstack_page_id=d.bookstack_page_id,
            bookstack_page_url=d.bookstack_page_url,
            created_at=d.created_at.isoformat(),
            updated_at=d.updated_at.isoformat(),
        )


class UpdateDraftRequest(BaseModel):
    title: str | None = None
    content: str | None = None


# ── Geração ───────────────────────────────────────────────────────────────────

@router.post("/sessions/{session_id}/generate-doc", response_model=DocDraftRead, status_code=201)
async def generate_doc(
    session_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocDraftRead:
    """Gera um rascunho de documentação a partir de uma sessão do AI Assistant."""
    try:
        draft = await doc_publisher.generate_draft(
            db=db,
            session_id=session_id,
            tenant_id=ctx.tenant.id,
            user_id=ctx.user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return DocDraftRead.from_orm(draft)


# ── Listagem ──────────────────────────────────────────────────────────────────

@router.get("/docs", response_model=list[DocDraftRead])
async def list_docs(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = None,
) -> list[DocDraftRead]:
    """Lista rascunhos de documentação do tenant, opcionalmente filtrado por status."""
    drafts = await doc_publisher.list_drafts(db, ctx.tenant.id, status=status)
    return [DocDraftRead.from_orm(d) for d in drafts]


@router.get("/docs/{draft_id}", response_model=DocDraftRead)
async def get_doc(
    draft_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocDraftRead:
    draft = await doc_publisher.get_draft(db, draft_id, ctx.tenant.id)
    if not draft:
        raise HTTPException(status_code=404, detail="Rascunho não encontrado.")
    return DocDraftRead.from_orm(draft)


# ── Ações ─────────────────────────────────────────────────────────────────────

@router.put("/docs/{draft_id}", response_model=DocDraftRead)
async def update_doc(
    draft_id: UUID,
    data: UpdateDraftRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocDraftRead:
    """Edita título e/ou conteúdo de um rascunho (re-sanitiza automaticamente)."""
    try:
        draft = await doc_publisher.update_draft_content(
            db, draft_id, ctx.tenant.id, data.title, data.content
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return DocDraftRead.from_orm(draft)


@router.post("/docs/{draft_id}/approve", response_model=DocDraftRead)
async def approve_doc(
    draft_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocDraftRead:
    """Marca o rascunho como aprovado (pronto para publicação)."""
    try:
        draft = await doc_publisher.approve_draft(db, draft_id, ctx.tenant.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return DocDraftRead.from_orm(draft)


@router.post("/docs/{draft_id}/reject", response_model=DocDraftRead)
async def reject_doc(
    draft_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocDraftRead:
    """Rejeita o rascunho — não será publicado."""
    try:
        draft = await doc_publisher.reject_draft(db, draft_id, ctx.tenant.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return DocDraftRead.from_orm(draft)


@router.post("/docs/{draft_id}/publish", response_model=DocDraftRead)
async def publish_doc(
    draft_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocDraftRead:
    """Publica o rascunho no BookStack e dispara reindexação no RAG."""
    try:
        draft = await doc_publisher.publish_draft(db, draft_id, ctx.tenant.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return DocDraftRead.from_orm(draft)


@router.delete("/docs/{draft_id}", status_code=204)
async def delete_doc(
    draft_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Remove o rascunho (somente drafts não publicados)."""
    from sqlalchemy import select, delete
    from app.models.doc_draft import AssistantDocDraft

    result = await db.execute(
        select(AssistantDocDraft).where(
            AssistantDocDraft.id == draft_id,
            AssistantDocDraft.tenant_id == ctx.tenant.id,
        )
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Rascunho não encontrado.")
    if draft.status == "published":
        raise HTTPException(status_code=400, detail="Rascunhos publicados não podem ser removidos.")
    await db.execute(
        delete(AssistantDocDraft).where(AssistantDocDraft.id == draft_id)
    )
    await db.flush()
    return Response(status_code=204)
