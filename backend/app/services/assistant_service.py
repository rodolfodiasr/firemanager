"""AI Assistant Service — RAG + LLM + audit hash-chain + pastas + compartilhamento."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import AssistantFolder, AssistantMessage, AssistantSession
from app.models.user_tenant_role import TenantRole
from app.services.assistant_data_scope import build_context_for_query
from app.services.llm_provider import get_provider

_ASSISTANT_SYSTEM_TEMPLATE = """\
Você é o AI Assistant do Eternity SecOps, plataforma de operação de infraestrutura \
de segurança com IA agentic para MSSPs.

SUAS CAPACIDADES:
- Responder perguntas sobre dispositivos gerenciados, regras de firewall, compliance, \
identidade e histórico de operações do tenant
- Consultar e explicar informações da base de conhecimento e snapshots de dispositivos
- Explicar conceitos de segurança, boas práticas e como usar a plataforma
- Ajudar o analista a formular o pedido correto para o Agente Operacional (que executa ações)

RESTRIÇÕES ABSOLUTAS — não negocie:
- Não executa operações, não altera configurações, não aplica comandos
- Não revela credenciais, senhas, chaves API, tokens ou valores cifrados
- Não acessa dados de outros tenants — você só vê o contexto fornecido abaixo
- Se não encontrar a informação no contexto, diga claramente que não tem acesso

CONTEXTO DO TENANT (dados atuais):
{context}

Responda em português. Seja preciso, objetivo e seguro.\
"""


def _compute_hash(prev_hash: str, role: str, content: str) -> str:
    data = f"{prev_hash}|{role}|{content}|{datetime.utcnow().isoformat()}"
    return hashlib.sha256(data.encode()).hexdigest()


# ── Session internals ─────────────────────────────────────────────────────────

async def _get_or_create_session(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    session_id: UUID | None,
    model_preference: str | None,
    folder_id: UUID | None = None,
) -> AssistantSession:
    if session_id:
        result = await db.execute(
            select(AssistantSession).where(
                AssistantSession.id == session_id,
                AssistantSession.tenant_id == tenant_id,
                AssistantSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session:
            return session

    provider = get_provider(model_preference)
    session = AssistantSession(
        tenant_id=tenant_id,
        user_id=user_id,
        model_used=provider.name,
        folder_id=folder_id,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


async def _load_history(db: AsyncSession, session_id: UUID, limit: int = 20) -> list[dict]:
    result = await db.execute(
        select(AssistantMessage)
        .where(AssistantMessage.session_id == session_id)
        .order_by(AssistantMessage.created_at)
        .limit(limit)
    )
    return [{"role": m.role, "content": m.content} for m in result.scalars().all()]


# ── Send message ──────────────────────────────────────────────────────────────

async def send_message(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    user_role: TenantRole,
    session_id: UUID | None,
    content: str,
    model_preference: str | None,
    folder_id: UUID | None = None,
) -> tuple[AssistantSession, AssistantMessage]:
    from app.agent.guardrails import check_action_plan
    _safe_plan: dict = {
        "intent": "assistant_query",
        "ssh_commands": [],
        "raw_intent_data": {"description": content},
    }
    _gr = check_action_plan(_safe_plan, content)
    if _gr.blocked:
        raise ValueError(f"Mensagem bloqueada pela política de segurança: {_gr.block_reason}")

    session = await _get_or_create_session(
        db, tenant_id, user_id, session_id, model_preference, folder_id
    )

    prev_hash = session.last_hash or ""
    user_msg = AssistantMessage(
        session_id=session.id,
        role="user",
        content=content,
        rag_context_used=False,
        message_hash=_compute_hash(prev_hash, "user", content),
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg)
    await db.flush()
    await db.refresh(user_msg)

    context = await build_context_for_query(db, tenant_id, user_role, content)
    system = _ASSISTANT_SYSTEM_TEMPLATE.replace("{context}", context or "(nenhum contexto disponível)")

    history = await _load_history(db, session.id, limit=18)
    if not history or history[-1]["content"] != content:
        history.append({"role": "user", "content": content})

    provider = get_provider(model_preference or session.model_used)
    response_text, input_tok, output_tok = await provider.chat(history, system)

    ai_msg = AssistantMessage(
        session_id=session.id,
        role="assistant",
        content=response_text,
        model=provider.name,
        input_tokens=input_tok,
        output_tokens=output_tok,
        rag_context_used=bool(context),
        message_hash=_compute_hash(user_msg.message_hash, "assistant", response_text),
        created_at=datetime.now(timezone.utc),
    )
    db.add(ai_msg)

    session.last_hash = ai_msg.message_hash
    session.message_count += 2
    session.model_used = provider.name
    if not session.title:
        session.title = content[:80]

    await db.flush()
    await db.refresh(session)
    await db.refresh(ai_msg)
    await db.commit()

    return session, ai_msg


# ── Session queries ───────────────────────────────────────────────────────────

async def list_sessions(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    limit: int = 100,
) -> list[AssistantSession]:
    """Sessões do próprio usuário — fixadas primeiro, depois por updated_at."""
    result = await db.execute(
        select(AssistantSession)
        .where(
            AssistantSession.tenant_id == tenant_id,
            AssistantSession.user_id == user_id,
        )
        .order_by(
            desc(AssistantSession.pinned),
            desc(AssistantSession.updated_at),
        )
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_team_sessions(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    limit: int = 100,
) -> list[AssistantSession]:
    """Sessões visíveis para a equipe: is_shared=True ou em pasta de equipe."""
    result = await db.execute(
        select(AssistantSession)
        .outerjoin(AssistantFolder, AssistantSession.folder_id == AssistantFolder.id)
        .where(
            AssistantSession.tenant_id == tenant_id,
            AssistantSession.user_id != user_id,
            or_(
                AssistantSession.is_shared.is_(True),
                AssistantFolder.is_team.is_(True),
            ),
        )
        .order_by(desc(AssistantSession.updated_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_session_with_messages(
    db: AsyncSession,
    session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
) -> tuple[AssistantSession, list[AssistantMessage]] | None:
    """Retorna sessão + mensagens. Permite acesso a sessões compartilhadas."""
    result = await db.execute(
        select(AssistantSession).where(
            AssistantSession.id == session_id,
            AssistantSession.tenant_id == tenant_id,
            or_(
                AssistantSession.user_id == user_id,
                AssistantSession.is_shared.is_(True),
            ),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    msg_result = await db.execute(
        select(AssistantMessage)
        .where(AssistantMessage.session_id == session_id)
        .order_by(AssistantMessage.created_at)
    )
    return session, list(msg_result.scalars().all())


async def delete_session(
    db: AsyncSession,
    session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
) -> bool:
    result = await db.execute(
        select(AssistantSession).where(
            AssistantSession.id == session_id,
            AssistantSession.tenant_id == tenant_id,
            AssistantSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return False
    await db.delete(session)
    await db.commit()
    return True


# ── Session mutations ─────────────────────────────────────────────────────────

async def rename_session(
    db: AsyncSession,
    session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    title: str,
) -> AssistantSession | None:
    result = await db.execute(
        select(AssistantSession).where(
            AssistantSession.id == session_id,
            AssistantSession.tenant_id == tenant_id,
            AssistantSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    session.title = title[:120]
    await db.flush()
    await db.refresh(session)
    await db.commit()
    return session


async def move_session(
    db: AsyncSession,
    session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    folder_id: UUID | None,
) -> AssistantSession | None:
    result = await db.execute(
        select(AssistantSession).where(
            AssistantSession.id == session_id,
            AssistantSession.tenant_id == tenant_id,
            AssistantSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    # Validar que a pasta pertence ao tenant (se informada)
    if folder_id:
        f = await db.execute(
            select(AssistantFolder).where(
                AssistantFolder.id == folder_id,
                AssistantFolder.tenant_id == tenant_id,
            )
        )
        if not f.scalar_one_or_none():
            return None
    session.folder_id = folder_id
    await db.flush()
    await db.refresh(session)
    await db.commit()
    return session


async def share_session(
    db: AsyncSession,
    session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    shared: bool,
) -> AssistantSession | None:
    result = await db.execute(
        select(AssistantSession).where(
            AssistantSession.id == session_id,
            AssistantSession.tenant_id == tenant_id,
            AssistantSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    session.is_shared = shared
    session.shared_by = user_id if shared else None
    await db.flush()
    await db.refresh(session)
    await db.commit()
    return session


async def pin_session(
    db: AsyncSession,
    session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    pinned: bool,
) -> AssistantSession | None:
    result = await db.execute(
        select(AssistantSession).where(
            AssistantSession.id == session_id,
            AssistantSession.tenant_id == tenant_id,
            AssistantSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    session.pinned = pinned
    await db.flush()
    await db.refresh(session)
    await db.commit()
    return session


# ── Folder CRUD ───────────────────────────────────────────────────────────────

async def list_folders(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
) -> list[AssistantFolder]:
    """Pastas pessoais do usuário + pastas de equipe do tenant."""
    result = await db.execute(
        select(AssistantFolder)
        .where(
            AssistantFolder.tenant_id == tenant_id,
            or_(
                AssistantFolder.user_id == user_id,
                AssistantFolder.is_team.is_(True),
            ),
        )
        .order_by(AssistantFolder.is_team, AssistantFolder.name)
    )
    return list(result.scalars().all())


async def create_folder(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    name: str,
    color: str,
    is_team: bool,
) -> AssistantFolder:
    folder = AssistantFolder(
        tenant_id=tenant_id,
        user_id=None if is_team else user_id,
        name=name[:80],
        color=color,
        is_team=is_team,
    )
    db.add(folder)
    await db.flush()
    await db.refresh(folder)
    await db.commit()
    return folder


async def update_folder(
    db: AsyncSession,
    folder_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    name: str | None,
    color: str | None,
) -> AssistantFolder | None:
    result = await db.execute(
        select(AssistantFolder).where(
            AssistantFolder.id == folder_id,
            AssistantFolder.tenant_id == tenant_id,
            or_(
                AssistantFolder.user_id == user_id,
                AssistantFolder.is_team.is_(True),
            ),
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        return None
    if name is not None:
        folder.name = name[:80]
    if color is not None:
        folder.color = color
    await db.flush()
    await db.refresh(folder)
    await db.commit()
    return folder


async def delete_folder(
    db: AsyncSession,
    folder_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
) -> bool:
    result = await db.execute(
        select(AssistantFolder).where(
            AssistantFolder.id == folder_id,
            AssistantFolder.tenant_id == tenant_id,
            or_(
                AssistantFolder.user_id == user_id,
                AssistantFolder.is_team.is_(True),
            ),
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        return False
    # Sessões ficam com folder_id = NULL (ON DELETE SET NULL na FK)
    await db.delete(folder)
    await db.commit()
    return True
