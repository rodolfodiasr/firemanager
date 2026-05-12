"""Fase 40-B: Abstração de LLM provider para o AI Assistant Panel.

Suporta Claude (Anthropic) e GPT-4o (OpenAI).
Se OPENAI_API_KEY não estiver configurado, OpenAI não fica disponível
e o sistema retorna ao Claude automaticamente.
"""
from __future__ import annotations

from typing import Protocol

import anthropic

from app.config import settings


class LLMProvider(Protocol):
    name: str

    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str,
        max_tokens: int = 2048,
    ) -> tuple[str, int, int]:
        """Retorna (content, input_tokens, output_tokens)."""
        ...


class AnthropicProvider:
    name = settings.anthropic_model

    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str,
        max_tokens: int = 2048,
    ) -> tuple[str, int, int]:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        resp = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        content = resp.content[0].text
        return content, resp.usage.input_tokens, resp.usage.output_tokens


class OpenAIProvider:
    name = "gpt-4o"

    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str,
        max_tokens: int = 2048,
    ) -> tuple[str, int, int]:
        try:
            import openai
        except ImportError:
            raise RuntimeError("openai package não instalado. Execute: pip install openai>=1.0")

        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        full_messages = [{"role": "system", "content": system}] + messages
        resp = await client.chat.completions.create(
            model="gpt-4o",
            max_tokens=max_tokens,
            messages=full_messages,  # type: ignore[arg-type]
        )
        content = resp.choices[0].message.content or ""
        input_tok = resp.usage.prompt_tokens if resp.usage else 0
        output_tok = resp.usage.completion_tokens if resp.usage else 0
        return content, input_tok, output_tok


def openai_available() -> bool:
    """True se OPENAI_API_KEY está configurada e o pacote openai está instalado."""
    if not settings.openai_api_key:
        return False
    try:
        import openai  # noqa: F401
        return True
    except ImportError:
        return False


def get_provider(model_preference: str | None) -> LLMProvider:
    """Retorna o provider adequado. Fallback para Anthropic se OpenAI indisponível."""
    if model_preference == "openai" and openai_available():
        return OpenAIProvider()
    return AnthropicProvider()
