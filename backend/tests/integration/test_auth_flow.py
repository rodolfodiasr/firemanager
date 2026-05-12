"""Integration tests for authentication flow.

Covers: login, register, invalid credentials, JWT TTL enforcement.
Uses real JWT signing (same key as production) against SQLite in-memory DB.
"""
from datetime import timedelta

import pytest

from tests.conftest import make_tenant, make_user, assign_role
from app.models.user_tenant_role import TenantRole


class TestRegister:
    async def test_register_creates_user(self, client, db_session):
        resp = await client.post("/auth/register", json={
            "email": "new@test.local",
            "name": "New User",
            "password": "Secure@1234",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "new@test.local"
        assert "id" in body

    async def test_register_duplicate_email_rejected(self, client, db_session):
        await client.post("/auth/register", json={
            "email": "dup@test.local",
            "name": "First",
            "password": "Secure@1234",
        })
        resp = await client.post("/auth/register", json={
            "email": "dup@test.local",
            "name": "Second",
            "password": "Secure@1234",
        })
        assert resp.status_code == 400


class TestLogin:
    async def test_login_single_tenant_returns_access_token(self, client, db_session):
        user, pwd = await make_user(db_session, email="login1@test.local")
        tenant = await make_tenant(db_session)
        await assign_role(db_session, user, tenant, TenantRole.analyst_n1)

        resp = await client.post("/auth/login", json={
            "email": "login1@test.local",
            "password": pwd,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["access_token"] != ""

    async def test_login_wrong_password_returns_401(self, client, db_session):
        await make_user(db_session, email="wrongpwd@test.local")
        resp = await client.post("/auth/login", json={
            "email": "wrongpwd@test.local",
            "password": "wrong_password",
        })
        assert resp.status_code == 401

    async def test_login_unknown_email_returns_401(self, client, db_session):
        resp = await client.post("/auth/login", json={
            "email": "nobody@test.local",
            "password": "anything",
        })
        assert resp.status_code == 401

    async def test_login_user_no_tenant_returns_403(self, client, db_session):
        await make_user(db_session, email="notenant@test.local")
        resp = await client.post("/auth/login", json={
            "email": "notenant@test.local",
            "password": "Test@1234",
        })
        assert resp.status_code == 403

    async def test_login_multiple_tenants_returns_pre_token(self, client, db_session):
        user, pwd = await make_user(db_session, email="multitenant@test.local")
        tenant_a = await make_tenant(db_session)
        tenant_b = await make_tenant(db_session)
        await assign_role(db_session, user, tenant_a, TenantRole.analyst_n1)
        await assign_role(db_session, user, tenant_b, TenantRole.readonly)

        resp = await client.post("/auth/login", json={
            "email": "multitenant@test.local",
            "password": pwd,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "pre_token" in body
        assert isinstance(body.get("tenants"), list)
        assert len(body["tenants"]) == 2


class TestJwtTtl:
    async def test_token_expires_after_ttl(self, client, db_session):
        """JWT issued with negative TTL should be rejected immediately."""
        from jose import jwt as jose_jwt
        from app.config import settings
        from app.api.auth import ALGORITHM
        from datetime import datetime, timezone

        user, _ = await make_user(db_session, email="expired@test.local")
        tenant = await make_tenant(db_session)
        await assign_role(db_session, user, tenant, TenantRole.analyst_n1)

        # Forge a token that expired 1 second ago
        payload = {
            "sub": str(user.id),
            "super": False,
            "tenant_id": str(tenant.id),
            "role": "analyst_n1",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        }
        expired_token = jose_jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

        resp = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401

    async def test_token_ttl_is_15_minutes(self):
        """Config must enforce 15-minute access token TTL."""
        from app.config import settings
        assert settings.access_token_expire_minutes == 15

    async def test_valid_token_allows_me_endpoint(self, client, db_session):
        from tests.conftest import make_token

        user, _ = await make_user(db_session, email="validtoken@test.local")
        tenant = await make_tenant(db_session)
        await assign_role(db_session, user, tenant, TenantRole.analyst_n1)
        token = make_token(user, tenant, TenantRole.analyst_n1)

        resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "validtoken@test.local"
