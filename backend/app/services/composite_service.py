"""Composite (coordinated) investigation service.

Manages human-coordinated investigations where specialists work independently
per domain and an N3/admin consolidates their findings using Claude.
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.multi_domain import CompositeInvestigation, SubInvestigation
from app.services.llm_provider import get_provider

log = logging.getLogger(__name__)

_CONSOLIDATION_SYSTEM = """\
Você é um especialista N3 sênior em segurança e operações de infraestrutura.
Você receberá os achados de múltiplos especialistas de domínio sobre um mesmo sintoma.

Sua tarefa é consolidar esses achados em um diagnóstico unificado e um plano de ação.

Formato da resposta (Markdown em Português do Brasil):

## Consolidação — Investigação Composta

### Sintoma Investigado
[repita o sintoma original em uma frase]

### Achados por Domínio
[bullet points resumindo os achados mais relevantes de cada domínio]

### Correlações e Causa Raiz
[cruzamento dos achados — o que um domínio confirma do outro; causa raiz identificada]

### Diagnóstico Final
[conclusão clara e objetiva]

### Plano de Ação Integrado
[ações ordenadas por prioridade, indicando domínio responsável por cada ação]

### Próximos Passos
[o que fazer imediatamente após esta análise]
"""

_ACTION_PLAN_SYSTEM = """\
Você é um especialista N3 em segurança e operações de infraestrutura.
Com base na consolidação de uma investigação composta, gere um plano de ação executável e detalhado.

Formato da resposta (Markdown em Português do Brasil):

## Plano de Ação — Investigação Composta

### Objetivo
[o que este plano visa resolver]

### Escopo
[sistemas e domínios afetados]

### Ações Imediatas (hoje)
[lista numerada de ações urgentes]

### Ações de Curto Prazo (próximos 7 dias)
[lista numerada]

### Ações de Médio Prazo (próximos 30 dias)
[lista numerada]

### Critérios de Sucesso
[como saber que o problema foi resolvido]

### Riscos e Mitigações
[o que pode dar errado e como mitigar]
"""

_CHAT_SYSTEM = """\
Você é um especialista N3 em segurança e operações de infraestrutura.
Está conduzindo uma investigação composta coordenada.

Contexto:
- Sintoma: {symptom}
- Status: {status}
- Domínios em investigação: {domains}
- Consolidação atual: {consolidation}

Responda perguntas do analista em Português do Brasil.
Seja técnico, direto e colaborativo.
"""


async def create_composite(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    created_by_id: uuid.UUID,
    created_by_name: str,
    symptom: str,
    domains: list[str],
) -> CompositeInvestigation:
    inv = CompositeInvestigation(
        tenant_id=tenant_id,
        created_by_id=created_by_id,
        created_by_name=created_by_name,
        symptom=symptom,
        domains=domains,
        status="active",
    )
    db.add(inv)
    await db.flush()
    await db.refresh(inv)

    for domain in domains:
        sub = SubInvestigation(
            composite_id=inv.id,
            domain=domain,
            status="pending",
        )
        db.add(sub)

    await db.commit()
    await db.refresh(inv)
    return inv


async def get_composite(
    db: AsyncSession, composite_id: uuid.UUID, tenant_id: uuid.UUID
) -> CompositeInvestigation | None:
    result = await db.execute(
        select(CompositeInvestigation).where(
            CompositeInvestigation.id == composite_id,
            CompositeInvestigation.tenant_id == tenant_id,
        )
    )
    inv = result.scalar_one_or_none()
    if inv:
        # eagerly load sub_investigations
        await db.refresh(inv, ["sub_investigations"])
    return inv


async def list_composites(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[CompositeInvestigation]:
    result = await db.execute(
        select(CompositeInvestigation)
        .where(CompositeInvestigation.tenant_id == tenant_id)
        .order_by(desc(CompositeInvestigation.created_at))
    )
    invs = list(result.scalars().all())
    for inv in invs:
        await db.refresh(inv, ["sub_investigations"])
    return invs


async def assign_sub(
    db: AsyncSession,
    sub: SubInvestigation,
    assigned_to_id: uuid.UUID,
    assigned_to_name: str,
) -> SubInvestigation:
    sub.assigned_to_id = assigned_to_id
    sub.assigned_to_name = assigned_to_name
    sub.status = "assigned"
    await db.commit()
    await db.refresh(sub)
    return sub


async def submit_findings(
    db: AsyncSession,
    sub: SubInvestigation,
    findings: str,
    investigation_session_id: uuid.UUID | None = None,
) -> SubInvestigation:
    sub.findings = findings
    sub.status = "submitted"
    sub.submitted_at = datetime.now(timezone.utc)
    if investigation_session_id:
        sub.investigation_session_id = investigation_session_id
    await db.commit()
    await db.refresh(sub)
    return sub


async def escalate_sub(db: AsyncSession, sub: SubInvestigation) -> SubInvestigation:
    sub.status = "escalated"
    await db.commit()
    await db.refresh(sub)
    return sub


async def reopen_sub(db: AsyncSession, sub: SubInvestigation) -> SubInvestigation:
    """Reopen a submitted sub-investigation so the specialist can add more findings."""
    sub.status = "in_progress"
    sub.submitted_at = None
    await db.commit()
    await db.refresh(sub)
    return sub


async def consolidate(
    db: AsyncSession, inv: CompositeInvestigation
) -> CompositeInvestigation:
    """Run Claude consolidation over all submitted sub-investigation findings."""
    await db.refresh(inv, ["sub_investigations"])
    submitted = [s for s in inv.sub_investigations if s.findings]
    if not submitted:
        return inv

    inv.status = "consolidating"
    await db.commit()

    parts = [
        f"## Domínio: {s.domain}\n\n**Especialista:** {s.assigned_to_name or 'Não atribuído'}\n\n{s.findings}"
        for s in submitted
    ]
    user_msg = f"### Sintoma Original\n\n{inv.symptom}\n\n---\n\n" + "\n\n---\n\n".join(parts)

    provider = get_provider(None)
    consolidation, _, _ = await provider.chat(
        [{"role": "user", "content": user_msg}],
        system=_CONSOLIDATION_SYSTEM,
    )

    inv.consolidation = consolidation
    inv.status = "active"
    await db.commit()
    await db.refresh(inv)
    return inv


async def generate_action_plan(
    db: AsyncSession,
    inv: CompositeInvestigation,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> CompositeInvestigation:
    """Create an AI Assistant session with the action plan for this investigation."""
    from app.models.assistant import AssistantMessage, AssistantSession

    if not inv.consolidation:
        return inv

    provider = get_provider(None)
    plan_content, _, _ = await provider.chat(
        [{"role": "user", "content": f"### Consolidação\n\n{inv.consolidation}\n\n### Sintoma Original\n\n{inv.symptom}"}],
        system=_ACTION_PLAN_SYSTEM,
    )

    asst_session = AssistantSession(
        tenant_id=tenant_id,
        user_id=user_id,
        title=f"Plano de Ação: {inv.symptom[:60]}",
        model_used="claude-sonnet-4-6",
    )
    db.add(asst_session)
    await db.flush()
    await db.refresh(asst_session)

    seed_content = (
        f"**Plano de Ação gerado a partir da Investigação Composta**\n\n"
        f"Sintoma: {inv.symptom}\n\n"
        f"{plan_content}\n\n"
        "O que mais você precisa sobre este plano de ação?"
    )
    db.add(AssistantMessage(
        session_id=asst_session.id,
        role="assistant",
        content=seed_content,
        model="claude-sonnet-4-6",
        input_tokens=0,
        output_tokens=0,
    ))

    inv.action_plan_session_id = asst_session.id
    await db.commit()
    await db.refresh(inv)
    return inv


async def resolve_composite(
    db: AsyncSession, inv: CompositeInvestigation
) -> CompositeInvestigation:
    inv.status = "resolved"
    await db.commit()
    await db.refresh(inv)
    return inv


async def chat_in_composite(
    db: AsyncSession,
    inv: CompositeInvestigation,
    message: str,
) -> str:
    await db.refresh(inv, ["sub_investigations"])
    domains_str = ", ".join(inv.domains or [])
    system = _CHAT_SYSTEM.format(
        symptom=inv.symptom,
        status=inv.status,
        domains=domains_str,
        consolidation=inv.consolidation or "(consolidação ainda não realizada)",
    )

    provider = get_provider(None)
    response, _, _ = await provider.chat(
        [{"role": "user", "content": message}],
        system=system,
    )
    return response


async def delete_composite(
    db: AsyncSession, inv: CompositeInvestigation
) -> None:
    await db.delete(inv)
    await db.commit()


async def get_sub_investigation(
    db: AsyncSession, sub_id: uuid.UUID, tenant_id: uuid.UUID
) -> SubInvestigation | None:
    result = await db.execute(
        select(SubInvestigation)
        .join(CompositeInvestigation, SubInvestigation.composite_id == CompositeInvestigation.id)
        .where(
            SubInvestigation.id == sub_id,
            CompositeInvestigation.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def list_my_sub_investigations(
    db: AsyncSession, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> list[SubInvestigation]:
    result = await db.execute(
        select(SubInvestigation)
        .join(CompositeInvestigation, SubInvestigation.composite_id == CompositeInvestigation.id)
        .where(
            SubInvestigation.assigned_to_id == user_id,
            CompositeInvestigation.tenant_id == tenant_id,
        )
        .order_by(desc(SubInvestigation.created_at))
    )
    return list(result.scalars().all())
