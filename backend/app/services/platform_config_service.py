"""Platform config service — reads API keys/SMTP from DB with env fallback.

Usage pattern:
  - In async code with a DB session: await get(key, db)
  - In sync code or services without DB: get_sync(key) (reads from warmed cache → env)
  - On startup: await warm_cache(db) to pre-load all keys into cache

Keys that can be stored here:
  anthropic_api_key, anthropic_model, anthropic_max_tokens
  openai_api_key, openai_embedding_model
  smtp_host, smtp_port, smtp_user, smtp_password, email_from
"""
from __future__ import annotations

import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.crypto import _get_fernet

_CACHE: dict[str, tuple[str | None, float]] = {}
_CACHE_TTL = 300  # 5 minutes


def _encrypt(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def _decrypt(token: str) -> str:
    return _get_fernet().decrypt(token.encode()).decode()


def get_sync(key: str) -> str | None:
    """Return value from in-memory cache or env fallback — no DB call.

    Use this in services that don't have a DB session. Requires warm_cache()
    to have been called at startup for DB values to be reflected here.
    """
    from app.config import settings

    now = time.monotonic()
    if key in _CACHE:
        value, expires_at = _CACHE[key]
        if now < expires_at:
            return value

    # Cache miss — read from env
    return getattr(settings, key, None) or None


async def get(key: str, db: AsyncSession) -> str | None:
    """Return plaintext value for *key*, using cache then DB then env fallback."""
    from app.config import settings
    from app.models.platform_config import PlatformConfig

    now = time.monotonic()
    if key in _CACHE:
        value, expires_at = _CACHE[key]
        if now < expires_at:
            return value

    row = (await db.execute(select(PlatformConfig).where(PlatformConfig.key == key))).scalar_one_or_none()
    if row and row.encrypted_value:
        try:
            value = _decrypt(row.encrypted_value)
        except Exception:
            value = None
    else:
        value = getattr(settings, key, None) or None

    _CACHE[key] = (value, now + _CACHE_TTL)
    return value


async def warm_cache(db: AsyncSession) -> None:
    """Pre-load all keys from DB into the in-memory cache. Call once at startup."""
    from app.config import settings
    from app.models.platform_config import PlatformConfig

    rows = (await db.execute(select(PlatformConfig))).scalars().all()
    now = time.monotonic()
    for row in rows:
        if row.encrypted_value:
            try:
                value = _decrypt(row.encrypted_value)
            except Exception:
                value = getattr(settings, row.key, None) or None
        else:
            value = getattr(settings, row.key, None) or None
        _CACHE[row.key] = (value, now + _CACHE_TTL)


async def set_key(key: str, value: str, description: str | None, db: AsyncSession) -> None:
    """Encrypt and persist *value* for *key*. Invalidates cache entry."""
    from app.models.platform_config import PlatformConfig

    encrypted = _encrypt(value)
    row = (await db.execute(select(PlatformConfig).where(PlatformConfig.key == key))).scalar_one_or_none()
    if row:
        row.encrypted_value = encrypted
        if description is not None:
            row.description = description
    else:
        row = PlatformConfig(key=key, encrypted_value=encrypted, description=description)
        db.add(row)
    await db.flush()
    await db.refresh(row)
    _CACHE.pop(key, None)


async def delete_key(key: str, db: AsyncSession) -> bool:
    """Clear the DB value for *key* (falls back to env). Returns True if row existed."""
    from app.models.platform_config import PlatformConfig

    row = (await db.execute(select(PlatformConfig).where(PlatformConfig.key == key))).scalar_one_or_none()
    if not row:
        return False
    await db.delete(row)
    _CACHE.pop(key, None)
    return True


async def list_keys(db: AsyncSession) -> list[dict[str, Any]]:
    """Return metadata for all stored keys (never the plaintext value)."""
    from app.models.platform_config import PlatformConfig

    rows = (await db.execute(select(PlatformConfig).order_by(PlatformConfig.key))).scalars().all()
    return [
        {
            "key": r.key,
            "description": r.description,
            "is_sensitive": r.is_sensitive,
            "is_set": r.encrypted_value is not None,
            "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]


def invalidate(key: str | None = None) -> None:
    """Invalidate one or all cache entries."""
    if key:
        _CACHE.pop(key, None)
    else:
        _CACHE.clear()
