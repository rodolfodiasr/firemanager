"""Tenant-aware rate limiting for destructive operations.

Uses Redis INCR + EXPIRE (fixed-window counter). Keys never persist beyond
their window, so stale counters are impossible.

Key format: rl:{tenant_id}:{category}:{window_bucket}
  window_bucket = int(time.time() // window_seconds)

Categories and their limits:
  execute          30 / 60 s   — general operation executions
  destructive      10 / 300 s  — delete_rule, delete_nat, delete_route
  bulk             3  / 600 s  — bulk-job submissions
  ssh_direct       15 / 300 s  — direct SSH command executions
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request

from app.api.auth import TenantContext, get_tenant_context
from app.config import settings


@dataclass(frozen=True)
class RateLimit:
    category: str
    max_calls: int
    window_seconds: int


LIMITS: dict[str, RateLimit] = {
    "execute":     RateLimit("execute",     30, 60),
    "destructive": RateLimit("destructive", 10, 300),
    "bulk":        RateLimit("bulk",         3, 600),
    "ssh_direct":  RateLimit("ssh_direct",  15, 300),
}

_redis_pool: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis_pool


async def check_rate_limit(category: str, tenant_id: str) -> None:
    """Raise HTTP 429 if the tenant has exceeded the limit for this category."""
    limit = LIMITS.get(category)
    if limit is None:
        return

    bucket = int(time.time() // limit.window_seconds)
    key = f"rl:{tenant_id}:{category}:{bucket}"
    redis = _get_redis()

    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, limit.window_seconds + 5)  # +5 s grace for clock skew
    results = await pipe.execute()
    count: int = results[0]

    if count > limit.max_calls:
        retry_after = limit.window_seconds - (int(time.time()) % limit.window_seconds)
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "category": category,
                "limit": limit.max_calls,
                "window_seconds": limit.window_seconds,
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )


# ── FastAPI Dependencies ──────────────────────────────────────────────────────

async def limit_execute(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> None:
    """Rate limit: 30 executions per minute per tenant."""
    await check_rate_limit("execute", str(ctx.tenant.id))


async def limit_destructive(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> None:
    """Rate limit: 10 destructive operations per 5 minutes per tenant."""
    await check_rate_limit("destructive", str(ctx.tenant.id))


async def limit_bulk(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> None:
    """Rate limit: 3 bulk jobs per 10 minutes per tenant."""
    await check_rate_limit("bulk", str(ctx.tenant.id))


async def limit_ssh_direct(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> None:
    """Rate limit: 15 direct SSH operations per 5 minutes per tenant."""
    await check_rate_limit("ssh_direct", str(ctx.tenant.id))
