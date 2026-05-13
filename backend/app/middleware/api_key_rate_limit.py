"""Rate limiting por API key com planos (Starter/Pro/Enterprise).

Limite fixo por janela deslizante de 60 segundos.
Injeta headers X-RateLimit-* em todas as respostas de requests autenticados via API key.

Planos e limites (req/min):
  starter    →   60 req/min
  pro        →  600 req/min
  enterprise →  6000 req/min (efetivamente ilimitado para uso normal)

Autenticação: header  X-API-Key: fm_xxxxxxxx...
"""
from __future__ import annotations

import hashlib
import time
from typing import Callable

import redis.asyncio as aioredis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings

# Limites por plano (req / 60 s)
_PLAN_LIMITS: dict[str, int] = {
    "starter":    60,
    "pro":        600,
    "enterprise": 6000,
}
_WINDOW_SEC = 60

_redis_pool: aioredis.Redis | None = None


def _redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis_pool


def _key_hash(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


class ApiKeyRateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware que intercepta requests com X-API-Key e aplica rate limiting por plano."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        api_key_raw = request.headers.get("X-API-Key")
        if not api_key_raw:
            # Request sem API key — passa sem rate limit (auth JWT tratado em outro lugar)
            return await call_next(request)

        # Lookup da key no banco (via app.database — sessão manual)
        try:
            result = await self._lookup_and_check(api_key_raw, request)
        except _RateLimitExceeded as exc:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "rate_limit_exceeded",
                    "plan": exc.plan,
                    "limit": exc.limit,
                    "window_seconds": _WINDOW_SEC,
                    "retry_after_seconds": exc.retry_after,
                },
                headers={
                    "X-RateLimit-Limit":     str(exc.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset":     str(exc.reset_at),
                    "Retry-After":           str(exc.retry_after),
                },
            )
        except _KeyInvalid:
            return JSONResponse(status_code=401, content={"detail": "Invalid or inactive API key"})
        except Exception:
            # Falha no rate limit não bloqueia a request (fail-open)
            return await call_next(request)

        response = await call_next(request)

        # Injeta headers informativos
        response.headers["X-RateLimit-Limit"]     = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(max(result.remaining, 0))
        response.headers["X-RateLimit-Reset"]     = str(result.reset_at)
        return response

    async def _lookup_and_check(self, raw_key: str, request: Request) -> "_RLResult":
        from app.database import AsyncSessionLocal
        from app.models.enterprise import ApiKey
        from sqlalchemy import select

        key_hash = _key_hash(raw_key)
        async with AsyncSessionLocal() as db:
            row = (
                await db.execute(
                    select(ApiKey).where(
                        ApiKey.key_hash == key_hash,
                        ApiKey.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()

            if not row:
                raise _KeyInvalid()

            # Atualiza last_used_at (best-effort, sem bloquear)
            from datetime import datetime, timezone
            row.last_used_at = datetime.now(timezone.utc)
            await db.commit()

        # Guarda a key_id no request state para uso downstream (opcional)
        request.state.api_key_id = str(row.id)
        request.state.api_key_plan = row.plan

        plan  = row.plan if row.plan in _PLAN_LIMITS else "starter"
        limit = _PLAN_LIMITS[plan]

        # Redis sliding-window counter
        bucket   = int(time.time() // _WINDOW_SEC)
        redis_key = f"akrl:{row.id}:{bucket}"
        r         = _redis()

        pipe = r.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, _WINDOW_SEC + 5)
        results   = await pipe.execute()
        count: int = results[0]

        reset_at   = (bucket + 1) * _WINDOW_SEC
        remaining  = max(limit - count, 0)
        retry_after = reset_at - int(time.time())

        if count > limit:
            raise _RateLimitExceeded(plan=plan, limit=limit, reset_at=reset_at, retry_after=retry_after)

        return _RLResult(limit=limit, remaining=remaining, reset_at=reset_at)


# ── Internal helpers ──────────────────────────────────────────────────────────

class _RLResult:
    __slots__ = ("limit", "remaining", "reset_at")

    def __init__(self, limit: int, remaining: int, reset_at: int) -> None:
        self.limit     = limit
        self.remaining = remaining
        self.reset_at  = reset_at


class _RateLimitExceeded(Exception):
    def __init__(self, plan: str, limit: int, reset_at: int, retry_after: int) -> None:
        self.plan        = plan
        self.limit       = limit
        self.reset_at    = reset_at
        self.retry_after = retry_after


class _KeyInvalid(Exception):
    pass
