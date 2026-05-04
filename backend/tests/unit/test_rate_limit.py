"""Tests for tenant-aware rate limiting middleware."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.middleware.rate_limit import LIMITS, RateLimit, check_rate_limit

TENANT = "tenant-abc-123"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_redis(count: int) -> MagicMock:
    """Return a mock Redis client whose pipeline returns `count` as the INCR result."""
    pipe = AsyncMock()
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[count, True])
    redis = MagicMock()
    redis.pipeline.return_value = pipe
    return redis


# ── Rate limit configuration ──────────────────────────────────────────────────

class TestLimitsConfig:
    def test_execute_30_per_60s(self):
        assert LIMITS["execute"].max_calls == 30
        assert LIMITS["execute"].window_seconds == 60

    def test_destructive_10_per_300s(self):
        assert LIMITS["destructive"].max_calls == 10
        assert LIMITS["destructive"].window_seconds == 300

    def test_bulk_3_per_600s(self):
        assert LIMITS["bulk"].max_calls == 3
        assert LIMITS["bulk"].window_seconds == 600

    def test_ssh_direct_15_per_300s(self):
        assert LIMITS["ssh_direct"].max_calls == 15
        assert LIMITS["ssh_direct"].window_seconds == 300

    def test_all_categories_present(self):
        for cat in ("execute", "destructive", "bulk", "ssh_direct"):
            assert cat in LIMITS

    def test_rate_limit_is_frozen_dataclass(self):
        limit = LIMITS["execute"]
        with pytest.raises((AttributeError, TypeError)):
            limit.max_calls = 999  # type: ignore[misc]


# ── check_rate_limit behaviour ────────────────────────────────────────────────

class TestCheckRateLimit:
    async def test_first_call_passes(self):
        with patch("app.middleware.rate_limit._get_redis", return_value=_make_redis(1)):
            await check_rate_limit("execute", TENANT)

    async def test_call_exactly_at_limit_passes(self):
        with patch("app.middleware.rate_limit._get_redis", return_value=_make_redis(30)):
            await check_rate_limit("execute", TENANT)

    async def test_call_one_over_limit_raises_429(self):
        with patch("app.middleware.rate_limit._get_redis", return_value=_make_redis(31)):
            with pytest.raises(HTTPException) as exc:
                await check_rate_limit("execute", TENANT)
        assert exc.value.status_code == 429

    async def test_429_has_retry_after_header(self):
        with patch("app.middleware.rate_limit._get_redis", return_value=_make_redis(999)):
            with pytest.raises(HTTPException) as exc:
                await check_rate_limit("execute", TENANT)
        assert "Retry-After" in (exc.value.headers or {})

    async def test_429_detail_contains_error_key(self):
        with patch("app.middleware.rate_limit._get_redis", return_value=_make_redis(999)):
            with pytest.raises(HTTPException) as exc:
                await check_rate_limit("destructive", TENANT)
        detail = exc.value.detail
        assert detail["error"] == "rate_limit_exceeded"
        assert detail["category"] == "destructive"
        assert detail["limit"] == 10
        assert "retry_after_seconds" in detail

    async def test_unknown_category_silently_ignored(self):
        # No Redis call should be made, no exception raised
        mock_redis = _make_redis(9999)
        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit("nonexistent_category", TENANT)
        mock_redis.pipeline.assert_not_called()

    async def test_bulk_limit_strict_three_max(self):
        with patch("app.middleware.rate_limit._get_redis", return_value=_make_redis(4)):
            with pytest.raises(HTTPException) as exc:
                await check_rate_limit("bulk", TENANT)
        assert exc.value.status_code == 429
        assert exc.value.detail["limit"] == 3

    async def test_redis_key_includes_tenant_and_category(self):
        captured: list[str] = []

        pipe = AsyncMock()
        pipe.execute = AsyncMock(return_value=[1, True])
        pipe.expire = MagicMock(return_value=pipe)

        def capture_incr(key: str):
            captured.append(key)
            return pipe

        pipe.incr = MagicMock(side_effect=capture_incr)
        redis = MagicMock()
        redis.pipeline.return_value = pipe

        with patch("app.middleware.rate_limit._get_redis", return_value=redis):
            await check_rate_limit("execute", "my-tenant-id")

        assert len(captured) == 1
        assert captured[0].startswith("rl:my-tenant-id:execute:")

    async def test_different_tenants_have_independent_counters(self):
        """Each tenant gets its own key — a blocked tenant doesn't block another."""
        keys_seen: list[str] = []

        def _redis_for_tenant():
            pipe = AsyncMock()
            pipe.execute = AsyncMock(return_value=[1, True])
            pipe.expire = MagicMock(return_value=pipe)

            def capture(key: str):
                keys_seen.append(key)
                return pipe

            pipe.incr = MagicMock(side_effect=capture)
            r = MagicMock()
            r.pipeline.return_value = pipe
            return r

        with patch("app.middleware.rate_limit._get_redis", side_effect=_redis_for_tenant):
            await check_rate_limit("execute", "tenant-A")
            await check_rate_limit("execute", "tenant-B")

        tenant_prefixes = {k.split(":")[1] for k in keys_seen}
        assert "tenant-A" in tenant_prefixes
        assert "tenant-B" in tenant_prefixes

    async def test_ssh_direct_at_limit_passes(self):
        with patch("app.middleware.rate_limit._get_redis", return_value=_make_redis(15)):
            await check_rate_limit("ssh_direct", TENANT)

    async def test_ssh_direct_over_limit_raises(self):
        with patch("app.middleware.rate_limit._get_redis", return_value=_make_redis(16)):
            with pytest.raises(HTTPException) as exc:
                await check_rate_limit("ssh_direct", TENANT)
        assert exc.value.detail["limit"] == 15
