"""IdentityAgent — sub-agente especializado em AD/M365 e ciclo de vida de identidade.

Usa o AD Tool Kit (ferramentas determinísticas) para executar operações.
O LLM apenas identifica intent e parâmetros — a execução é sempre via tool.
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.agent.sub_agents.base import AgentHandoff, BaseSubAgent

_IDENTITY_KEYWORDS = re.compile(
    r"\b(usuário|usuario|user|conta|account|ad|active.?directory|ldap|azure.?ad|m365|"
    r"onboarding|offboarding|desabilit|habilit|desativ|ativ|senha|password|reset|"
    r"grupo|group|membro|member|permiss|acesso|access|jit|sod|licen|certific|"
    r"mfa|domain.?admin|global.?admin|identidade|identity|provisionar|provisioning)\b",
    re.IGNORECASE,
)

# Mapeamento intent → tool
_TOOL_REGISTRY: dict[str, str] = {
    "list_users":           "ad_list_users",
    "get_user":             "ad_get_user",
    "disable_user":         "ad_disable_user",
    "enable_user":          "ad_enable_user",
    "reset_password":       "ad_reset_password",
    "add_to_group":         "ad_add_to_group",
    "remove_from_group":    "ad_remove_from_group",
    "get_group_members":    "ad_get_group_members",
    "list_groups":          "ad_list_groups",
    "batch_disable":        "ad_batch_disable_users",
    "compliance_report":    "ad_compliance_report",
    "list_inactive":        "ad_list_inactive_users",
}

_WRITE_TOOLS = {
    "ad_disable_user", "ad_enable_user", "ad_reset_password",
    "ad_add_to_group", "ad_remove_from_group", "ad_batch_disable_users",
}

_PARSE_SYSTEM = """\
Você é o IdentityAgent do Eternity SecOps. Analise a solicitação e retorne JSON com:
{
  "intent": "<um de: list_users|get_user|disable_user|enable_user|reset_password|add_to_group|remove_from_group|get_group_members|list_groups|batch_disable|compliance_report|list_inactive>",
  "parameters": {
    "username_or_upn": "<se mencionado>",
    "group_name": "<se mencionado>",
    "department": "<se mencionado>",
    "days_inactive": <número se mencionado>,
    "report_type": "<senhas_expiradas|inativos|admins_sem_mfa|membros_grupo>"
  },
  "requires_approval": <true para operações de escrita>,
  "confidence": <0.0 a 1.0>,
  "reasoning": "<por que este intent>"
}
Retorne APENAS o JSON, sem markdown."""


class IdentityAgent(BaseSubAgent):
    name = "IdentityAgent"

    async def can_handle(self, query: str) -> bool:
        return bool(_IDENTITY_KEYWORDS.search(query))

    async def handle(
        self,
        query: str,
        context: dict[str, Any],
    ) -> AgentHandoff:
        from app.services.llm_provider import get_provider

        provider = get_provider(None)
        messages = [{"role": "user", "content": query}]
        raw, _, _ = await provider.chat(messages, _PARSE_SYSTEM)

        try:
            parsed = json.loads(raw.strip())
        except json.JSONDecodeError:
            return AgentHandoff(
                agent=self.name,
                success=False,
                error=f"Falha ao interpretar intent: {raw[:200]}",
                confidence=0.0,
            )

        intent = parsed.get("intent", "unknown")
        params = parsed.get("parameters", {})
        confidence = float(parsed.get("confidence", 0.7))
        tool_name = _TOOL_REGISTRY.get(intent)
        requires_approval = tool_name in _WRITE_TOOLS if tool_name else False

        # Executar tool se contexto AD disponível e ferramenta de leitura
        tool_result: dict = {}
        actions_taken: list[str] = []

        ad_config = context.get("ad_config")
        if ad_config and tool_name and tool_name not in _WRITE_TOOLS:
            try:
                tool_result = await _execute_read_tool(tool_name, params, ad_config)
                actions_taken.append(f"{tool_name}({_fmt_params(params)})")
            except Exception as exc:
                tool_result = {"error": str(exc)}

        next_steps = []
        if requires_approval:
            next_steps.append(
                f"Ação '{tool_name}' requer aprovação humana antes de executar. "
                "Use o Agente Operacional após confirmação."
            )

        return AgentHandoff(
            agent=self.name,
            success=True,
            result={
                "intent": intent,
                "tool": tool_name,
                "parameters": params,
                "tool_result": tool_result,
                "reasoning": parsed.get("reasoning", ""),
            },
            actions_taken=actions_taken,
            requires_approval=requires_approval,
            confidence=confidence,
            next_steps=next_steps,
        )


def _fmt_params(params: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in params.items() if v)


async def _execute_read_tool(tool_name: str, params: dict, ad_config: dict) -> dict:
    """Executa ferramentas de leitura do AD Tool Kit."""
    from app.services import local_ad_service as ldap

    if tool_name == "ad_list_users":
        users = await ldap.list_users(ad_config)
        dept = params.get("department")
        if dept:
            users = [u for u in users if (u.get("department") or "").lower() == dept.lower()]
        return {"users": users, "count": len(users)}

    if tool_name == "ad_get_user":
        upn = params.get("username_or_upn", "")
        user = await ldap.find_user(ad_config, upn)
        return {"user": user}

    if tool_name == "ad_list_inactive_users":
        days = int(params.get("days_inactive", 60))
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        users = await ldap.list_users(ad_config)
        inactive = []
        for u in users:
            ls = u.get("last_logon_str")
            if not ls:
                inactive.append(u)
                continue
            try:
                last = datetime.fromisoformat(ls)
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                if last < cutoff:
                    inactive.append(u)
            except ValueError:
                inactive.append(u)
        return {"users": inactive, "count": len(inactive), "days_threshold": days}

    if tool_name == "ad_get_group_members":
        group = params.get("group_name", "")
        members = await ldap.get_group_members(ad_config, group)
        return {"members": members, "group": group}

    if tool_name == "ad_compliance_report":
        report_type = params.get("report_type", "inativos")
        users = await ldap.list_users(ad_config)
        if report_type == "inativos":
            from datetime import datetime, timedelta, timezone
            cutoff = datetime.now(timezone.utc) - timedelta(days=60)
            result = [u for u in users if not u.get("last_logon_str")]
        elif report_type == "senhas_expiradas":
            result = users  # placeholder — requer pwdLastSet + maxPwdAge
        else:
            result = users
        return {"report_type": report_type, "items": result[:50], "total": len(result)}

    return {"message": f"Tool '{tool_name}' não implementada ainda"}
