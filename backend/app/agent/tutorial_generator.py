"""Generate step-by-step manual tutorials for executed firewall operations."""
import json

import anthropic

from app.config import settings

_SYSTEM = (
    "Você é um instrutor de segurança de redes especialista em SonicWall. "
    "Escreva tutoriais didáticos e objetivos em português brasileiro voltados para "
    "operadores de rede. Use markdown com títulos (##), passos numerados, "
    "blocos de destaque (> Dica:) e caminhos de menu em negrito."
)

_INTENT_CONTEXT = {
    "create_rule": "criação de regra de acesso (Access Rules)",
    "edit_rule": "edição de regra de acesso (Access Rules)",
    "delete_rule": "exclusão de regra de acesso (Access Rules)",
    "create_nat_policy": "criação de política NAT",
    "delete_nat_policy": "exclusão de política NAT",
    "create_route_policy": "criação de rota estática",
    "delete_route_policy": "exclusão de rota estática",
    "create_group": "criação de grupo de endereços",
    "configure_content_filter": "configuração de Content Filter (CFS)",
    "configure_app_rules": "configuração de App Rules",
    "add_security_exclusion": "adição de exclusão de segurança",
    "toggle_gateway_av": "ativação/desativação do Gateway Anti-Virus",
    "toggle_anti_spyware": "ativação/desativação do Anti-Spyware",
    "toggle_ips": "ativação/desativação do Intrusion Prevention (IPS)",
    "toggle_app_control": "ativação/desativação do App Control",
    "toggle_geo_ip": "ativação/desativação do Geo-IP Filter",
    "toggle_botnet": "ativação/desativação do Botnet Filter",
    "toggle_dpi_ssl": "ativação/desativação do DPI-SSL",
}


async def generate_tutorial(
    intent: str,
    natural_language_input: str,
    action_plan: dict,
) -> str:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    clean_plan = {
        k: v for k, v in action_plan.items()
        if k not in ("result", "steps", "raw_intent_data")
    }

    context = _INTENT_CONTEXT.get(intent, intent)
    plan_json = json.dumps(clean_plan, ensure_ascii=False, indent=2)

    prompt = f"""O usuário solicitou: "{natural_language_input}"

A operação executada foi do tipo **{context}**.

Configuração aplicada:
```json
{plan_json}
```

Gere um tutorial passo a passo explicando como o usuário faria **exatamente essa mesma configuração** \
pelo painel web do SonicWall (Management UI), sem usar o FireManager ou SSH.

Estruture assim:
## O que foi configurado
(breve resumo da operação)

## Como fazer manualmente no SonicWall
(passos numerados com caminho de navegação no menu, campos a preencher e onde clicar para salvar)

## Dicas e boas práticas
(alertas, verificações recomendadas ou boas práticas relacionadas)

Seja direto, prático e didático. Use caminhos de menu em negrito, ex: **Manage → Security Services → Content Filter**."""

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2000,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
