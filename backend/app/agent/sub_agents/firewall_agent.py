"""FirewallAgent — sub-agente especializado em operações de firewall."""
from __future__ import annotations

import re
from typing import Any

from app.agent.sub_agents.base import AgentHandoff, BaseSubAgent

_FIREWALL_KEYWORDS = re.compile(
    r"\b(firewall|regra|rule|nat|rota|route|bloquei|bloqueio|permit|allow|deny|"
    r"acl|política|policy|vlan|interface|fortinet|sonicwall|pfsense|opnsense|"
    r"snapshot|golden.?config|bundle|vpn|ipsec|bgp|ospf|conect|ping)\b",
    re.IGNORECASE,
)


class FirewallAgent(BaseSubAgent):
    name = "FirewallAgent"

    async def can_handle(self, query: str) -> bool:
        return bool(_FIREWALL_KEYWORDS.search(query))

    async def handle(
        self,
        query: str,
        context: dict[str, Any],
    ) -> AgentHandoff:
        from app.services.llm_provider import get_provider

        provider = get_provider(None)
        system = (
            "Você é o FirewallAgent do Eternity SecOps — especialista em firewalls multivendor "
            "(Fortinet, SonicWall, pfSense, OPNsense, MikroTik, Sophos, Cisco, Palo Alto, Check Point). "
            "Analise a solicitação do analista e retorne um plano de ação JSON estruturado com os campos: "
            "intent, device_hint, parameters, requires_approval (bool), confidence (0-1), next_steps (list). "
            "Contexto disponível:\n" + str(context.get("firewall_summary", "(sem contexto de firewall)"))
        )
        messages = [{"role": "user", "content": query}]
        response, _, _ = await provider.chat(messages, system)

        return AgentHandoff(
            agent=self.name,
            success=True,
            result={"plan_text": response},
            actions_taken=[],
            requires_approval=True,
            confidence=0.85,
            next_steps=["Revisar plano e executar via Agente Operacional"],
        )
