"""AI-powered device documentation generator."""
from datetime import datetime, timezone

import anthropic

from app.config import settings
from app.models.device import Device
from app.models.operation import Operation

_SYSTEM = (
    "Você é um especialista em documentação técnica de infraestrutura de TI e segurança de redes. "
    "Gere documentação clara, estruturada e profissional em português brasileiro. "
    "Use markdown com headers, tabelas e listas onde adequado. "
    "Seja técnico e preciso — o público-alvo são administradores de rede."
)


async def generate_device_doc(
    device: Device,
    recent_ops: list[Operation],
    bookstack_context: str = "",
) -> str:
    """Call Claude to produce a structured markdown documentation page for the device."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ops_block = _ops_summary(recent_ops)

    context_block = ""
    if bookstack_context:
        context_block = (
            "\n## Documentação de referência (existente no BookStack)\n\n"
            f"{bookstack_context}\n"
        )

    prompt = f"""Data de geração: {now}

## Dispositivo

| Campo | Valor |
|---|---|
| Nome | {device.name} |
| Vendor | {device.vendor.value} |
| Categoria | {device.category.value} |
| Host | {device.host}:{device.port} |
| Firmware | {device.firmware_version or "não informado"} |
| Status | {device.status.value} |
| Notas | {device.notes or "nenhuma"} |

## Operações recentes gerenciadas pelo FireManager

{ops_block}
{context_block}
---

Gere uma documentação técnica profissional em markdown cobrindo obrigatoriamente:

1. **Sumário executivo** — Função do dispositivo na rede (1-2 parágrafos, infira pelo padrão de operações)
2. **Informações de acesso** — Tabela com host, porta, vendor, firmware, categoria
3. **Histórico de alterações via FireManager** — Resumo das configurações realizadas, agrupado por tema (regras, NAT, rotas, segurança)
4. **Observações técnicas** — Zonas identificadas, nomenclaturas de objetos, padrões de configuração observados
5. **Pontos de atenção** — Riscos, configurações incomuns ou itens que merecem revisão humana (se houver)

Não inclua senhas, tokens ou credenciais. Se não houver operações suficientes para alguma seção, indique "Sem dados suficientes" ao invés de inventar.
""".strip()

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text if response.content else ""


def _ops_summary(ops: list[Operation]) -> str:
    if not ops:
        return "_Nenhuma operação concluída registrada ainda._"

    lines = []
    for op in ops:
        intent = (op.intent or "desconhecida").replace("_", " ")
        date = op.created_at.strftime("%Y-%m-%d") if op.created_at else "?"
        icon = "✅" if op.status.value == "completed" else "❌"
        excerpt = op.natural_language_input[:120].replace("\n", " ")
        lines.append(f"- {icon} **{date}** — *{intent}*: {excerpt}")

    return "\n".join(lines)
