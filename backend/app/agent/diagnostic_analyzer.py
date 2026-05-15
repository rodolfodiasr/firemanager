"""Post-execution diagnostic analysis for get_info operations."""
import json
from typing import Any
from uuid import UUID

import anthropic

from app.config import settings

_FALLBACK_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = (
    "Você é um especialista em diagnóstico de infraestrutura de rede e segurança. "
    "Analise os outputs de comandos coletados de um dispositivo e forneça um diagnóstico "
    "estruturado em português. Seja objetivo, técnico e prático."
)

_TEMPLATE = """Dispositivo: {vendor} (firmware: {firmware_version})
Contexto/problema relatado: {problem_description}

Comandos executados: {commands_list}

Saída coletada:
```
{output}
```

Com base nos dados acima, retorne APENAS um JSON (sem markdown) com:
{{
  "summary": "resumo executivo em 1-2 frases do estado geral do dispositivo",
  "findings": [
    {{
      "severity": "critical|high|medium|low|info",
      "title": "título curto do achado",
      "detail": "explicação técnica com dados concretos do output"
    }}
  ],
  "root_causes": ["causa raiz 1 identificada", "causa raiz 2"],
  "recommendations": ["ação recomendada 1", "ação recomendada 2"],
  "requires_immediate_action": false,
  "suggested_follow_up_commands": ["comando1 para investigar mais", "comando2"]
}}

Inclua apenas findings reais encontrados nos dados. Se não houver problemas, diga isso no summary.
Em suggested_follow_up_commands, inclua 2-5 comandos de leitura (show/display) que aprofundariam o diagnóstico com base nos problemas encontrados. Se não houver nada a investigar, retorne lista vazia."""


async def analyze_diagnostic(
    vendor: str,
    firmware_version: str | None,
    problem_description: str,
    commands: list[str],
    output: str,
    tenant_id: UUID | None = None,
    db: Any = None,
) -> dict[str, Any]:
    """Analyze SSH command outputs and return a structured diagnosis dict."""
    prompt = (
        _TEMPLATE
        .replace("{vendor}", vendor)
        .replace("{firmware_version}", firmware_version or "unknown")
        .replace("{problem_description}", problem_description or "diagnóstico geral")
        .replace("{commands_list}", ", ".join(commands))
        .replace("{output}", output[:8000])  # cap to avoid token overflow
    )

    if db is not None and tenant_id is not None:
        try:
            from app.services.llm_config_service import resolve_provider
            provider = await resolve_provider(tenant_id, db)
            content, _, _ = await provider.chat(
                messages=[{"role": "user", "content": prompt}],
                system=_SYSTEM,
                max_tokens=2048,
            )
        except Exception:
            content = await _call_anthropic(prompt)
    else:
        content = await _call_anthropic(prompt)

    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.rsplit("```", 1)[0]

    try:
        return json.loads(content.strip())
    except Exception:
        return {
            "summary": content[:500],
            "findings": [],
            "root_causes": [],
            "recommendations": [],
            "requires_immediate_action": False,
            "suggested_follow_up_commands": [],
        }


async def _call_anthropic(prompt: str) -> str:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    primary = settings.anthropic_model
    try:
        message = await client.messages.create(
            model=primary,
            max_tokens=2048,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.InternalServerError as exc:
        if exc.status_code == 529 and primary != _FALLBACK_MODEL:
            message = await client.messages.create(
                model=_FALLBACK_MODEL,
                max_tokens=2048,
                system=_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
        else:
            raise
    return message.content[0].text if message.content else "{}"
