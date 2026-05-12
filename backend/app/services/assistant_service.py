"""Fase 40-B: AI Assistant Service — orquestra RAG + LLM + audit hash-chain."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import AssistantMessage, AssistantSession
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


async def _get_or_create_session(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    session_id: UUID | None,
    model_preference: str | None,
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
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


async def _load_history(db: AsyncSession, session_id: UUID, limit: int = 20) -> list[dict[str, str]]:
    result = await db.execute(
        select(AssistantMessage)
        .where(AssistantMessage.session_id == session_id)
        .order_by(AssistantMessage.created_at)
        .limit(limit)
    )
    return [{"role": m.role, "content": m.content} for m in result.scalars().all()]


async def send_message(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    user_role: TenantRole,
    session_id: UUID | None,
    content: str,
    model_preference: str | None,
) -> tuple[AssistantSession, AssistantMessage]:
    # Guardrail básico: detectar tentativa de injeção antes de processar
    from app.agent.guardrails import check_action_plan
    _safe_plan: dict = {"intent": "assistant_query", "ssh_commands": [], "raw_intent_data": {"description": content}}
    _gr = check_action_plan(_safe_plan, content)
    if _gr.blocked:
        raise ValueError(f"Mensagem bloqueada pela política de segurança: {_gr.block_reason}")

    session = await _get_or_create_session(db, tenant_id, user_id, session_id, model_preference)

    # Salvar mensagem do usuário com hash
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

    # Construir contexto via RAG + data scope
    context = await build_context_for_query(db, tenant_id, user_role, content)
    system = _ASSISTANT_SYSTEM_TEMPLATE.replace("{context}", context or "(nenhum contexto disponível)")

    # Histórico de mensagens para o LLM (sem a mensagem atual — já incluída abaixo)
    history = await _load_history(db, session.id, limit=18)

    # Garantir que a msg do usuário está no histórico para o LLM
    if not history or history[-1]["content"] != content:
        history.append({"role": "user", "content": content})

    # Chamar LLM
    provider = get_provider(model_preference or session.model_used)
    response_text, input_tok, output_tok = await provider.chat(history, system)

    # Salvar resposta com hash encadeado
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

    # Atualizar sessão
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


async def list_sessions(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    limit: int = 50,
) -> list[AssistantSession]:
    result = await db.execute(
        select(AssistantSession)
        .where(
            AssistantSession.tenant_id == tenant_id,
            AssistantSession.user_id == user_id,
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
