"""AI Assistant — endpoints REST (chat, sessões, pastas, compartilhamento)."""
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
    model: str | None = None
    folder_id: UUID | None = None


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
    folder_id: str | None
    is_shared: bool
    pinned: bool
    user_name: str | None = None
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, s, user_name: str | None = None) -> "AssistantSessionRead":
        return cls(
            id=str(s.id),
            title=s.title,
            model_used=s.model_used,
            message_count=s.message_count,
            folder_id=str(s.folder_id) if s.folder_id else None,
            is_shared=s.is_shared,
            pinned=s.pinned,
            user_name=user_name,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
        )


class AssistantFolderRead(BaseModel):
    id: str
    name: str
    color: str
    is_team: bool
    user_id: str | None
    created_at: str

    @classmethod
    def from_orm(cls, f) -> "AssistantFolderRead":
        return cls(
            id=str(f.id),
            name=f.name,
            color=f.color,
            is_team=f.is_team,
            user_id=str(f.user_id) if f.user_id else None,
            created_at=f.created_at.isoformat(),
        )


class AssistantCapabilities(BaseModel):
    openai_available: bool
    default_model: str


class CreateFolderRequest(BaseModel):
    name: str
    color: str = "#6366f1"
    is_team: bool = False


class UpdateFolderRequest(BaseModel):
    name: str | None = None
    color: str | None = None


class RenameSessionRequest(BaseModel):
    title: str


class MoveSessionRequest(BaseModel):
    folder_id: UUID | None = None


class ShareSessionRequest(BaseModel):
    shared: bool


class PinSessionRequest(BaseModel):
    pinned: bool


# ── Capabilities ──────────────────────────────────────────────────────────────

@router.get("/capabilities", response_model=AssistantCapabilities)
async def get_capabilities(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> AssistantCapabilities:
    from app.config import settings
    return AssistantCapabilities(
        openai_available=openai_available(),
        default_model=settings.anthropic_model,
    )


# ── Chat ──────────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=AssistantMessageRead, status_code=200)
async def chat(
    data: AssistantChatRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssistantMessageRead:
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
            folder_id=data.folder_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return AssistantMessageRead.from_orm(ai_msg)


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.get("/sessions", response_model=list[AssistantSessionRead])
async def list_sessions(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AssistantSessionRead]:
    sessions = await assistant_service.list_sessions(db, ctx.tenant.id, ctx.user.id)
    return [AssistantSessionRead.from_orm(s) for s in sessions]


@router.get("/sessions/team", response_model=list[AssistantSessionRead])
async def list_team_sessions(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AssistantSessionRead]:
    """Sessões compartilhadas ou em pastas de equipe de outros membros."""
    from sqlalchemy import select
    from app.models.assistant import AssistantSession
    from app.models.user import User

    sessions = await assistant_service.list_team_sessions(db, ctx.tenant.id, ctx.user.id)

    # Buscar nomes dos autores em batch
    user_ids = list({s.user_id for s in sessions})
    names: dict[UUID, str] = {}
    if user_ids:
        result = await db.execute(
            select(User.id, User.name).where(User.id.in_(user_ids))
        )
        names = {row.id: row.name for row in result}

    return [AssistantSessionRead.from_orm(s, user_name=names.get(s.user_id)) for s in sessions]


@router.get("/sessions/{session_id}", response_model=dict)
async def get_session(
    session_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    deleted = await assistant_service.delete_session(db, session_id, ctx.tenant.id, ctx.user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    return Response(status_code=204)


@router.put("/sessions/{session_id}/rename", response_model=AssistantSessionRead)
async def rename_session(
    session_id: UUID,
    data: RenameSessionRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssistantSessionRead:
    session = await assistant_service.rename_session(
        db, session_id, ctx.tenant.id, ctx.user.id, data.title.strip()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    return AssistantSessionRead.from_orm(session)


@router.put("/sessions/{session_id}/move", response_model=AssistantSessionRead)
async def move_session(
    session_id: UUID,
    data: MoveSessionRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssistantSessionRead:
    session = await assistant_service.move_session(
        db, session_id, ctx.tenant.id, ctx.user.id, data.folder_id
    )
    if not session:
        raise HTTPException(status_code=404, detail="Sessão ou pasta não encontrada.")
    return AssistantSessionRead.from_orm(session)


@router.put("/sessions/{session_id}/share", response_model=AssistantSessionRead)
async def share_session(
    session_id: UUID,
    data: ShareSessionRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssistantSessionRead:
    session = await assistant_service.share_session(
        db, session_id, ctx.tenant.id, ctx.user.id, data.shared
    )
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    return AssistantSessionRead.from_orm(session)


@router.put("/sessions/{session_id}/pin", response_model=AssistantSessionRead)
async def pin_session(
    session_id: UUID,
    data: PinSessionRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssistantSessionRead:
    session = await assistant_service.pin_session(
        db, session_id, ctx.tenant.id, ctx.user.id, data.pinned
    )
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    return AssistantSessionRead.from_orm(session)


# ── Folders ───────────────────────────────────────────────────────────────────

@router.get("/folders", response_model=list[AssistantFolderRead])
async def list_folders(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AssistantFolderRead]:
    folders = await assistant_service.list_folders(db, ctx.tenant.id, ctx.user.id)
    return [AssistantFolderRead.from_orm(f) for f in folders]


@router.post("/folders", response_model=AssistantFolderRead, status_code=201)
async def create_folder(
    data: CreateFolderRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssistantFolderRead:
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="Nome da pasta não pode ser vazio.")
    folder = await assistant_service.create_folder(
        db, ctx.tenant.id, ctx.user.id,
        data.name.strip(), data.color, data.is_team,
    )
    return AssistantFolderRead.from_orm(folder)


@router.put("/folders/{folder_id}", response_model=AssistantFolderRead)
async def update_folder(
    folder_id: UUID,
    data: UpdateFolderRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssistantFolderRead:
    folder = await assistant_service.update_folder(
        db, folder_id, ctx.tenant.id, ctx.user.id,
        data.name, data.color,
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Pasta não encontrada.")
    return AssistantFolderRead.from_orm(folder)


@router.delete("/folders/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    deleted = await assistant_service.delete_folder(
        db, folder_id, ctx.tenant.id, ctx.user.id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Pasta não encontrada.")
    return Response(status_code=204)
