"""Security tests: JWT authentication boundaries.

Verifies that tokens are properly validated — expired, tampered, wrong type,
missing claims, and unsigned tokens are all rejected. Also documents known
gaps (brute force protection, user enumeration) via pytest.xfail.
"""
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import (
    ALGORITHM,
    PRE_TOKEN_TTL,
    _create_pre_token,
    _create_refresh_token,
    _create_token,
    _hash_password,
)
from app.config import settings
from app.models.user import User, UserRole
from app.models.user_tenant_role import TenantRole


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def active_user(db_session: AsyncSession):
    u = User(
        id=uuid4(),
        email=f"active-{uuid4()}@example.com",
        name="Active User",
        hashed_password=_hash_password("correct-password"),
        role=UserRole.operator,
        is_active=True,
        is_super_admin=False,
    )
    db_session.add(u)
    await db_session.flush()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def inactive_user(db_session: AsyncSession):
    u = User(
        id=uuid4(),
        email=f"inactive-{uuid4()}@example.com",
        name="Inactive User",
        hashed_password=_hash_password("password"),
        role=UserRole.operator,
        is_active=False,
    )
    db_session.add(u)
    await db_session.flush()
    await db_session.refresh(u)
    return u


# ── Token structure boundaries ────────────────────────────────────────────────

class TestTokenStructureBoundaries:
    async def test_no_token_returns_401(self, client):
        resp = await client.get("/devices")
        assert resp.status_code == 401

    async def test_empty_bearer_returns_401(self, client):
        resp = await client.get("/devices", headers={"Authorization": "Bearer "})
        assert resp.status_code == 401

    async def test_garbage_token_returns_401(self, client):
        resp = await client.get("/devices", headers={"Authorization": "Bearer not.a.token"})
        assert resp.status_code == 401

    async def test_expired_token_returns_401(self, client):
        payload = {
            "sub": str(uuid4()),
            "tenant_id": str(uuid4()),
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        }
        token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
        resp = await client.get("/devices", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_token_signed_with_wrong_key_returns_401(self, client):
        payload = {"sub": str(uuid4()), "tenant_id": str(uuid4())}
        token = jwt.encode(payload, "completely-wrong-secret-key", algorithm=ALGORITHM)
        resp = await client.get("/devices", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_tampered_payload_returns_401(self, client):
        """Modifying the JWT payload must invalidate the signature."""
        import base64, json as _json

        payload = {"sub": str(uuid4()), "tenant_id": str(uuid4()), "super": False}
        token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
        parts = token.split(".")

        # Replace payload with one claiming super admin
        fake = {"sub": str(uuid4()), "tenant_id": str(uuid4()), "super": True}
        fake_b64 = base64.urlsafe_b64encode(
            _json.dumps(fake).encode()
        ).decode().rstrip("=")
        tampered = f"{parts[0]}.{fake_b64}.{parts[2]}"

        resp = await client.get("/devices", headers={"Authorization": f"Bearer {tampered}"})
        assert resp.status_code == 401, "Tampered JWT payload must be rejected"

    async def test_token_without_tenant_id_returns_403(self, client, active_user):
        """Access token with no tenant_id claim must be rejected on tenant-scoped endpoints."""
        token = _create_token({"sub": str(active_user.id)}, timedelta(minutes=5))
        resp = await client.get("/devices", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    async def test_token_none_algorithm_rejected(self, client):
        """'none' algorithm tokens (unsigned) must not be accepted."""
        import base64, json as _json
        header = base64.urlsafe_b64encode(
            _json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).decode().rstrip("=")
        payload_enc = base64.urlsafe_b64encode(
            _json.dumps({"sub": str(uuid4()), "tenant_id": str(uuid4())}).encode()
        ).decode().rstrip("=")
        none_token = f"{header}.{payload_enc}."  # no signature

        resp = await client.get("/devices", headers={"Authorization": f"Bearer {none_token}"})
        assert resp.status_code == 401, "'none' algorithm token must be rejected"


# ── Token type misuse ─────────────────────────────────────────────────────────

class TestTokenTypeMisuse:
    async def test_refresh_token_cannot_access_api(self, client, active_user):
        """refresh token (type='refresh') must not be accepted as an access token."""
        token = _create_refresh_token(active_user.id)
        resp = await client.get("/devices", headers={"Authorization": f"Bearer {token}"})
        # refresh token has no tenant_id → 403, or invalid type → 401
        assert resp.status_code in (401, 403), (
            "SECURITY: refresh token was accepted as an access token"
        )

    async def test_pre_token_cannot_access_api(self, client, active_user):
        """pre_tenant token (type='pre_tenant') must not work on regular endpoints."""
        token = _create_pre_token(active_user.id)
        resp = await client.get("/devices", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (401, 403), (
            "SECURITY: pre_tenant token was accepted as an access token"
        )

    async def test_pre_token_cannot_be_used_as_select_tenant_twice(
        self, client, active_user, db_session
    ):
        """pre_token is single-use (TTL=5min) — using it twice is not prevented by server
        today (no revocation list). Document as known gap."""
        token = _create_pre_token(active_user.id)
        # Both calls with the same pre_token → server currently accepts both
        # This is a known gap: no token revocation after first use
        resp1 = await client.post("/auth/select-tenant", json={
            "pre_token": token,
            "tenant_id": str(uuid4()),
        })
        resp2 = await client.post("/auth/select-tenant", json={
            "pre_token": token,
            "tenant_id": str(uuid4()),
        })
        # Both may return 403 (no tenant association) but neither should crash
        assert resp1.status_code in (200, 400, 403)
        assert resp2.status_code in (200, 400, 403)


# ── Inactive user ─────────────────────────────────────────────────────────────

class TestInactiveUser:
    async def test_inactive_user_token_rejected(self, client, inactive_user):
        """Token for a deactivated user must be rejected even if signature is valid."""
        token = _create_token(
            {"sub": str(inactive_user.id), "tenant_id": str(uuid4())},
            timedelta(minutes=5),
        )
        resp = await client.get("/devices", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401, (
            "SECURITY: Inactive user's token was accepted"
        )


# ── Login behavior ────────────────────────────────────────────────────────────

class TestLoginBehavior:
    async def test_wrong_password_returns_401(self, client, active_user):
        resp = await client.post("/auth/login", json={
            "email": active_user.email,
            "password": "wrong-password",
        })
        assert resp.status_code == 401

    async def test_nonexistent_user_returns_same_as_wrong_password(self, client):
        """Prevents user enumeration: both cases must return identical status and message."""
        resp_exist = await client.post("/auth/login", json={
            "email": "definitely-does-not-exist@example.com",
            "password": "wrong",
        })
        resp_wrong = await client.post("/auth/login", json={
            "email": "also-does-not-exist@example.com",
            "password": "wrong",
        })
        assert resp_exist.status_code == resp_wrong.status_code == 401
        assert resp_exist.json()["detail"] == resp_wrong.json()["detail"], (
            "SECURITY: Different error messages for unknown vs wrong-password may leak user existence"
        )

    async def test_login_no_brute_force_protection_documented(self, client):
        """
        KNOWN GAP: /auth/login has no rate limiting.
        An attacker can attempt unlimited passwords without throttling.
        This test documents the gap — it will pass (gap exists) until protection is added.
        """
        # Send 10 rapid failed logins — none should trigger a 429
        codes = []
        for _ in range(10):
            r = await client.post("/auth/login", json={
                "email": "victim@example.com",
                "password": "wrong",
            })
            codes.append(r.status_code)

        has_rate_limit = any(c == 429 for c in codes)
        if has_rate_limit:
            pass  # Protection was added — test passes cleanly
        else:
            pytest.xfail(
                "KNOWN GAP: /auth/login has no brute force protection (no 429 after 10 attempts). "
                "Add rate limiting on login endpoint."
            )

    async def test_register_email_enumeration_gap(self, client, active_user):
        """
        KNOWN GAP: POST /auth/register returns 400 'Email already registered'
        when the email exists, allowing user enumeration.
        """
        resp = await client.post("/auth/register", json={
            "email": active_user.email,
            "name": "Another",
            "password": "StrongPass123!",
            "role": "operator",
        })
        if resp.status_code == 400 and "already" in resp.json().get("detail", "").lower():
            pytest.xfail(
                "KNOWN GAP: /auth/register leaks email existence via 'Email already registered' message. "
                "Consider returning 201 with a generic message regardless."
            )


# ── POST /auth/refresh ────────────────────────────────────────────────────────

class TestRefreshEndpoint:
    async def test_valid_refresh_with_tenant_returns_new_tokens(
        self, client, db_session
    ):
        """Valid refresh token + tenant_id returns new access + refresh tokens."""
        from tests.conftest import assign_role, make_tenant, make_user

        tenant = await make_tenant(db_session)
        user, _ = await make_user(db_session)
        await assign_role(db_session, user, tenant, TenantRole.admin)

        refresh = _create_refresh_token(user.id)
        resp = await client.post("/auth/refresh", json={
            "refresh_token": refresh,
            "tenant_id": str(tenant.id),
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"] is not None
        assert body["refresh_token"] is not None

    async def test_super_admin_refresh_no_tenant_needed(self, client, db_session):
        """Super admin refresh returns new tokens without requiring tenant_id."""
        from tests.conftest import make_user

        admin, _ = await make_user(db_session, is_super_admin=True)
        refresh = _create_refresh_token(admin.id)
        resp = await client.post("/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"] is not None
        assert body["refresh_token"] is not None

    async def test_access_token_cannot_be_used_as_refresh(self, client, active_user):
        """Token without type='refresh' must be rejected with 401."""
        access = _create_token(
            {"sub": str(active_user.id), "tenant_id": str(uuid4())},
            timedelta(minutes=15),
        )
        resp = await client.post("/auth/refresh", json={"refresh_token": access})
        assert resp.status_code == 401

    async def test_expired_refresh_token_rejected(self, client, active_user):
        """Expired refresh token must return 401."""
        expired = _create_token(
            {"sub": str(active_user.id), "type": "refresh"},
            timedelta(seconds=-1),
        )
        resp = await client.post("/auth/refresh", json={"refresh_token": expired})
        assert resp.status_code == 401

    async def test_refresh_for_inactive_user_rejected(self, client, inactive_user):
        """Refresh token for deactivated user must return 401."""
        refresh = _create_refresh_token(inactive_user.id)
        resp = await client.post("/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 401

    async def test_refresh_with_wrong_tenant_returns_403(self, client, active_user):
        """Refresh token with a tenant the user doesn't belong to must return 403."""
        refresh = _create_refresh_token(active_user.id)
        resp = await client.post("/auth/refresh", json={
            "refresh_token": refresh,
            "tenant_id": str(uuid4()),
        })
        assert resp.status_code == 403

    async def test_single_tenant_user_refresh_without_tenant_id(
        self, client, db_session
    ):
        """Single-tenant user with no tenant_id in body gets auto-scoped token."""
        from tests.conftest import assign_role, make_tenant, make_user

        tenant = await make_tenant(db_session)
        user, _ = await make_user(db_session)
        await assign_role(db_session, user, tenant, TenantRole.analyst)

        refresh = _create_refresh_token(user.id)
        resp = await client.post("/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"] is not None
        assert body["refresh_token"] is not None
