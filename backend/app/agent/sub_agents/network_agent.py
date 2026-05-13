"""NetworkAgent — sub-agente especializado em conectividade, BGP/OSPF e topologia."""
from __future__ import annotations

import re
from typing import Any

from app.agent.sub_agents.base import AgentHandoff, BaseSubAgent

_NET_KEYWORDS = re.compile(
    r"\b(rede|network|rota|route|bgp|ospf|sd.?wan|latência|latency|ping|traceroute|"
    r"switch|vlan|topologia|topology|nmap|porta|port|subnet|gateway|dns|dhcp|"
    r"conectividade|connectivity|link|interface|ip|bandwidth|qos)\b",
    re.IGNORECASE,
)


class NetworkAgent(BaseSubAgent):
    name = "NetworkAgent"

    async def can_handle(self, query: str) -> bool:
        return bool(_NET_KEYWORDS.search(query))

    async def handle(
        self,
        query: str,
        context: dict[str, Any],
    ) -> AgentHandoff:
        from app.services.llm_provider import get_provider

        provider = get_provider(None)
        system = (
            "Você é o NetworkAgent do Eternity SecOps — especialista em conectividade de rede, "
            "análise de rotas BGP/OSPF, SD-WAN, switches e topologia. "
            "Analise a solicitação e retorne um diagnóstico estruturado ou plano de análise. "
            "Contexto disponível:\n" + str(context.get("network_summary", "(sem contexto de rede)"))
        )
        messages = [{"role": "user", "content": query}]
        response, _, _ = await provider.chat(messages, system)

        return AgentHandoff(
            agent=self.name,
            success=True,
            result={"analysis": response},
            actions_taken=[],
            requires_approval=False,
            confidence=0.80,
            next_steps=["Verificar rotas via módulo de conectividade se necessário"],
        )
