from typing import Any

import anthropic

from app.agent.intent_parser import IntentParseResult
from app.config import settings

_FIELD_QUESTIONS: dict[str, str] = {
    "name": "Qual o nome para esta regra?",
    "src_address": "Qual o endereço de origem? (IP, range CIDR ou nome do objeto)",
    "dst_address": "Qual o endereço de destino? (IP, range CIDR ou nome do objeto)",
    "service": "Qual serviço/porta? (ex: HTTPS, HTTP, TCP/8080, UDP/53)",
    "action": "Qual a ação? (accept/deny/drop)",
    "comment": "Deseja adicionar um comentário/justificativa para esta regra? (opcional)",
    "rule_id": "Qual o ID ou nome da regra que deseja modificar?",
    "members": "Quais endereços/objetos fazem parte do grupo? (separe por vírgula)",
}


def get_next_question(missing_fields: list[str]) -> str | None:
    """Return the next question to ask based on missing required fields."""
    required_first = ["name", "src_address", "dst_address", "service", "action", "rule_id", "members"]
    for field in required_first:
        if field in missing_fields:
            return _FIELD_QUESTIONS.get(field)
    # Handle any remaining fields
    for field in missing_fields:
        if field in _FIELD_QUESTIONS:
            return _FIELD_QUESTIONS[field]
    return None


async def ask_clarification(
    conversation_history: list[dict[str, str]],
    missing_fields: list[str],
    collected_data: dict[str, Any],
) -> str:
    """Generate a contextual clarification question using Claude."""
    if not missing_fields:
        return "Tenho todas as informações necessárias. Gerando o plano de ação..."

    next_question = get_next_question(missing_fields)
    if next_question:
        return next_question

    # Fallback: ask Claude for a contextual question
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    context = f"""
Dados já coletados: {collected_data}
Campos faltantes: {missing_fields}
Faça UMA pergunta objetiva para obter o próximo campo faltante.
Responda apenas com a pergunta, sem explicações adicionais.
"""
    history = conversation_history + [{"role": "user", "content": context}]
    message = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=200,
        messages=history,
    )
    return message.content[0].text if message.content else "Por favor, forneça mais detalhes."
