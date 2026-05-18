"""Cross-domain automatic investigation service.

Analyzes problems across multiple security domains (firewall, network, n3, rmm)
using Claude. Each domain gets its own background task that reads recent
investigation syntheses from the tenant for context.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.investigation import InvestigationSession
from app.models.multi_domain import CrossDomainSession
from app.services.llm_provider import get_provider

log = logging.getLogger(__name__)

# Domain → agent_type mapping (aligns with InvestigationSession.agent_type)
_DOMAIN_TO_AGENT: dict[str, str] = {
    "firewall": "firewall",
    "network":  "network",
    "n3":       "n3",
    "rmm":      "rmm",
}

_DOMAIN_LABELS: dict[str, str] = {
    "firewall": "Firewall / Segurança de Rede",
    "network":  "Redes / Conectividade",
    "n3":       "Servidores / Infraestrutura",
    "rmm":      "Estações / Endpoints (RMM)",
}

_DOMAIN_ANALYSIS_SYSTEM = """\
Você é um especialista em diagnóstico de infraestrutura de segurança com foco em {domain_label}.
Sua tarefa é analisar um problema relatado pelo time de segurança do ponto de vista exclusivo do seu domínio.

CONTEXTO DISPONÍVEL:
- Descrição do problema fornecida pelo analista
- Investigações recentes realizadas pelo time no domínio {domain_label} (podem conter dados relevantes)

INSTRUÇÕES:
1. Analise o problema sob a ótica de {domain_label}
2. Use o contexto das investigações recentes para identificar padrões ou evidências relacionadas
3. Produza um diagnóstico focado e acionável
4. Indique claramente se o problema parece ter raízes em outro domínio

Formato da resposta (Markdown em Português do Brasil):

## Análise do Domínio: {domain_label}

### O que pode estar causando o problema neste domínio
[análise técnica detalhada]

### Evidências encontradas no histórico
[o que as investigações recentes mostram que é relevante — cite dados concretos se disponíveis]

### Diagnóstico provável
[conclusão do ponto de vista deste domínio]

### Indicadores de outros domínios
[se houver suspeita de envolvimento de outros domínios, descreva aqui; caso contrário, escreva "Nenhum"]

### Ações recomendadas
[lista de ações concretas para este domínio]
"""

_CORRELATION_SYSTEM = """\
Você é um especialista sênior em segurança e operações de infraestrutura.
Você receberá análises independentes de múltiplos domínios técnicos sobre um mesmo problema.

Sua tarefa é correlacionar essas análises e produzir um diagnóstico unificado.

Formato da resposta (Markdown em Português do Brasil):

## Diagnóstico Correlacionado — Investigação Multi-Domínio

### Resumo Executivo
[2-3 parágrafos explicando a causa raiz identificada cruzando os domínios]

### Correlações Identificadas
[o que os domínios têm em comum — eventos coincidentes, padrões complementares]

### Causa Raiz Mais Provável
[diagnóstico definitivo baseado na correlação]

### Plano de Ação Integrado
[ações ordenadas por prioridade, indicando qual domínio é responsável por cada ação]

### Domínio Primário do Problema
[qual domínio parece ser a origem — justifique]
"""

_DOMAIN_CHAT_SYSTEM = """\
Você é um especialista em {domain_label}.
Você está respondendo perguntas do analista sobre a análise que fez de um problema específico.

Contexto disponível:
- Problema original: {problem_description}
- Análise que você produziu: {domain_synthesis}

Responda em Português do Brasil. Seja técnico e direto.
Se o analista pedir para refazer a análise com novas informações, produza uma análise atualizada
no mesmo formato da análise original.
"""


async def _get_recent_syntheses(db: AsyncSession, tenant_id: uuid.UUID, agent_type: str, limit: int = 3) -> list[str]:
    """Fetch recent done investigation syntheses for context."""
    result = await db.execute(
        select(InvestigationSession)
        .where(
            InvestigationSession.tenant_id == tenant_id,
            InvestigationSession.agent_type == agent_type,
            InvestigationSession.status == "done",
            InvestigationSession.synthesis.isnot(None),
        )
        .order_by(desc(InvestigationSession.updated_at))
        .limit(limit)
    )
    sessions = result.scalars().all()
    return [s.synthesis for s in sessions if s.synthesis]


def _build_sub_result(domain: str, status: str, synthesis: str | None = None,
                      error: str | None = None, investigation_session_id: str | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "domain": domain,
        "status": status,
        "investigation_session_id": investigation_session_id,
        "synthesis": synthesis,
        "error": error,
        "started_at": now if status == "running" else None,
        "finished_at": now if status in ("done", "error") else None,
    }


async def _analyze_domain_background(session_id: uuid.UUID, tenant_id: uuid.UUID, domain: str,
                                      problem_description: str) -> None:
    """Background task: analyze one domain and update sub_results in the DB."""
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(CrossDomainSession).where(CrossDomainSession.id == session_id))
            session = result.scalar_one_or_none()
            if not session:
                return

            # Mark this domain as running
            sub_results: list[dict] = list(session.sub_results or [])
            for sr in sub_results:
                if sr["domain"] == domain:
                    sr["status"] = "running"
                    sr["started_at"] = datetime.now(timezone.utc).isoformat()
            session.sub_results = sub_results
            await db.commit()

            # Gather context from recent investigations
            agent_type = _DOMAIN_TO_AGENT.get(domain, domain)
            recent = await _get_recent_syntheses(db, tenant_id, agent_type)
            context_block = ""
            if recent:
                context_block = "\n\n### Investigações Recentes do Time neste Domínio\n"
                for i, s in enumerate(recent, 1):
                    context_block += f"\n**Investigação {i}:**\n{s}\n"

            domain_label = _DOMAIN_LABELS.get(domain, domain)
            system = _DOMAIN_ANALYSIS_SYSTEM.format(domain_label=domain_label)
            user_msg = f"## Problema Relatado\n\n{problem_description}{context_block}"

            provider = get_provider(None)
            synthesis, _, _ = await provider.chat(
                [{"role": "user", "content": user_msg}],
                system=system,
            )

            # Update sub_result with synthesis
            result2 = await db.execute(select(CrossDomainSession).where(CrossDomainSession.id == session_id))
            session = result2.scalar_one_or_none()
            if not session:
                return

            sub_results = list(session.sub_results or [])
            for sr in sub_results:
                if sr["domain"] == domain:
                    sr["status"] = "done"
                    sr["synthesis"] = synthesis
                    sr["finished_at"] = datetime.now(timezone.utc).isoformat()

            # Check if all domains are done
            all_done = all(sr["status"] in ("done", "error") for sr in sub_results)
            session.sub_results = sub_results
            if all_done:
                session.status = "done"

            await db.commit()

        except Exception as exc:
            log.error("cross_domain background error domain=%s session=%s: %s", domain, session_id, exc)
            async with AsyncSessionLocal() as db2:
                result3 = await db2.execute(select(CrossDomainSession).where(CrossDomainSession.id == session_id))
                sess = result3.scalar_one_or_none()
                if sess:
                    sub_results = list(sess.sub_results or [])
                    for sr in sub_results:
                        if sr["domain"] == domain:
                            sr["status"] = "error"
                            sr["error"] = str(exc)
                            sr["finished_at"] = datetime.now(timezone.utc).isoformat()
                    all_done = all(sr["status"] in ("done", "error") for sr in sub_results)
                    sess.sub_results = sub_results
                    if all_done:
                        sess.status = "done"
                    await db2.commit()


async def start_session(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID,
                        problem_description: str, domains: list[str]) -> CrossDomainSession:
    """Create a new cross-domain session and launch background analysis tasks."""
    initial_sub_results = [_build_sub_result(d, "pending") for d in domains]

    session = CrossDomainSession(
        tenant_id=tenant_id,
        user_id=user_id,
        problem_description=problem_description,
        domains=domains,
        status="running",
        sub_results=initial_sub_results,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    session_id = session.id

    # Launch one background task per domain (non-blocking)
    for domain in domains:
        asyncio.ensure_future(
            _analyze_domain_background(session_id, tenant_id, domain, problem_description)
        )

    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: uuid.UUID, tenant_id: uuid.UUID) -> CrossDomainSession | None:
    result = await db.execute(
        select(CrossDomainSession).where(
            CrossDomainSession.id == session_id,
            CrossDomainSession.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def list_sessions(db: AsyncSession, tenant_id: uuid.UUID) -> list[CrossDomainSession]:
    result = await db.execute(
        select(CrossDomainSession)
        .where(CrossDomainSession.tenant_id == tenant_id)
        .order_by(desc(CrossDomainSession.created_at))
    )
    return list(result.scalars().all())


async def correlate(db: AsyncSession, session: CrossDomainSession) -> CrossDomainSession:
    """Run Claude correlation across all done sub-results."""
    done_results = [sr for sr in (session.sub_results or []) if sr.get("status") == "done" and sr.get("synthesis")]
    if not done_results:
        return session

    parts = [f"## Análise do Domínio: {_DOMAIN_LABELS.get(sr['domain'], sr['domain'])}\n\n{sr['synthesis']}"
             for sr in done_results]
    user_msg = f"### Problema Original\n\n{session.problem_description}\n\n---\n\n" + "\n\n---\n\n".join(parts)

    provider = get_provider(None)
    correlation, _, _ = await provider.chat(
        [{"role": "user", "content": user_msg}],
        system=_CORRELATION_SYSTEM,
    )

    session.correlation = correlation
    await db.commit()
    await db.refresh(session)
    return session


async def rerun_domain(db: AsyncSession, session: CrossDomainSession,
                       domain: str, additional_context: str | None = None) -> CrossDomainSession:
    """Rerun a specific domain analysis, optionally with extra context."""
    sub_results = list(session.sub_results or [])
    found = any(sr["domain"] == domain for sr in sub_results)
    if not found:
        return session

    # Reset to pending so UI shows running
    for sr in sub_results:
        if sr["domain"] == domain:
            sr["status"] = "pending"
            sr["synthesis"] = None
            sr["error"] = None
            sr["started_at"] = None
            sr["finished_at"] = None

    session.sub_results = sub_results
    session.status = "running"
    await db.commit()
    await db.refresh(session)

    problem = session.problem_description
    if additional_context:
        problem = f"{problem}\n\n### Contexto Adicional Fornecido pelo Analista\n\n{additional_context}"

    asyncio.ensure_future(
        _analyze_domain_background(session.id, session.tenant_id, domain, problem)
    )

    return session


async def chat_in_domain(db: AsyncSession, session: CrossDomainSession,
                         domain: str, message: str) -> str:
    """Send a message to a specific domain's analysis context and get a response."""
    domain_sr = next((sr for sr in (session.sub_results or []) if sr["domain"] == domain), None)
    synthesis = domain_sr.get("synthesis", "") if domain_sr else ""
    domain_label = _DOMAIN_LABELS.get(domain, domain)

    system = _DOMAIN_CHAT_SYSTEM.format(
        domain_label=domain_label,
        problem_description=session.problem_description,
        domain_synthesis=synthesis or "(análise ainda não concluída)",
    )

    provider = get_provider(None)
    response, _, _ = await provider.chat(
        [{"role": "user", "content": message}],
        system=system,
    )
    return response


async def delete_session(db: AsyncSession, session: CrossDomainSession) -> None:
    await db.delete(session)
    await db.commit()
