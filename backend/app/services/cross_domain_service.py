"""Cross-domain automatic investigation service.

Analyzes problems across multiple security domains (firewall, network, n3, rmm)
using Claude. Each domain gets its own background task that reads recent
investigation syntheses from the tenant for context, optionally enriched with
RAG from the Knowledge Base and device-specific context.
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone

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

# RAG queries per domain — used to search the tenant's Knowledge Base
_DOMAIN_RAG_QUERIES: dict[str, str] = {
    "firewall": "firewall regras segurança política acesso NAT VPN bloqueio",
    "network":  "rede switch roteamento conectividade BGP OSPF topologia VLAN",
    "n3":       "servidor infraestrutura sistema operacional aplicação serviço processo",
    "rmm":      "estação workstation endpoint agente monitoramento desktop",
}

# Regex for extracting IPs and hostnames from problem descriptions
_IP_RE       = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
_HOSTNAME_RE = re.compile(r'\b([a-zA-Z][a-zA-Z0-9\-]{2,}(?:\.[a-zA-Z0-9\-]+){1,})\b')

_DOMAIN_ANALYSIS_SYSTEM = """\
Você é um especialista em diagnóstico de infraestrutura de segurança com foco em {domain_label}.
Sua tarefa é analisar um problema relatado pelo time de segurança do ponto de vista exclusivo do seu domínio.

CONTEXTO DISPONÍVEL:
- Descrição do problema fornecida pelo analista
- Investigações recentes realizadas pelo time no domínio {domain_label} (podem conter dados relevantes)
- Documentação da Base de Conhecimento do tenant (quando disponível)
- Contexto de dispositivos específicos (quando selecionados pelo analista)

INSTRUÇÕES:
1. Analise o problema sob a ótica de {domain_label}
2. Use o contexto das investigações recentes para identificar padrões ou evidências relacionadas
3. Use a documentação da Base de Conhecimento para referenciar procedimentos ou configurações conhecidas
4. Se dispositivos foram selecionados, foque a análise neles prioritariamente
5. Produza um diagnóstico focado e acionável
6. Indique claramente se o problema parece ter raízes em outro domínio

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


# ── RAG & device context helpers ──────────────────────────────────────────────

def _extract_rag_titles(rag_text: str) -> list[str]:
    """Parse BookStack page names from semantic_search output."""
    return re.findall(r'^## (.+)$', rag_text, re.MULTILINE)


async def _get_rag_context(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    domain: str,
) -> tuple[str, list[str]]:
    """Search the tenant KB for domain-relevant content.

    Returns (rag_text, title_list). Both empty when no OpenAI key or no KB indexed.
    """
    from app.services.embedding_service import semantic_search

    query    = _DOMAIN_RAG_QUERIES.get(domain, domain)
    rag_text = await semantic_search(db, tenant_id, query, top_k=5)
    titles   = _extract_rag_titles(rag_text) if rag_text else []
    return rag_text, titles


async def _get_device_context(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    domain: str,
    device_ids: list[str],
) -> str:
    """Build a text block describing the analyst-selected devices for the domain."""
    if not device_ids:
        return ""

    lines: list[str] = []

    if domain in ("firewall", "network"):
        from app.models.device import Device

        try:
            uids = [uuid.UUID(did) for did in device_ids]
        except ValueError:
            return ""

        result = await db.execute(
            select(Device).where(Device.id.in_(uids), Device.tenant_id == tenant_id)
        )
        devices = result.scalars().all()
        if devices:
            lines.append("### Dispositivos Selecionados para Análise")
            for d in devices:
                lines.append(
                    f"- **{d.name}** ({d.vendor.value}) — Host: {d.host} — Status: {d.status.value}"
                )

    elif domain == "n3":
        from app.models.server import Server

        try:
            uids = [uuid.UUID(did) for did in device_ids]
        except ValueError:
            return ""

        result = await db.execute(
            select(Server).where(Server.id.in_(uids), Server.tenant_id == tenant_id)
        )
        servers = result.scalars().all()
        if servers:
            lines.append("### Servidores Selecionados para Análise")
            for s in servers:
                lines.append(
                    f"- **{s.name}** ({s.os_type.value}) — Host: {s.host}"
                )

    elif domain == "rmm":
        from app.models.rmm import RmmAgent

        try:
            uids = [uuid.UUID(did) for did in device_ids]
        except ValueError:
            return ""

        result = await db.execute(select(RmmAgent).where(RmmAgent.id.in_(uids)))
        agents = result.scalars().all()
        if agents:
            lines.append("### Estações Selecionadas para Análise")
            for a in agents:
                lines.append(f"- **{a.hostname}** — IP: {a.ip_address or 'N/A'}")

    return "\n".join(lines)


async def identify_devices(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    problem_description: str,
) -> dict[str, list[dict]]:
    """Extract IPs/hostnames from the problem text and match against managed devices.

    Returns a dict like {"firewall": [...], "network": [...], "n3": [...]} where
    each value is a list of {"id", "name", "vendor"/"os_type", "host"} dicts.
    """
    from app.models.device import Device, DeviceCategory
    from app.models.server import Server

    ips       = set(_IP_RE.findall(problem_description))
    hostnames = {m.lower() for m in _HOSTNAME_RE.findall(problem_description)}
    candidates = ips | hostnames

    if not candidates:
        return {}

    result: dict[str, list[dict]] = {}

    # Match against managed devices (firewall + network categories)
    dev_result = await db.execute(select(Device).where(Device.tenant_id == tenant_id))
    devices    = dev_result.scalars().all()

    fw_devices: list[dict] = []
    net_devices: list[dict] = []

    for d in devices:
        matched = any(
            c in (d.host or "").lower() or c in d.name.lower()
            for c in candidates
        )
        if not matched:
            continue
        entry = {"id": str(d.id), "name": d.name, "vendor": d.vendor.value, "host": d.host}
        if d.category == DeviceCategory.firewall:
            fw_devices.append(entry)
        elif d.category in (DeviceCategory.switch, DeviceCategory.routing):
            net_devices.append(entry)

    if fw_devices:
        result["firewall"] = fw_devices
    if net_devices:
        result["network"] = net_devices

    # Match against servers (n3)
    srv_result = await db.execute(select(Server).where(Server.tenant_id == tenant_id))
    servers    = srv_result.scalars().all()

    n3_devices: list[dict] = []
    for s in servers:
        matched = any(
            c in (s.host or "").lower() or c in s.name.lower()
            for c in candidates
        )
        if matched:
            n3_devices.append(
                {"id": str(s.id), "name": s.name, "host": s.host, "os_type": s.os_type.value}
            )

    if n3_devices:
        result["n3"] = n3_devices

    return result


# ── Investigation history ─────────────────────────────────────────────────────

async def _get_recent_syntheses(
    db: AsyncSession, tenant_id: uuid.UUID, agent_type: str, limit: int = 3
) -> list[str]:
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


# ── Sub-result builder ────────────────────────────────────────────────────────

def _build_sub_result(
    domain: str,
    status: str,
    synthesis: str | None = None,
    error: str | None = None,
    investigation_session_id: str | None = None,
    rag_docs_found: int = 0,
    rag_doc_titles: list[str] | None = None,
    device_ids: list[str] | None = None,
    mode: str = "diagnostico",
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "domain": domain,
        "status": status,
        "investigation_session_id": investigation_session_id,
        "synthesis": synthesis,
        "error": error,
        "started_at": now if status == "running" else None,
        "finished_at": now if status in ("done", "error") else None,
        "rag_docs_found": rag_docs_found,
        "rag_doc_titles": rag_doc_titles or [],
        "device_ids": device_ids or [],
        "mode": mode,
    }


# ── Background analysis task ──────────────────────────────────────────────────

async def _analyze_domain_background(
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    domain: str,
    problem_description: str,
    device_ids: list[str] | None = None,
    mode: str = "diagnostico",
) -> None:
    """Background task: analyze one domain and update sub_results in the DB."""
    device_ids = device_ids or []

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(CrossDomainSession).where(CrossDomainSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            if not session:
                return

            # Mark this domain as running
            sub_results: list[dict] = list(session.sub_results or [])
            for sr in sub_results:
                if sr["domain"] == domain:
                    sr["status"]     = "running"
                    sr["started_at"] = datetime.now(timezone.utc).isoformat()
            session.sub_results = sub_results
            await db.commit()

            # ── Gather investigation history (skip in "consulta" mode) ──────
            agent_type   = _DOMAIN_TO_AGENT.get(domain, domain)
            context_block = ""
            if mode != "consulta":
                recent = await _get_recent_syntheses(db, tenant_id, agent_type)
                if recent:
                    context_block = "\n\n### Investigações Recentes do Time neste Domínio\n"
                    for i, s in enumerate(recent, 1):
                        context_block += f"\n**Investigação {i}:**\n{s}\n"

            # ── RAG from Knowledge Base (always, silently ignored if no key) ─
            rag_text, rag_titles = await _get_rag_context(db, tenant_id, domain)
            rag_block = ""
            if rag_text:
                rag_block = f"\n\n### Documentação da Base de Conhecimento\n\n{rag_text}"

            # ── Device context (when analyst selected specific devices) ──────
            device_block = ""
            if device_ids:
                device_block_raw = await _get_device_context(db, tenant_id, domain, device_ids)
                if device_block_raw:
                    device_block = f"\n\n{device_block_raw}"

            domain_label = _DOMAIN_LABELS.get(domain, domain)
            system   = _DOMAIN_ANALYSIS_SYSTEM.format(domain_label=domain_label)
            user_msg = (
                f"## Problema Relatado\n\n{problem_description}"
                f"{context_block}"
                f"{rag_block}"
                f"{device_block}"
            )

            provider = get_provider(None)
            synthesis, _, _ = await provider.chat(
                [{"role": "user", "content": user_msg}],
                system=system,
            )

            # ── Persist result ────────────────────────────────────────────────
            result2 = await db.execute(
                select(CrossDomainSession).where(CrossDomainSession.id == session_id)
            )
            session = result2.scalar_one_or_none()
            if not session:
                return

            sub_results = list(session.sub_results or [])
            for sr in sub_results:
                if sr["domain"] == domain:
                    sr["status"]          = "done"
                    sr["synthesis"]       = synthesis
                    sr["finished_at"]     = datetime.now(timezone.utc).isoformat()
                    sr["rag_docs_found"]  = len(rag_titles)
                    sr["rag_doc_titles"]  = rag_titles

            all_done = all(sr["status"] in ("done", "error") for sr in sub_results)
            session.sub_results = sub_results
            if all_done:
                session.status = "done"

            await db.commit()

        except Exception as exc:
            log.error(
                "cross_domain background error domain=%s session=%s: %s",
                domain, session_id, exc,
            )
            async with AsyncSessionLocal() as db2:
                result3 = await db2.execute(
                    select(CrossDomainSession).where(CrossDomainSession.id == session_id)
                )
                sess = result3.scalar_one_or_none()
                if sess:
                    sub_results = list(sess.sub_results or [])
                    for sr in sub_results:
                        if sr["domain"] == domain:
                            sr["status"]      = "error"
                            sr["error"]       = str(exc)
                            sr["finished_at"] = datetime.now(timezone.utc).isoformat()
                    all_done = all(sr["status"] in ("done", "error") for sr in sub_results)
                    sess.sub_results = sub_results
                    if all_done:
                        sess.status = "done"
                    await db2.commit()


# ── Public service functions ──────────────────────────────────────────────────

async def start_session(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    problem_description: str,
    domains: list[str],
    domain_devices: dict[str, list[str]] | None = None,
    mode: str = "diagnostico",
) -> CrossDomainSession:
    """Create a new cross-domain session and launch background analysis tasks."""
    domain_devices = domain_devices or {}

    initial_sub_results = [
        _build_sub_result(
            d, "pending",
            device_ids=domain_devices.get(d, []),
            mode=mode,
        )
        for d in domains
    ]

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

    for domain in domains:
        asyncio.ensure_future(
            _analyze_domain_background(
                session_id, tenant_id, domain, problem_description,
                device_ids=domain_devices.get(domain, []),
                mode=mode,
            )
        )

    await db.commit()
    await db.refresh(session)
    return session


async def get_session(
    db: AsyncSession, session_id: uuid.UUID, tenant_id: uuid.UUID
) -> CrossDomainSession | None:
    result = await db.execute(
        select(CrossDomainSession).where(
            CrossDomainSession.id == session_id,
            CrossDomainSession.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def list_sessions(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[CrossDomainSession]:
    result = await db.execute(
        select(CrossDomainSession)
        .where(CrossDomainSession.tenant_id == tenant_id)
        .order_by(desc(CrossDomainSession.created_at))
    )
    return list(result.scalars().all())


async def correlate(
    db: AsyncSession, session: CrossDomainSession
) -> CrossDomainSession:
    """Run Claude correlation across all done sub-results."""
    done_results = [
        sr for sr in (session.sub_results or [])
        if sr.get("status") == "done" and sr.get("synthesis")
    ]
    if not done_results:
        return session

    parts = [
        f"## Análise do Domínio: {_DOMAIN_LABELS.get(sr['domain'], sr['domain'])}\n\n{sr['synthesis']}"
        for sr in done_results
    ]
    user_msg = (
        f"### Problema Original\n\n{session.problem_description}\n\n---\n\n"
        + "\n\n---\n\n".join(parts)
    )

    provider = get_provider(None)
    correlation, _, _ = await provider.chat(
        [{"role": "user", "content": user_msg}],
        system=_CORRELATION_SYSTEM,
    )

    session.correlation = correlation
    await db.commit()
    await db.refresh(session)
    return session


async def rerun_domain(
    db: AsyncSession,
    session: CrossDomainSession,
    domain: str,
    additional_context: str | None = None,
) -> CrossDomainSession:
    """Rerun a specific domain analysis, preserving device_ids and mode from prior run."""
    sub_results = list(session.sub_results or [])
    found = any(sr["domain"] == domain for sr in sub_results)
    if not found:
        return session

    # Preserve device_ids and mode from the stored sub_result
    prior_sr    = next((sr for sr in sub_results if sr["domain"] == domain), {})
    device_ids  = prior_sr.get("device_ids", [])
    mode        = prior_sr.get("mode", "diagnostico")

    for sr in sub_results:
        if sr["domain"] == domain:
            sr["status"]    = "pending"
            sr["synthesis"] = None
            sr["error"]     = None
            sr["started_at"]  = None
            sr["finished_at"] = None

    session.sub_results = sub_results
    session.status = "running"
    await db.commit()
    await db.refresh(session)

    problem = session.problem_description
    if additional_context:
        problem = (
            f"{problem}\n\n### Contexto Adicional Fornecido pelo Analista\n\n{additional_context}"
        )

    asyncio.ensure_future(
        _analyze_domain_background(
            session.id, session.tenant_id, domain, problem,
            device_ids=device_ids,
            mode=mode,
        )
    )

    return session


async def chat_in_domain(
    db: AsyncSession, session: CrossDomainSession, domain: str, message: str
) -> str:
    """Send a message to a specific domain's analysis context and get a response."""
    domain_sr  = next((sr for sr in (session.sub_results or []) if sr["domain"] == domain), None)
    synthesis  = domain_sr.get("synthesis", "") if domain_sr else ""
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
