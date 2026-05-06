"""Security tests: role-based access control on operations.

Verifies that:
- readonly users cannot execute operations
- analyst_n1 cannot execute directly (must use submit-review)
- analyst_n2 / admin can execute
- super admin flag in JWT is verified against the database record
"""
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.auth import TenantContext, get_tenant_context, _create_token
from app.config import settings
from app.main import app
from app.middleware.rate_limit import limit_execute
from app.models.device import Device, DeviceCategory, VendorEnum
from app.models.operation import Operation, OperationRisk, OperationStatus
from app.models.user import User, UserRole
from app.models.user_tenant_role import TenantRole
from datetime import timedelta


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_ctx(user, tenant_id, role):
    tenant = MagicMock()
    tenant.id = tenant_id
    return TenantContext(user=user, tenant=tenant, role=role)


async def _make_user(db_session, suffix=""):
    u = User(
        id=uuid4(),
        email=f"role-test-{suffix}-{uuid4()}@example.com",
        name=f"User {suffix}",
        hashed_password="x",
        role=UserRole.operator,
        is_super_admin=False,
    )
    db_session.add(u)
    await db_session.flush()
    await db_session.refresh(u)
    return u


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tenant_id():
    return uuid4()


@pytest_asyncio.fixture
async def device(db_session: AsyncSession, tenant_id):
    d = Device(
        id=uuid4(), tenant_id=tenant_id, name="FW-Role-Test",
        vendor=VendorEnum.fortinet, category=DeviceCategory.firewall,
        host="10.0.0.1", port=443, encrypted_credentials="dummy",
    )
    db_session.add(d)
    await db_session.flush()
    await db_session.refresh(d)
    return d


async def _approved_op(db_session, user, device, intent="create_rule", risk=OperationRisk.medium):
    op = Operation(
        id=uuid4(), user_id=user.id, device_id=device.id,
        natural_language_input="create rule",
        intent=intent,
        status=OperationStatus.approved,
        risk_level=risk,
        required_approvals=1,
        co_approvals=[],
    )
    db_session.add(op)
    await db_session.flush()
    await db_session.refresh(op)
    return op


# ── Readonly role ─────────────────────────────────────────────────────────────

class TestReadonlyRoleBlocked:
    async def test_readonly_cannot_execute_operation(
        self, client, db_session, device, tenant_id
    ):
        """readonly role must be blocked from executing any operation."""
        user = await _make_user(db_session, "readonly")
        op = await _approved_op(db_session, user, device)

        app.dependency_overrides[get_tenant_context] = lambda: _mock_ctx(user, tenant_id, TenantRole.readonly)
        app.dependency_overrides[limit_execute] = lambda: None
        try:
            with patch(
                "app.api.operations.resolve_device_role",
                new_callable=AsyncMock,
                return_value=TenantRole.readonly,
            ):
                resp = await client.post(f"/operations/{op.id}/execute")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(limit_execute, None)

        assert resp.status_code == 403, (
            "SECURITY: readonly user was allowed to execute an operation"
        )

    async def test_readonly_cannot_create_direct_ssh_operation(
        self, client, db_session, device, tenant_id
    ):
        """readonly role must be blocked from creating direct SSH operations."""
        user = await _make_user(db_session, "readonly-ssh")

        app.dependency_overrides[get_tenant_context] = lambda: _mock_ctx(user, tenant_id, TenantRole.readonly)
        try:
            with patch(
                "app.api.operations.resolve_device_role",
                new_callable=AsyncMock,
                return_value=TenantRole.readonly,
            ):
                resp = await client.post("/operations/direct-ssh", json={
                    "device_id": str(device.id),
                    "description": "test",
                    "ssh_commands": ["show run"],
                })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 403


# ── Analyst N1 restrictions ───────────────────────────────────────────────────

class TestAnalystN1Restrictions:
    async def test_analyst_n1_cannot_execute_directly(
        self, client, db_session, device, tenant_id
    ):
        """Analyst N1 must use submit-review, not execute directly."""
        user = await _make_user(db_session, "n1")
        op = await _approved_op(db_session, user, device)

        app.dependency_overrides[get_tenant_context] = lambda: _mock_ctx(user, tenant_id, TenantRole.analyst_n1)
        app.dependency_overrides[limit_execute] = lambda: None
        try:
            with patch(
                "app.api.operations.resolve_device_role",
                new_callable=AsyncMock,
                return_value=TenantRole.analyst_n1,
            ):
                resp = await client.post(f"/operations/{op.id}/execute")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(limit_execute, None)

        assert resp.status_code == 403
        detail = resp.json().get("detail", "")
        assert "N1" in detail or "revisão" in detail.lower() or "review" in detail.lower(), (
            f"SECURITY: N1 execute block returned unexpected message: '{detail}'"
        )

    async def test_analyst_n1_cannot_create_direct_ssh(
        self, client, db_session, device, tenant_id
    ):
        """Analyst N1 must not be able to run arbitrary SSH commands."""
        user = await _make_user(db_session, "n1-ssh")

        app.dependency_overrides[get_tenant_context] = lambda: _mock_ctx(user, tenant_id, TenantRole.analyst_n1)
        try:
            with patch(
                "app.api.operations.resolve_device_role",
                new_callable=AsyncMock,
                return_value=TenantRole.analyst_n1,
            ):
                resp = await client.post("/operations/direct-ssh", json={
                    "device_id": str(device.id),
                    "description": "N1 bypass attempt",
                    "ssh_commands": ["show run"],
                })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 403


# ── Analyst N2 / Admin allowed ────────────────────────────────────────────────

class TestAnalystN2AndAdminAllowed:
    async def test_admin_execute_not_blocked_by_role_check(
        self, client, db_session, device, tenant_id
    ):
        """Admin role must pass the role gate (may still fail on device connect etc.)."""
        user = await _make_user(db_session, "admin")
        op = await _approved_op(db_session, user, device)

        app.dependency_overrides[get_tenant_context] = lambda: _mock_ctx(user, tenant_id, TenantRole.admin)
        app.dependency_overrides[limit_execute] = lambda: None
        try:
            with patch(
                "app.api.operations.resolve_device_role",
                new_callable=AsyncMock,
                return_value=TenantRole.admin,
            ), patch(
                "app.api.operations.execute_operation",
                new_callable=AsyncMock,
                return_value=op,
            ):
                resp = await client.post(f"/operations/{op.id}/execute")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(limit_execute, None)

        # Should not be 403 due to role — may be other errors
        if resp.status_code == 403:
            detail = resp.json().get("detail", {})
            if isinstance(detail, dict):
                assert detail.get("error") != "role_forbidden", \
                    "Admin should not be blocked by role check"
            else:
                assert "role" not in str(detail).lower(), \
                    f"Admin blocked by role: {detail}"

    async def test_analyst_n2_not_blocked_by_role_check(
        self, client, db_session, device, tenant_id
    ):
        """Analyst N2 role must pass the role gate."""
        user = await _make_user(db_session, "n2")
        op = await _approved_op(db_session, user, device)

        app.dependency_overrides[get_tenant_context] = lambda: _mock_ctx(user, tenant_id, TenantRole.analyst_n2)
        app.dependency_overrides[limit_execute] = lambda: None
        try:
            with patch(
                "app.api.operations.resolve_device_role",
                new_callable=AsyncMock,
                return_value=TenantRole.analyst_n2,
            ), patch(
                "app.api.operations.execute_operation",
                new_callable=AsyncMock,
                return_value=op,
            ), patch(
                "app.services.audit_service.check_requires_approval",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.post(f"/operations/{op.id}/execute")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(limit_execute, None)

        if resp.status_code == 403:
            detail = resp.json().get("detail", "")
            assert "N1" not in str(detail), \
                f"N2 user incorrectly blocked with N1 message: {detail}"


# ── Super admin JWT forgery ───────────────────────────────────────────────────

class TestSuperAdminForgery:
    async def test_super_false_in_token_cannot_access_admin_endpoints(self, client, db_session):
        """Token with super=False must not access super-admin-only endpoints."""
        user = await _make_user(db_session, "fake-super")
        # Token claims super=False — should not grant super admin
        token = _create_token(
            {"sub": str(user.id), "super": False},
            timedelta(minutes=5),
        )
        resp = await client.get(
            "/admin/tenants",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (401, 403)

    async def test_non_super_user_with_super_true_in_token_rejected(self, client, db_session):
        """Even if super=True is in the token, the DB record must be checked."""
        user = await _make_user(db_session, "not-really-super")
        # Crafting a token that claims super=True for a non-super user
        # (would require knowing the secret key — this simulates a compromised key scenario)
        token = _create_token(
            {"sub": str(user.id), "super": True},
            timedelta(minutes=5),
        )
        resp = await client.get(
            "/admin/tenants",
            headers={"Authorization": f"Bearer {token}"},
        )
        # require_super_admin checks DB record — user.is_super_admin is False
        assert resp.status_code == 403, (
            "SECURITY: non-super user with super=True claim in token was granted super admin access"
        )
