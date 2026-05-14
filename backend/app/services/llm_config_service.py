"""LLM Config Service — gerencia providers LLM com hierarquia tenant → global → env.

Hierarquia de resolução:
  1. Config do tenant (is_default=True, is_enabled=True, tenant_id=<id>)
  2. Config global (is_default=True, is_enabled=True, tenant_id=NULL)
  3. platform_config legado (anthropic_api_key / openai_api_key)
  4. Variáveis de ambiente (.env)
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_config import LLMConfig
from app.utils.crypto import _get_fernet

if TYPE_CHECKING:
    from app.services.llm_provider import LLMProvider

# ── Metadados fixos por provider ──────────────────────────────────────────────

PROVIDER_META: dict[str, dict[str, Any]] = {
    "anthropic":  {"label": "Claude (Anthropic)",    "base_url": None,                                                       "default_model": "claude-sonnet-4-6",                            "needs_key": True,  "local": False},
    "openai":     {"label": "GPT (OpenAI)",           "base_url": "https://api.openai.com/v1",                                "default_model": "gpt-4o",                                       "needs_key": True,  "local": False},
    "google":     {"label": "Gemini (Google)",        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "default_model": "gemini-2.0-flash",                             "needs_key": True,  "local": False},
    "deepseek":   {"label": "DeepSeek",               "base_url": "https://api.deepseek.com/v1",                              "default_model": "deepseek-chat",                                "needs_key": True,  "local": False},
    "moonshot":   {"label": "Kimi (Moonshot)",        "base_url": "https://api.moonshot.cn/v1",                               "default_model": "moonshot-v1-8k",                               "needs_key": True,  "local": False},
    "xai":        {"label": "Grok (xAI)",             "base_url": "https://api.x.ai/v1",                                      "default_model": "grok-3",                                       "needs_key": True,  "local": False},
    "perplexity": {"label": "Perplexity",             "base_url": "https://api.perplexity.ai",                                "default_model": "llama-3.1-sonar-large-128k-online",            "needs_key": True,  "local": False},
    "nvidia":     {"label": "Nemotron (NVIDIA)",      "base_url": "https://integrate.api.nvidia.com/v1",                      "default_model": "nvidia/llama-3.1-nemotron-70b-instruct",       "needs_key": True,  "local": False},
    "zhipu":      {"label": "GLM (Zhipu)",            "base_url": "https://open.bigmodel.cn/api/paas/v4/",                    "default_model": "glm-4",                                        "needs_key": True,  "local": False},
    "minimax":    {"label": "MiniMax",                "base_url": "https://api.minimax.chat/v1",                              "default_model": "abab6.5s-chat",                                "needs_key": True,  "local": False},
    "ollama":     {"label": "Ollama / Custom",        "base_url": None,                                                       "default_model": "llama3",                                       "needs_key": False, "local": True},
}


# ── Crypto helpers ────────────────────────────────────────────────────────────

def _encrypt(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def _decrypt(token: str) -> str:
    return _get_fernet().decrypt(token.encode()).decode()


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def list_configs(db: AsyncSession, tenant_id: uuid.UUID | None) -> list[LLMConfig]:
    """Lista configs do escopo: NULL=global, NOT NULL=tenant."""
    result = await db.execute(
        select(LLMConfig)
        .where(LLMConfig.tenant_id == tenant_id)
        .order_by(LLMConfig.priority.desc(), LLMConfig.created_at)
    )
    return list(result.scalars().all())


async def get_config(db: AsyncSession, config_id: uuid.UUID, tenant_id: uuid.UUID | None) -> LLMConfig | None:
    result = await db.execute(
        select(LLMConfig).where(LLMConfig.id == config_id, LLMConfig.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def create_config(
    db: AsyncSession,
    tenant_id: uuid.UUID | None,
    provider: str,
    model_name: str,
    api_key: str | None,
    api_base_url: str | None,
    is_default: bool,
    no_train_flag: bool,
) -> LLMConfig:
    meta = PROVIDER_META.get(provider, {})
    display_name = meta.get("label", provider)
    resolved_base_url = api_base_url or meta.get("base_url")

    if is_default:
        await _clear_default(db, tenant_id)

    cfg = LLMConfig(
        tenant_id=tenant_id,
        provider=provider,
        display_name=display_name,
        api_key_encrypted=_encrypt(api_key) if api_key else None,
        api_base_url=resolved_base_url,
        model_name=model_name,
        is_default=is_default,
        no_train_flag=no_train_flag,
    )
    db.add(cfg)
    await db.flush()
    await db.refresh(cfg)
    return cfg


async def update_config(
    db: AsyncSession,
    cfg: LLMConfig,
    model_name: str | None,
    api_key: str | None,
    api_base_url: str | None,
    is_default: bool | None,
    is_enabled: bool | None,
    no_train_flag: bool | None,
) -> LLMConfig:
    if model_name is not None:
        cfg.model_name = model_name
    if api_key is not None:
        cfg.api_key_encrypted = _encrypt(api_key)
    if api_base_url is not None:
        cfg.api_base_url = api_base_url
    if is_default is not None:
        if is_default:
            await _clear_default(db, cfg.tenant_id)
        cfg.is_default = is_default
    if is_enabled is not None:
        cfg.is_enabled = is_enabled
    if no_train_flag is not None:
        cfg.no_train_flag = no_train_flag
    await db.flush()
    await db.refresh(cfg)
    return cfg


async def delete_config(db: AsyncSession, cfg: LLMConfig) -> None:
    await db.delete(cfg)


async def _clear_default(db: AsyncSession, tenant_id: uuid.UUID | None) -> None:
    """Remove is_default de todos os configs do mesmo escopo."""
    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(LLMConfig)
        .where(LLMConfig.tenant_id == tenant_id, LLMConfig.is_default.is_(True))
        .values(is_default=False)
    )


# ── Provider resolution ───────────────────────────────────────────────────────

async def resolve_provider(
    tenant_id: uuid.UUID,
    db: AsyncSession,
    preference: str | None = None,
) -> "LLMProvider":
    """Retorna instância de LLMProvider seguindo a hierarquia tenant → global → env.

    `preference` pode ser um slug de provider (ex: 'openai', 'anthropic') para
    forçar um provider específico — usado pelo seletor de modelo no frontend.
    """
    from app.services.llm_provider import build_provider_from_config, get_provider

    # 1. Busca config habilitada do tenant
    tenant_cfg = await _find_best(db, tenant_id, preference)
    if tenant_cfg:
        return build_provider_from_config(tenant_cfg, _decrypt)

    # 2. Busca config global
    global_cfg = await _find_best(db, None, preference)
    if global_cfg:
        return build_provider_from_config(global_cfg, _decrypt)

    # 3. Fallback para platform_config / env (comportamento legado)
    return get_provider(preference)


async def _find_best(
    db: AsyncSession,
    tenant_id: uuid.UUID | None,
    preference: str | None,
) -> LLMConfig | None:
    q = select(LLMConfig).where(
        LLMConfig.tenant_id == tenant_id,
        LLMConfig.is_enabled.is_(True),
    )
    if preference:
        # Tenta encontrar o provider preferido; se não, cai no padrão
        result = await db.execute(q.where(LLMConfig.provider == preference).limit(1))
        cfg = result.scalar_one_or_none()
        if cfg:
            return cfg

    # Usa o marcado como padrão
    result = await db.execute(q.where(LLMConfig.is_default.is_(True)).limit(1))
    return result.scalar_one_or_none()


# ── Test connection ───────────────────────────────────────────────────────────

async def test_connection(cfg: LLMConfig) -> dict:
    """Testa o provider com uma mensagem mínima. Retorna {ok, message, latency_ms}."""
    import time
    from app.services.llm_provider import build_provider_from_config

    provider = build_provider_from_config(cfg, _decrypt)
    start = time.monotonic()
    try:
        text, _, _ = await provider.chat(
            messages=[{"role": "user", "content": "ping"}],
            system="Responda apenas: pong",
            max_tokens=10,
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        return {"ok": True, "message": f"Resposta: {text.strip()[:40]}", "latency_ms": latency_ms}
    except Exception as exc:
        return {"ok": False, "message": str(exc)[:200], "latency_ms": 0}
