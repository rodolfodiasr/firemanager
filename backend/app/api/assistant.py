"""Fase 40-B: AI Assistant Panel — endpoints REST."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.services import assistant_service
from app.services.llm_provider import openai_available

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class AssistantChatRequest(BaseModel):
    content: str
    session_id: UUID | None = None
    model: str | None = None  # "openai" | "claude" | None (usa padrão)


class AssistantMessageRead(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    rag_context_used: bool
    created_at: str

    @classmethod
    def from_orm(cls, m) -> "AssistantMessageRead":
        return cls(
            id=str(m.id),
            session_id=str(m.session_id),
            role=m.role,
            content=m.content,
            model=m.model,
            input_tokens=m.input_tokens,
            output_tokens=m.output_tokens,
            rag_context_used=m.rag_context_used,
            created_at=m.created_at.isoformat(),
        )


class AssistantSessionRead(BaseModel):
    id: str
    title: str | None
    model_used: str
    message_count: int
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, s) -> "AssistantSessionRead":
        return cls(
            id=str(s.id),
            title=s.title,
            model_used=s.model_used,
            message_count=s.message_count,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
        )


class AssistantCapabilities(BaseModel):
    openai_available: bool
    default_model: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/capabilities", response_model=AssistantCapabilities)
async def get_capabilities(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> AssistantCapabilities:
    """Retorna quais modelos estão disponíveis para o tenant."""
    from app.config import settings
    return AssistantCapabilities(
        openai_available=openai_available(),
        default_model=settings.anthropic_model,
    )


@router.post("/chat", response_model=AssistantMessageRead, status_code=200)
async def chat(
    data: AssistantChatRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> AssistantMessageRead:
    """Envia mensagem ao AI Assistant e recebe resposta."""
    if not data.content.strip():
        raise HTTPException(status_code=400, detail="Mensagem não pode ser vazia.")

    try:
        _, ai_msg = await assistant_service.send_message(
            db=db,
            tenant_id=ctx.tenant.id,
            user_id=ctx.user.id,
            user_role=ctx.role,
            session_id=data.session_id,
            content=data.content.strip(),
            model_preference=data.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return AssistantMessageRead.from_orm(ai_msg)


@router.get("/sessions", response_model=list[AssistantSessionRead])
async def list_sessions(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[AssistantSessionRead]:
    """Lista sessões do usuário atual (mais recentes primeiro)."""
    sessions = await assistant_service.list_sessions(db, ctx.tenant.id, ctx.user.id)
    return [AssistantSessionRead.from_orm(s) for s in sessions]


@router.get("/sessions/{session_id}", response_model=dict)
async def get_session(
    session_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Retorna sessão com todas as mensagens."""
    result = await assistant_service.get_session_with_messages(
        db, session_id, ctx.tenant.id, ctx.user.id
    )
    if not result:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    session, messages = result
    return {
        "session": AssistantSessionRead.from_orm(session),
        "messages": [AssistantMessageRead.from_orm(m) for m in messages],
    }


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Deleta sessão e todas as mensagens."""
    deleted = await assistant_service.delete_session(db, session_id, ctx.tenant.id, ctx.user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    return Response(status_code=204)
