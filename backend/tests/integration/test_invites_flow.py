"""Integration tests for invite flow.

Covers: create invite, 24h TTL, single-use enforcement, accept creates user,
existing user accept, duplicate pending rejected, expired invite rejected.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from tests.conftest import assign_role, make_tenant, make_token, make_user
from app.models.invite_token import InviteToken
from app.models.user_tenant_role import TenantRole


# Patch send_invite_email globally for all tests in this module to avoid SMTP
@pytest.fixture(autouse=True)
def _no_smtp():
    with patch("app.api.invite.send_invite_email"):
        yield


async def _create_invite(client, token: str, tenant_id: str, email: str, role: str = "analyst_n1") -> dict:
    resp = await client.post(
        "/invites",
        json={
            "email": email,
            "tenant_id": tenant_id,
            "role": role,
            "frontend_url": "http://test.local",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


class TestCreateInvite:
    async def test_admin_can_create_invite(self, client, db_session):
        tenant = await make_tenant(db_session)
        admin, _ = await make_user(db_session)
        await assign_role(db_session, admin, tenant, TenantRole.admin)
        token = make_token(admin, tenant, TenantRole.admin)

        resp = await _create_invite(client, token, str(tenant.id), "invited@test.local")
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "invited@test.local"
        assert "token" in body
        assert len(body["token"]) > 10

    async def test_invite_has_24h_ttl(self, client, db_session):
        tenant = await make_tenant(db_session)
        admin, _ = await make_user(db_session)
        await assign_role(db_session, admin, tenant, TenantRole.admin)
        token = make_token(admin, tenant, TenantRole.admin)

        resp = await _create_invite(client, token, str(tenant.id), "ttl@test.local")
        assert resp.status_code == 201

        expires_at = datetime.fromisoformat(resp.json()["expires_at"])
        now = datetime.now(timezone.utc)
        delta = expires_at - now
        # Should be close to 24h (allow ±5 seconds for test execution time)
        assert timedelta(hours=23, minutes=59, seconds=55) <= delta <= timedelta(hours=24, seconds=5)

    async def test_duplicate_pending_invite_rejected(self, client, db_session):
        tenant = await make_tenant(db_session)
        admin, _ = await make_user(db_session)
        await assign_role(db_session, admin, tenant, TenantRole.admin)
        token = make_token(admin, tenant, TenantRole.admin)

        await _create_invite(client, token, str(tenant.id), "dup@test.local")
        resp = await _create_invite(client, token, str(tenant.id), "dup@test.local")
        assert resp.status_code == 409

    async def test_non_admin_cannot_create_invite(self, client, db_session):
        tenant = await make_tenant(db_session)
        analyst, _ = await make_user(db_session)
        await assign_role(db_session, analyst, tenant, TenantRole.analyst_n1)
        token = make_token(analyst, tenant, TenantRole.analyst_n1)

        resp = await _create_invite(client, token, str(tenant.id), "nope@test.local")
        assert resp.status_code == 403


class TestGetInvite:
    async def test_get_existing_invite_by_token(self, client, db_session):
        tenant = await make_tenant(db_session)
        admin, _ = await make_user(db_session)
        await assign_role(db_session, admin, tenant, TenantRole.admin)
        token = make_token(admin, tenant, TenantRole.admin)

        create_resp = await _create_invite(client, token, str(tenant.id), "get@test.local")
        invite_token = create_resp.json()["token"]

        resp = await client.get(f"/invites/{invite_token}")
        assert resp.status_code == 200
        assert resp.json()["email"] == "get@test.local"

    async def test_get_nonexistent_token_returns_404(self, client, db_session):
        resp = await client.get("/invites/doesnotexist")
        assert resp.status_code == 404


class TestAcceptInvite:
    async def test_new_user_accept_creates_account(self, client, db_session):
        tenant = await make_tenant(db_session)
        admin, _ = await make_user(db_session)
        await assign_role(db_session, admin, tenant, TenantRole.admin)
        admin_token = make_token(admin, tenant, TenantRole.admin)

        create_resp = await _create_invite(
            client, admin_token, str(tenant.id), "brandnew@test.local"
        )
        invite_token = create_resp.json()["token"]

        resp = await client.post(
            f"/invites/{invite_token}/accept",
            json={"name": "Brand New", "password": "NewPass@1234"},
        )
        assert resp.status_code == 200
        assert "sucesso" in resp.json()["message"].lower()

    async def test_invite_is_single_use(self, client, db_session):
        tenant = await make_tenant(db_session)
        admin, _ = await make_user(db_session)
        await assign_role(db_session, admin, tenant, TenantRole.admin)
        admin_token = make_token(admin, tenant, TenantRole.admin)

        create_resp = await _create_invite(
            client, admin_token, str(tenant.id), "singleuse@test.local"
        )
        invite_token = create_resp.json()["token"]

        # First accept — should succeed
        first = await client.post(
            f"/invites/{invite_token}/accept",
            json={"name": "First Accept", "password": "Pass@1234"},
        )
        assert first.status_code == 200

        # Second attempt — token is consumed
        second = await client.post(
            f"/invites/{invite_token}/accept",
            json={"name": "Second Attempt", "password": "Pass@1234"},
        )
        assert second.status_code == 410

    async def test_existing_user_accept_adds_to_tenant(self, client, db_session):
        tenant = await make_tenant(db_session)
        admin, _ = await make_user(db_session)
        existing_user, _ = await make_user(
            db_session, email="existinguser@test.local", password="Exists@1234"
        )
        await assign_role(db_session, admin, tenant, TenantRole.admin)
        admin_token = make_token(admin, tenant, TenantRole.admin)

        create_resp = await _create_invite(
            client, admin_token, str(tenant.id), "existinguser@test.local"
        )
        invite_token = create_resp.json()["token"]

        # Accept without providing name/password (user already exists)
        resp = await client.post(f"/invites/{invite_token}/accept", json={})
        assert resp.status_code == 200

    async def test_expired_invite_returns_410(self, client, db_session):
        from sqlalchemy import select

        tenant = await make_tenant(db_session)
        admin, _ = await make_user(db_session)
        await assign_role(db_session, admin, tenant, TenantRole.admin)
        admin_token = make_token(admin, tenant, TenantRole.admin)

        create_resp = await _create_invite(
            client, admin_token, str(tenant.id), "expired@test.local"
        )
        invite_token_str = create_resp.json()["token"]

        # Manually expire the invite in the DB
        result = await db_session.execute(
            select(InviteToken).where(InviteToken.token == invite_token_str)
        )
        invite = result.scalar_one()
        invite.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db_session.add(invite)
        await db_session.flush()

        resp = await client.get(f"/invites/{invite_token_str}")
        assert resp.status_code == 410

    async def test_new_user_missing_name_returns_422(self, client, db_session):
        tenant = await make_tenant(db_session)
        admin, _ = await make_user(db_session)
        await assign_role(db_session, admin, tenant, TenantRole.admin)
        admin_token = make_token(admin, tenant, TenantRole.admin)

        create_resp = await _create_invite(
            client, admin_token, str(tenant.id), "noname@test.local"
        )
        invite_token = create_resp.json()["token"]

        resp = await client.post(
            f"/invites/{invite_token}/accept",
            json={"password": "Pass@1234"},  # name missing
        )
        assert resp.status_code == 422

    async def test_accepted_user_has_correct_role(self, client, db_session):
        from sqlalchemy import select
        from app.models.user import User
        from app.models.user_tenant_role import UserTenantRole

        tenant = await make_tenant(db_session)
        admin, _ = await make_user(db_session)
        await assign_role(db_session, admin, tenant, TenantRole.admin)
        admin_token = make_token(admin, tenant, TenantRole.admin)

        create_resp = await _create_invite(
            client, admin_token, str(tenant.id), "rolecheck@test.local", role="readonly"
        )
        invite_token = create_resp.json()["token"]

        await client.post(
            f"/invites/{invite_token}/accept",
            json={"name": "Role Check", "password": "Pass@1234"},
        )

        user_r = await db_session.execute(
            select(User).where(User.email == "rolecheck@test.local")
        )
        user = user_r.scalar_one()
        utr_r = await db_session.execute(
            select(UserTenantRole).where(
                UserTenantRole.user_id == user.id,
                UserTenantRole.tenant_id == tenant.id,
            )
        )
        utr = utr_r.scalar_one()
        assert utr.role == TenantRole.readonly
