"""Circuit breaker por device — Redis-backed, sem dependência de tenacity.

Estado de cada device é armazenado em duas chaves Redis:
  cb:dev:{device_id}:fail   → contador de falhas consecutivas (TTL = window)
  cb:dev:{device_id}:open   → flag de circuito aberto (TTL = cooldown)

Ao detectar o circuito aberto, a operação levanta CircuitOpenError antes
de tentar conectar ao device, poupando threads e tempo de timeout.

Threshold padrão: 3 falhas em 60 s → abre por 300 s.
"""
from __future__ import annotations

from dataclasses import dataclass

import redis.asyncio as aioredis

from app.config import settings

_FAILURE_THRESHOLD  = 3      # falhas consecutivas para abrir
_FAILURE_WINDOW_SEC = 60     # janela de contagem
_COOLDOWN_SEC       = 300    # tempo de circuito aberto (5 min)

_redis_pool: aioredis.Redis | None = None


def _redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis_pool


def _keys(device_id: str) -> tuple[str, str]:
    return f"cb:dev:{device_id}:fail", f"cb:dev:{device_id}:open"


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open for the target device."""

    def __init__(self, device_id: str, ttl: int) -> None:
        self.device_id = device_id
        self.ttl = ttl
        super().__init__(
            f"Circuit breaker OPEN for device {device_id}. "
            f"Retry after {ttl} seconds."
        )


async def check(device_id: str) -> None:
    """Levanta CircuitOpenError se o circuito estiver aberto."""
    _, open_key = _keys(str(device_id))
    r = _redis()
    ttl = await r.ttl(open_key)
    if ttl > 0:
        raise CircuitOpenError(str(device_id), ttl)


async def record_success(device_id: str) -> None:
    """Reseta o contador de falhas ao registrar sucesso."""
    fail_key, open_key = _keys(str(device_id))
    r = _redis()
    pipe = r.pipeline()
    pipe.delete(fail_key)
    pipe.delete(open_key)
    await pipe.execute()


async def record_failure(device_id: str) -> None:
    """Incrementa falhas; abre circuito se atingir o threshold."""
    fail_key, open_key = _keys(str(device_id))
    r = _redis()

    pipe = r.pipeline()
    pipe.incr(fail_key)
    pipe.expire(fail_key, _FAILURE_WINDOW_SEC)
    results = await pipe.execute()
    count: int = results[0]

    if count >= _FAILURE_THRESHOLD:
        await r.set(open_key, "1", ex=_COOLDOWN_SEC)


@dataclass
class CircuitStatus:
    device_id: str
    state: str        # "closed" | "open"
    failures: int
    cooldown_remaining: int


async def status(device_id: str) -> CircuitStatus:
    """Retorna o estado atual do circuit breaker para um device."""
    fail_key, open_key = _keys(str(device_id))
    r = _redis()
    failures_str = await r.get(fail_key)
    ttl          = await r.ttl(open_key)
    failures     = int(failures_str) if failures_str else 0
    state        = "open" if ttl > 0 else "closed"
    return CircuitStatus(
        device_id=str(device_id),
        state=state,
        failures=failures,
        cooldown_remaining=max(ttl, 0),
    )
