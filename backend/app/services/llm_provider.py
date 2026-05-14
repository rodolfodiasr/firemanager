"""Abstração de LLM provider — suporta Anthropic, OpenAI e qualquer provider
OpenAI-compatível (DeepSeek, Kimi, Grok, Perplexity, Gemini, NVIDIA, Ollama, etc.).

Hierarquia de uso:
  - resolve_provider() em llm_config_service.py → retorna instância correta por tenant
  - get_provider() → fallback legado lido do .env (sem DB)
  - build_provider_from_config() → constrói provider a partir de LLMConfig
"""
from __future__ import annotations

from typing import Callable, Protocol

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


# ── Anthropic ─────────────────────────────────────────────────────────────────

class AnthropicProvider:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or settings.anthropic_api_key
        self._model = model or settings.anthropic_model
        self.name = self._model

    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str,
        max_tokens: int = 2048,
    ) -> tuple[str, int, int]:
        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        resp = await client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        content = resp.content[0].text
        return content, resp.usage.input_tokens, resp.usage.output_tokens


# ── OpenAI-compatible (OpenAI, DeepSeek, Kimi, Grok, Perplexity, Gemini, etc.) ─

class GenericOpenAICompatProvider:
    """Funciona com qualquer provider que exponha a API OpenAI-compatível.

    Inclui: OpenAI, DeepSeek, Kimi/Moonshot, Grok/xAI, Perplexity,
    Gemini (via endpoint beta), NVIDIA NIM, Zhipu GLM, MiniMax, Ollama.
    """

    def __init__(self, api_key: str | None, base_url: str, model: str, label: str = "") -> None:
        self._api_key = api_key or "none"   # Ollama não exige key
        self._base_url = base_url
        self._model = model
        self.name = label or model

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

        client = openai.AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        full_messages = [{"role": "system", "content": system}] + messages
        resp = await client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=full_messages,  # type: ignore[arg-type]
        )
        content = resp.choices[0].message.content or ""
        input_tok = resp.usage.prompt_tokens if resp.usage else 0
        output_tok = resp.usage.completion_tokens if resp.usage else 0
        return content, input_tok, output_tok


# ── OpenAI legado (mantido para compatibilidade) ──────────────────────────────

class OpenAIProvider(GenericOpenAICompatProvider):
    def __init__(self) -> None:
        super().__init__(
            api_key=settings.openai_api_key,
            base_url="https://api.openai.com/v1",
            model="gpt-4o",
            label="gpt-4o",
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

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
    """Retorna provider lendo apenas .env/settings — fallback legado sem DB."""
    from app.services import platform_config_service as _pcs

    pref = (model_preference or "").lower()

    if pref == "openai" and openai_available():
        return OpenAIProvider()

    # Tenta ler API key do cache de platform_config (não faz query ao DB)
    anthropic_key = _pcs.get_sync("anthropic_api_key") or settings.anthropic_api_key
    anthropic_model = _pcs.get_sync("anthropic_model") or settings.anthropic_model
    return AnthropicProvider(api_key=anthropic_key, model=anthropic_model)


def build_provider_from_config(cfg: "object", decrypt_fn: Callable[[str], str]) -> LLMProvider:
    """Constrói um LLMProvider a partir de um registro LLMConfig."""
    from app.services.llm_config_service import PROVIDER_META

    api_key = decrypt_fn(cfg.api_key_encrypted) if cfg.api_key_encrypted else None  # type: ignore[attr-defined]
    provider = cfg.provider  # type: ignore[attr-defined]
    model = cfg.model_name   # type: ignore[attr-defined]
    base_url = cfg.api_base_url  # type: ignore[attr-defined]
    meta = PROVIDER_META.get(provider, {})
    resolved_base_url = base_url or meta.get("base_url")
    label = meta.get("label", provider)

    if provider == "anthropic":
        return AnthropicProvider(api_key=api_key, model=model)

    if resolved_base_url:
        return GenericOpenAICompatProvider(
            api_key=api_key,
            base_url=resolved_base_url,
            model=model,
            label=label,
        )

    # Sem base_url configurada (ex: Ollama sem URL) — cai no Anthropic padrão
    return get_provider(None)
