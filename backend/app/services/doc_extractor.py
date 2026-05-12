"""Agente extrator de conhecimento — analisa uma sessão do AI Assistant e gera documentação estruturada."""
from __future__ import annotations

from app.models.assistant import AssistantMessage, AssistantSession

_EXTRACTOR_SYSTEM = """\
Você é um especialista em documentação técnica de operações de segurança de rede.
Receberá o histórico completo de uma conversa entre um analista e um assistente de IA \
sobre infraestrutura de segurança (firewalls, redes, identidade, compliance).

Sua tarefa é extrair o conhecimento desta conversa e estruturá-lo como documentação técnica \
no formato JSON exato abaixo. Responda APENAS com o JSON, sem texto adicional.

Formato de saída (JSON):
{
  "title": "Título descritivo da solução (máx 100 chars)",
  "categoria": "firewall | rede | identidade | servidor | compliance | geral",
  "ambiente": "descrição do ambiente mencionado (vendor, device, tenant) ou 'Não especificado'",
  "sintoma": "O que o analista reportou como problema ou pergunta inicial",
  "diagnostico": "O que foi identificado como causa ou contexto técnico",
  "solucao": "Passo-a-passo da solução aplicada ou recomendada",
  "comandos": "Comandos ou configurações relevantes mencionados, ou null se não houver",
  "resultado": "Resultado final — resolvido, pendente, recomendação, etc.",
  "tags": ["tag1", "tag2", "tag3"]
}

Regras:
- Se a conversa não tiver resolução clara, preencha 'resultado' com 'Pendente — sem resolução definitiva'
- Extraia comandos exatos mencionados em blocos de código ou entre backticks
- Tags devem ser termos técnicos úteis para busca (vendor, protocolo, tipo de problema)
- Máximo 5 tags
- Responda sempre em português
"""


def _build_conversation_text(messages: list[AssistantMessage]) -> str:
    parts: list[str] = []
    for msg in messages:
        role_label = "ANALISTA" if msg.role == "user" else "ASSISTENTE IA"
        parts.append(f"[{role_label}]\n{msg.content}")
    return "\n\n---\n\n".join(parts)


async def extract_knowledge(
    session: AssistantSession,
    messages: list[AssistantMessage],
) -> dict:
    """Chama Claude para extrair conhecimento da sessão e retorna dict estruturado."""
    import json
    from app.config import settings
    import anthropic

    if not messages:
        return _empty_draft(session)

    conversation = _build_conversation_text(messages)

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        system=_EXTRACTOR_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Histórico da sessão '{session.title or 'Sem título'}':\n\n"
                    f"{conversation}"
                ),
            }
        ],
    )

    raw = response.content[0].text.strip()

    # Extrai JSON mesmo que haja markdown fence
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        data = json.loads(raw)
    except Exception:
        return _empty_draft(session)

    return data


def render_markdown(data: dict, session: AssistantSession) -> str:
    """Converte o dict extraído no template Markdown padronizado."""
    from datetime import datetime, timezone

    title = data.get("title") or session.title or "Documentação Técnica"
    categoria = data.get("categoria", "geral").capitalize()
    ambiente = data.get("ambiente", "Não especificado")
    sintoma = data.get("sintoma", "")
    diagnostico = data.get("diagnostico", "")
    solucao = data.get("solucao", "")
    comandos = data.get("comandos")
    resultado = data.get("resultado", "")
    tags = data.get("tags", [])
    agora = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    lines: list[str] = [
        f"# {title}",
        "",
        f"**Categoria:** {categoria}  ",
        f"**Ambiente:** {ambiente}  ",
        f"**Gerado em:** {agora}  ",
        f"**Revisão:** ⏳ Pendente",
        "",
        "---",
        "",
        "## Sintoma",
        "",
        sintoma,
        "",
        "## Diagnóstico",
        "",
        diagnostico,
        "",
        "## Solução",
        "",
        solucao,
    ]

    if comandos:
        lines += ["", "## Comandos / Configurações", "", "```", comandos, "```"]

    lines += [
        "",
        "## Resultado",
        "",
        resultado,
        "",
        "---",
        "",
        f"**Tags:** {', '.join(tags) if tags else '—'}",
    ]

    return "\n".join(lines)


def _empty_draft(session: AssistantSession) -> dict:
    return {
        "title": session.title or "Documentação sem título",
        "categoria": "geral",
        "ambiente": "Não especificado",
        "sintoma": "",
        "diagnostico": "",
        "solucao": "",
        "comandos": None,
        "resultado": "Pendente — conversa sem conteúdo suficiente para extração",
        "tags": [],
    }
