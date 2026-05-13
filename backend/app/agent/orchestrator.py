"""MultiAgentOrchestrator — coordena sub-agentes por domínio.

Fluxo:
  1. Recebe query em linguagem natural
  2. Identifica quais sub-agentes podem tratar (pode ser mais de um em paralelo)
  3. Executa sub-agentes (paralelos quando independentes)
  4. Consolida resultado via LLM
  5. Registra em orchestration_runs + ai_interactions
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.agent.sub_agents.base import AgentHandoff
from app.agent.sub_agents.firewall_agent import FirewallAgent
from app.agent.sub_agents.identity_agent import IdentityAgent
from app.agent.sub_agents.network_agent import NetworkAgent

_CONFIDENCE_THRESHOLD = 0.70   # abaixo disso → awaiting_approval automático

_CONSOLIDATE_SYSTEM = """\
Você é o orquestrador do Eternity SecOps. Recebeu os resultados de múltiplos sub-agentes \
especializados e deve consolidar uma resposta única, coerente e estruturada para o analista.
Responda em português. Seja objetivo. Se algum sub-agente requer aprovação humana, indique \
claramente qual ação precisa de aprovação antes de executar."""


class MultiAgentOrchestrator:
    """Orquestrador principal — instanciado por requisição (stateless)."""

    def __init__(self) -> None:
        self._agents = [FirewallAgent(), IdentityAgent(), NetworkAgent()]

    async def run(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        db=None,
        tenant_id: UUID | None = None,
        user_id: UUID | None = None,
        operation_id: UUID | None = None,
    ) -> dict[str, Any]:
        context = context or {}
        started_at = datetime.now(timezone.utc)

        # 1. Descobrir quais agentes podem tratar
        eligible = [a for a in self._agents if await a.can_handle(query)]
        if not eligible:
            eligible = [self._agents[0]]   # fallback: FirewallAgent

        # 2. Executar em paralelo
        tasks = [agent.handle(query, context) for agent in eligible]
        handoffs: list[AgentHandoff] = await asyncio.gather(*tasks, return_exceptions=False)

        # 3. Calcular confiança global (mínima entre agentes)
        overall_confidence = min((h.confidence for h in handoffs), default=1.0)
        requires_approval = any(h.requires_approval for h in handoffs) or (
            overall_confidence < _CONFIDENCE_THRESHOLD
        )

        # 4. Consolidar resposta
        consolidated = await self._consolidate(query, handoffs)

        run_result = {
            "query": query,
            "agents_invoked": [h.agent for h in handoffs],
            "handoffs": [
                {
                    "agent": h.agent,
                    "success": h.success,
                    "result": h.result,
                    "actions_taken": h.actions_taken,
                    "requires_approval": h.requires_approval,
                    "confidence": h.confidence,
                    "error": h.error,
                    "next_steps": h.next_steps,
                }
                for h in handoffs
            ],
            "consolidated_response": consolidated,
            "overall_confidence": overall_confidence,
            "requires_approval": requires_approval,
            "status": "completed",
            "duration_ms": int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000),
        }

        # 5. Persistir orchestration_run (best-effort)
        if db and tenant_id:
            await self._persist_run(
                db, tenant_id, user_id, operation_id, query, run_result
            )

        return run_result

    async def _consolidate(self, query: str, handoffs: list[AgentHandoff]) -> str:
        from app.services.llm_provider import get_provider

        if len(handoffs) == 1 and handoffs[0].result.get("plan_text"):
            return handoffs[0].result["plan_text"]

        summary_parts = []
        for h in handoffs:
            if h.error:
                summary_parts.append(f"[{h.agent}] ERRO: {h.error}")
            else:
                summary_parts.append(f"[{h.agent}] {h.result}")

        provider = get_provider(None)
        content = (
            f"Consulta original: {query}\n\n"
            f"Resultados dos sub-agentes:\n" + "\n\n".join(summary_parts)
        )
        messages = [{"role": "user", "content": content}]
        response, _, _ = await provider.chat(messages, _CONSOLIDATE_SYSTEM)
        return response

    async def _persist_run(
        self,
        db,
        tenant_id: UUID,
        user_id: UUID | None,
        operation_id: UUID | None,
        query: str,
        result: dict,
    ) -> None:
        try:
            from sqlalchemy import text
            import json as _json

            await db.execute(
                text(
                    "INSERT INTO orchestration_runs "
                    "(tenant_id, user_id, operation_id, user_query, agents_invoked, result, status, finished_at) "
                    "VALUES (:tenant_id, :user_id, :operation_id, :query, :agents, :result, :status, now())"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "user_id": str(user_id) if user_id else None,
                    "operation_id": str(operation_id) if operation_id else None,
                    "query": query,
                    "agents": _json.dumps(result.get("agents_invoked", [])),
                    "result": _json.dumps(result),
                    "status": "completed",
                },
            )
            await db.commit()
        except Exception:
            pass   # observabilidade não bloqueia a resposta
