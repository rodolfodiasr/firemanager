"""Fase 40-A: Clarification Engine — gera perguntas de clarificação e calcula confidence score.

Quando o agente não tem informações suficientes ou a intenção é ambígua, este módulo
gera perguntas estruturadas para o analista responder antes de gerar o plano de ação.
"""
from __future__ import annotations

import json
import re

import anthropic

from app.config import settings

_CONFIDENCE_SYSTEM = """
Você avalia se um pedido de configuração de rede/firewall tem informações suficientes
para ser executado com segurança.

Analise a intenção detectada, os dados coletados e o histórico da conversa.
Retorne um JSON com:
{
  "confidence": 0.0,
  "reason": "motivo em 1 frase"
}

confidence: 0.0 (completamente ambíguo) a 1.0 (totalmente claro e seguro de executar).
Considere baixa confiança quando:
- Endereços IP ausentes ou ambíguos
- Zonas de firewall não especificadas
- Serviço/porta não especificado para regras de acesso
- Intenção de deleção sem identificador único da regra
- Pedido contraditório com dados coletados
"""

_CLARIFICATION_SYSTEM = """
Você é o agente de operações do Eternity SecOps.
O analista fez um pedido que precisa de clarificação antes de ser executado com segurança.

Com base nos campos faltantes e no contexto, gere de 1 a 3 perguntas objetivas e diretas.

Retorne APENAS JSON válido:
{
  "questions": [
    {
      "id": "q1",
      "question": "Pergunta clara e objetiva?",
      "field": "nome_do_campo",
      "options": ["opção 1", "opção 2"]
    }
  ]
}

"options" é opcional — inclua apenas quando as respostas são de um conjunto fechado e conhecido.
As perguntas devem ser em português e focar em obter a informação mínima necessária.
"""

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


async def compute_confidence_score(
    intent: str,
    collected_data: dict,
    conversation_history: list[dict],
    natural_language_input: str,
) -> float:
    """Retorna score 0.0–1.0 baseado na completude e coerência dos dados coletados."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    context = (
        f"Intenção detectada: {intent}\n"
        f"Dados coletados: {json.dumps(collected_data, ensure_ascii=False)}\n"
        f"Pedido original: {natural_language_input}\n"
        f"Mensagens: {len(conversation_history)} trocas"
    )

    try:
        resp = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=200,
            system=_CONFIDENCE_SYSTEM,
            messages=[{"role": "user", "content": context}],
        )
        raw = resp.content[0].text
        m = _JSON_RE.search(raw)
        if m:
            data = json.loads(m.group())
            score = float(data.get("confidence", 0.5))
            return max(0.0, min(1.0, score))
    except Exception:
        pass

    # Fallback heurístico: conta campos obrigatórios presentes
    required_by_intent: dict[str, list[str]] = {
        "create_rule": ["src_address", "dst_address", "service", "action"],
        "delete_rule": ["rule_id"],
        "create_nat_policy": ["destination", "translated_destination"],
        "create_route_policy": ["interface", "destination", "gateway"],
    }
    required = required_by_intent.get(intent, [])
    if not required:
        return 0.85
    present = sum(1 for f in required if f in collected_data)
    return present / len(required)


async def generate_clarification_questions(
    natural_language_input: str,
    missing_fields: list[str],
    collected_data: dict,
    conversation_history: list[dict],
    intent: str,
) -> list[dict]:
    """Gera lista de perguntas estruturadas para o analista completar as informações."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    context = (
        f"Pedido original: {natural_language_input}\n"
        f"Intenção: {intent}\n"
        f"Dados já coletados: {json.dumps(collected_data, ensure_ascii=False)}\n"
        f"Campos ainda faltando: {', '.join(missing_fields)}\n"
        f"Histórico ({len(conversation_history)} msgs): "
        + "; ".join(m.get("content", "")[:60] for m in conversation_history[-4:])
    )

    try:
        resp = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=600,
            system=_CLARIFICATION_SYSTEM,
            messages=[{"role": "user", "content": context}],
        )
        raw = resp.content[0].text
        m = _JSON_RE.search(raw)
        if m:
            data = json.loads(m.group())
            questions = data.get("questions", [])
            if questions:
                return questions
    except Exception:
        pass

    # Fallback: uma pergunta genérica por campo faltando
    return [
        {
            "id": f"q{i + 1}",
            "question": _field_to_question(field),
            "field": field,
        }
        for i, field in enumerate(missing_fields[:3])
    ]


def _field_to_question(field: str) -> str:
    labels = {
        "src_address": "Qual é o endereço IP ou rede de origem?",
        "dst_address": "Qual é o endereço IP ou rede de destino?",
        "src_zone": "Qual é a zona de origem (ex: LAN, WAN, DMZ)?",
        "dst_zone": "Qual é a zona de destino (ex: LAN, WAN, DMZ)?",
        "service": "Qual serviço ou porta? (ex: HTTPS, TCP 8080)",
        "action": "A regra deve permitir ou bloquear o tráfego?",
        "rule_id": "Qual é o nome ou ID da regra a ser modificada?",
        "name": "Qual nome deve ter esta regra/objeto?",
        "interface": "Qual interface de rede deve ser usada?",
        "destination": "Qual é a rede ou host de destino?",
        "gateway": "Qual é o gateway para esta rota?",
        "members": "Quais endereços IP devem ser adicionados ao grupo? (separados por vírgula)",
    }
    return labels.get(field, f"Qual é o valor para '{field}'?")


def format_clarification_message(questions: list[dict]) -> str:
    """Formata as perguntas de clarificação como mensagem do agente."""
    lines = [
        "Preciso de algumas informações adicionais antes de prosseguir:\n"
    ]
    for i, q in enumerate(questions, 1):
        lines.append(f"**{i}. {q['question']}**")
        if q.get("options"):
            lines.append("   Opções: " + " | ".join(q["options"]))
    lines.append("\nResponda usando o formulário abaixo.")
    return "\n".join(lines)
