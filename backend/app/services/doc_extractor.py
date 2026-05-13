"""Agente extrator de conhecimento — analisa uma sessão e gera documentação estruturada."""
from __future__ import annotations

from app.models.assistant import AssistantMessage, AssistantSession

# ── Prompts por tipo de documento ─────────────────────────────────────────────

_KNOWLEDGE_SYSTEM = """\
Você é um especialista em documentação técnica de operações de TI e segurança de rede.
Receberá o histórico completo de uma conversa entre um analista e um assistente de IA.

Extraia o conhecimento e estruture como documentação técnica no formato JSON exato abaixo.
Responda APENAS com o JSON, sem texto adicional.

{
  "title": "Título descritivo da solução (máx 100 chars)",
  "categoria": "firewall | rede | identidade | servidor | compliance | telefonia | geral",
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
- Máximo 5 tags. Responda sempre em português.
"""

_ACTION_PLAN_SYSTEM = """\
Você é especialista em gestão de TI e criação de planos de ação técnicos.
Receberá o histórico de uma conversa onde um analista discutiu um problema a ser resolvido.

Extraia as informações e estruture como um Plano de Ação no formato JSON exato abaixo.
Responda APENAS com o JSON, sem texto adicional.

{
  "title": "Título do plano de ação (máx 100 chars)",
  "categoria": "firewall | rede | identidade | servidor | compliance | telefonia | geral",
  "ambiente": "descrição do ambiente (vendor, device, tenant) ou 'Não especificado'",
  "problema": "Descrição clara do problema a ser resolvido",
  "objetivo": "O que deve ser alcançado ao final da execução",
  "etapas": ["Passo 1: descrição", "Passo 2: descrição"],
  "responsavel": "Perfil técnico necessário (Analista N1 / N2 / N3) ou 'Não definido'",
  "prazo_estimado": "Estimativa de tempo para execução ou 'Não definido'",
  "riscos": "Riscos ou pontos de atenção durante a execução, ou null",
  "validacao": "Como confirmar que o plano foi executado com sucesso",
  "tags": ["tag1", "tag2", "tag3"]
}

Regras:
- Etapas devem ser acionáveis, claras e sequenciais
- Máximo 5 tags com termos técnicos para busca
- Responda sempre em português
"""

_REMEDIATION_SYSTEM = """\
Você é especialista em documentação de remediações e resolução de incidentes de TI.
Receberá o histórico de uma conversa onde um analista resolveu e validou um problema técnico.

Extraia as informações e estruture como um Plano de Remediação no formato JSON exato abaixo.
Responda APENAS com o JSON, sem texto adicional.

{
  "title": "Título da remediação (máx 100 chars)",
  "categoria": "firewall | rede | identidade | servidor | compliance | telefonia | geral",
  "ambiente": "descrição do ambiente (vendor, device, tenant) ou 'Não especificado'",
  "problema": "Descrição do problema que foi resolvido",
  "causa_raiz": "Causa raiz identificada do problema, ou 'Não determinada'",
  "solucao_aplicada": "Descrição detalhada do que foi executado para resolver",
  "comandos": "Comandos ou configurações aplicados, ou null se não houver",
  "validacao": "Como foi confirmado que o problema foi resolvido",
  "resultado": "Resultado final e situação atual do ambiente",
  "prevencao": "O que fazer para evitar reocorrência, ou null",
  "tags": ["tag1", "tag2", "tag3"]
}

Regras:
- Foco no que já foi EXECUTADO e VALIDADO, não no que deveria ser feito
- Máximo 5 tags com termos técnicos para busca
- Responda sempre em português
"""

_SYSTEM_BY_TYPE: dict[str, str] = {
    "knowledge":   _KNOWLEDGE_SYSTEM,
    "action_plan": _ACTION_PLAN_SYSTEM,
    "remediation": _REMEDIATION_SYSTEM,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_conversation_text(messages: list[AssistantMessage]) -> str:
    parts: list[str] = []
    for msg in messages:
        role_label = "ANALISTA" if msg.role == "user" else "ASSISTENTE IA"
        parts.append(f"[{role_label}]\n{msg.content}")
    return "\n\n---\n\n".join(parts)


# ── Extração via Claude ───────────────────────────────────────────────────────

async def extract_knowledge(
    session: AssistantSession,
    messages: list[AssistantMessage],
    doc_type: str = "knowledge",
) -> dict:
    """Chama Claude para extrair conhecimento da sessão e retorna dict estruturado."""
    import json
    from app.config import settings
    import anthropic

    if not messages:
        return _empty_draft(session, doc_type)

    system_prompt = _SYSTEM_BY_TYPE.get(doc_type, _KNOWLEDGE_SYSTEM)
    conversation = _build_conversation_text(messages)

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        system=system_prompt,
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
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except Exception:
        return _empty_draft(session, doc_type)


# ── Renderers Markdown por tipo ───────────────────────────────────────────────

def render_markdown(data: dict, session: AssistantSession, doc_type: str = "knowledge") -> str:
    if doc_type == "action_plan":
        return _render_action_plan(data, session)
    if doc_type == "remediation":
        return _render_remediation(data, session)
    return _render_knowledge(data, session)


def _render_knowledge(data: dict, session: AssistantSession) -> str:
    from datetime import datetime, timezone

    title      = data.get("title") or session.title or "Documentação Técnica"
    categoria  = data.get("categoria", "geral").capitalize()
    ambiente   = data.get("ambiente", "Não especificado")
    sintoma    = data.get("sintoma", "")
    diagnostico= data.get("diagnostico", "")
    solucao    = data.get("solucao", "")
    comandos   = data.get("comandos")
    resultado  = data.get("resultado", "")
    tags       = data.get("tags", [])
    agora      = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    lines = [
        f"# {title}", "",
        f"**Tipo:** Artigo de Conhecimento  ",
        f"**Categoria:** {categoria}  ",
        f"**Ambiente:** {ambiente}  ",
        f"**Gerado em:** {agora}  ",
        f"**Revisão:** ⏳ Pendente",
        "", "---", "",
        "## Sintoma", "", sintoma, "",
        "## Diagnóstico", "", diagnostico, "",
        "## Solução", "", solucao,
    ]
    if comandos:
        lines += ["", "## Comandos / Configurações", "", "```", comandos, "```"]
    lines += ["", "## Resultado", "", resultado, "", "---", "",
              f"**Tags:** {', '.join(tags) if tags else '—'}"]
    return "\n".join(lines)


def _render_action_plan(data: dict, session: AssistantSession) -> str:
    from datetime import datetime, timezone

    title     = data.get("title") or session.title or "Plano de Ação"
    categoria = data.get("categoria", "geral").capitalize()
    ambiente  = data.get("ambiente", "Não especificado")
    problema  = data.get("problema", "")
    objetivo  = data.get("objetivo", "")
    etapas    = data.get("etapas", [])
    responsavel = data.get("responsavel", "Não definido")
    prazo     = data.get("prazo_estimado", "Não definido")
    riscos    = data.get("riscos")
    validacao = data.get("validacao", "")
    tags      = data.get("tags", [])
    agora     = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    etapas_md = "\n".join(f"{i+1}. {e}" for i, e in enumerate(etapas)) if etapas else "—"

    lines = [
        f"# {title}", "",
        f"**Tipo:** Plano de Ação  ",
        f"**Categoria:** {categoria}  ",
        f"**Ambiente:** {ambiente}  ",
        f"**Gerado em:** {agora}  ",
        f"**Status:** ⏳ Aguardando execução",
        "", "---", "",
        "## Problema", "", problema, "",
        "## Objetivo", "", objetivo, "",
        "## Etapas de Execução", "", etapas_md, "",
        "## Responsável", "", responsavel, "",
        "## Prazo Estimado", "", prazo, "",
    ]
    if riscos:
        lines += ["", "## Riscos / Pontos de Atenção", "", riscos, ""]
    lines += [
        "## Critério de Validação", "", validacao, "",
        "---", "",
        f"**Tags:** {', '.join(tags) if tags else '—'}",
    ]
    return "\n".join(lines)


def _render_remediation(data: dict, session: AssistantSession) -> str:
    from datetime import datetime, timezone

    title      = data.get("title") or session.title or "Plano de Remediação"
    categoria  = data.get("categoria", "geral").capitalize()
    ambiente   = data.get("ambiente", "Não especificado")
    problema   = data.get("problema", "")
    causa_raiz = data.get("causa_raiz", "Não determinada")
    solucao    = data.get("solucao_aplicada", "")
    comandos   = data.get("comandos")
    validacao  = data.get("validacao", "")
    resultado  = data.get("resultado", "")
    prevencao  = data.get("prevencao")
    tags       = data.get("tags", [])
    agora      = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    lines = [
        f"# {title}", "",
        f"**Tipo:** Plano de Remediação  ",
        f"**Categoria:** {categoria}  ",
        f"**Ambiente:** {ambiente}  ",
        f"**Gerado em:** {agora}  ",
        f"**Status:** ✅ Executado e validado",
        "", "---", "",
        "## Problema", "", problema, "",
        "## Causa Raiz", "", causa_raiz, "",
        "## Solução Aplicada", "", solucao, "",
    ]
    if comandos:
        lines += ["## Comandos / Configurações", "", "```", comandos, "```", ""]
    lines += [
        "## Validação", "", validacao, "",
        "## Resultado", "", resultado, "",
    ]
    if prevencao:
        lines += ["## Prevenção de Reocorrência", "", prevencao, ""]
    lines += ["---", "", f"**Tags:** {', '.join(tags) if tags else '—'}"]
    return "\n".join(lines)


# ── Fallback ──────────────────────────────────────────────────────────────────

def _empty_draft(session: AssistantSession, doc_type: str = "knowledge") -> dict:
    base = {
        "title": session.title or "Documento sem título",
        "categoria": "geral",
        "ambiente": "Não especificado",
        "tags": [],
    }
    if doc_type == "action_plan":
        return {**base, "problema": "", "objetivo": "", "etapas": [],
                "responsavel": "Não definido", "prazo_estimado": "Não definido",
                "riscos": None, "validacao": "Pendente — conversa sem conteúdo suficiente"}
    if doc_type == "remediation":
        return {**base, "problema": "", "causa_raiz": "Não determinada",
                "solucao_aplicada": "", "comandos": None, "validacao": "",
                "resultado": "Pendente — conversa sem conteúdo suficiente", "prevencao": None}
    return {**base, "sintoma": "", "diagnostico": "", "solucao": "", "comandos": None,
            "resultado": "Pendente — conversa sem conteúdo suficiente"}
