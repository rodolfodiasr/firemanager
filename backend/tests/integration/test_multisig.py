"""Integration tests for multi-sig approval flow (P6 security hardening).

Uses the in-memory SQLite database from conftest. SQLite does not enforce
foreign-key constraints by default, so user/tenant records are created as
lightweight stubs — only the fields used by the tested queries are populated.

Covers:
  - co-approve endpoint: add co-approver, prevent self-approval, idempotency
  - execute gate: block when co_approvals insufficient, pass when satisfied
  - risk classification applied to operation defaults
"""
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from unittest.mock import AsyncMock, patch

from app.api.auth import TenantContext, get_tenant_context
from app.main import app
from app.middleware.rate_limit import limit_execute
from app.models.device import Device, DeviceCategory, VendorEnum
from app.models.operation import Operation, OperationRisk, OperationStatus
from app.models.user import User, UserRole
from app.models.user_tenant_role import TenantRole


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def user1(db_session: AsyncSession) -> User:
    u = User(
        id=uuid4(),
        email="creator@example.com",
        name="Creator",
        hashed_password="$2b$12$placeholder",
        role=UserRole.operator,
    )
    db_session.add(u)
    await db_session.flush()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def user2(db_session: AsyncSession) -> User:
    u = User(
        id=uuid4(),
        email="co-approver@example.com",
        name="Co-Approver",
        hashed_password="$2b$12$placeholder",
        role=UserRole.operator,
    )
    db_session.add(u)
    await db_session.flush()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
def tenant_id():
    return uuid4()


@pytest_asyncio.fixture
async def device(db_session: AsyncSession, tenant_id) -> Device:
    d = Device(
        id=uuid4(),
        tenant_id=tenant_id,
        name="Test Firewall",
        vendor=VendorEnum.fortinet,
        category=DeviceCategory.firewall,
        host="192.168.1.1",
        port=443,
        encrypted_credentials="dummy",
    )
    db_session.add(d)
    await db_session.flush()
    await db_session.refresh(d)
    return d


@pytest_asyncio.fixture
async def critical_op(
    db_session: AsyncSession, user1: User, device: Device
) -> Operation:
    op = Operation(
        id=uuid4(),
        user_id=user1.id,
        device_id=device.id,
        natural_language_input="run direct ssh command",
        intent="direct_ssh",
        status=OperationStatus.approved,
        risk_level=OperationRisk.critical,
        required_approvals=2,
        co_approvals=[],
    )
    db_session.add(op)
    await db_session.flush()
    await db_session.refresh(op)
    return op


def _ctx(user: User, tenant_id, role: TenantRole = TenantRole.admin) -> TenantContext:
    from unittest.mock import MagicMock
    tenant = MagicMock()
    tenant.id = tenant_id
    return TenantContext(user=user, tenant=tenant, role=role)


# ── co-approve endpoint ───────────────────────────────────────────────────────

class TestCoApproveEndpoint:
    async def test_adds_co_approver_to_list(
        self, client, db_session, critical_op, user2, tenant_id
    ):
        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user2, tenant_id)
        try:
            resp = await client.post(f"/operations/{critical_op.id}/co-approve")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 200
        await db_session.refresh(critical_op)
        assert str(user2.id) in (critical_op.co_approvals or [])

    async def test_prevents_creator_self_approval(
        self, client, critical_op, user1, tenant_id
    ):
        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user1, tenant_id)
        try:
            resp = await client.post(f"/operations/{critical_op.id}/co-approve")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 403
        assert "co-aprovador" in resp.json()["detail"].lower() or \
               "self" in resp.json()["detail"].lower() or \
               "criador" in resp.json()["detail"].lower()

    async def test_co_approve_is_idempotent(
        self, client, db_session, critical_op, user2, tenant_id
    ):
        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user2, tenant_id)
        try:
            await client.post(f"/operations/{critical_op.id}/co-approve")
            resp = await client.post(f"/operations/{critical_op.id}/co-approve")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 200
        await db_session.refresh(critical_op)
        # Duplicate entries must not accumulate
        co = critical_op.co_approvals or []
        assert co.count(str(user2.id)) == 1

    async def test_rejects_co_approve_on_single_approval_op(
        self, client, db_session, user1, user2, device, tenant_id
    ):
        normal_op = Operation(
            id=uuid4(),
            user_id=user1.id,
            device_id=device.id,
            natural_language_input="list rules",
            intent="list_rules",
            status=OperationStatus.approved,
            risk_level=OperationRisk.medium,
            required_approvals=1,
            co_approvals=[],
        )
        db_session.add(normal_op)
        await db_session.flush()

        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user2, tenant_id)
        try:
            resp = await client.post(f"/operations/{normal_op.id}/co-approve")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 400

    async def test_co_approve_on_nonexistent_operation_returns_404(
        self, client, user2, tenant_id
    ):
        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user2, tenant_id)
        try:
            resp = await client.post(f"/operations/{uuid4()}/co-approve")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 404

    async def test_prevents_primary_reviewer_self_approval(
        self, client, db_session, user1, user2, device, tenant_id
    ):
        op = Operation(
            id=uuid4(),
            user_id=user1.id,
            reviewer_id=user2.id,        # user2 is the primary reviewer
            device_id=device.id,
            natural_language_input="critical op",
            intent="direct_ssh",
            status=OperationStatus.pending_review,
            risk_level=OperationRisk.critical,
            required_approvals=2,
            co_approvals=[],
        )
        db_session.add(op)
        await db_session.flush()

        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user2, tenant_id)
        try:
            resp = await client.post(f"/operations/{op.id}/co-approve")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 403


# ── Execute gate — multi-sig check ───────────────────────────────────────────

class TestExecuteGateMultiSig:
    async def test_execute_blocked_when_co_approvals_missing(
        self, client, critical_op, user1, tenant_id
    ):
        # critical_op requires 2 approvals but co_approvals=[] (0 co-approvers)
        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user1, tenant_id)
        app.dependency_overrides[limit_execute] = lambda: None
        try:
            with patch(
                "app.api.operations.resolve_device_role",
                new_callable=AsyncMock,
                return_value=TenantRole.admin,
            ):
                resp = await client.post(f"/operations/{critical_op.id}/execute")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(limit_execute, None)

        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["error"] == "multi_sig_required"
        assert detail["co_approvals_needed"] == 1

    async def test_execute_allowed_when_co_approvals_satisfied(
        self, client, db_session, critical_op, user1, user2, device, tenant_id
    ):
        # Add user2 as co-approver
        critical_op.co_approvals = [str(user2.id)]
        await db_session.flush()

        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user1, tenant_id)
        app.dependency_overrides[limit_execute] = lambda: None
        try:
            with patch(
                "app.api.operations.resolve_device_role",
                new_callable=AsyncMock,
                return_value=TenantRole.admin,
            ), patch(
                "app.api.operations.execute_operation",
                new_callable=AsyncMock,
                return_value=critical_op,
            ):
                resp = await client.post(f"/operations/{critical_op.id}/execute")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(limit_execute, None)

        # Should not be 403 multi_sig_required — may be other errors (device connect, etc.)
        if resp.status_code == 403:
            detail = resp.json().get("detail", {})
            assert detail.get("error") != "multi_sig_required", \
                "Execute should not be blocked for multi-sig when co-approvals are satisfied"

    async def test_execute_multi_sig_detail_shows_remaining_approvals(
        self, client, db_session, user1, user2, device, tenant_id
    ):
        op = Operation(
            id=uuid4(),
            user_id=user1.id,
            device_id=device.id,
            natural_language_input="triple approval op",
            intent="direct_ssh",
            status=OperationStatus.approved,
            risk_level=OperationRisk.critical,
            required_approvals=3,
            co_approvals=[str(user2.id)],  # 1 of 2 needed co-approvals present
        )
        db_session.add(op)
        await db_session.flush()

        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user1, tenant_id)
        app.dependency_overrides[limit_execute] = lambda: None
        try:
            with patch(
                "app.api.operations.resolve_device_role",
                new_callable=AsyncMock,
                return_value=TenantRole.admin,
            ):
                resp = await client.post(f"/operations/{op.id}/execute")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(limit_execute, None)

        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["error"] == "multi_sig_required"
        assert detail["required_approvals"] == 3
        assert detail["co_approvals_received"] == 1
        assert detail["co_approvals_needed"] == 1


# ── Model defaults ────────────────────────────────────────────────────────────

class TestOperationModelDefaults:
    def test_default_risk_is_medium(self):
        col = Operation.__table__.c.risk_level
        assert col.default is not None
        assert col.default.arg == OperationRisk.medium
        assert col.nullable is False

    def test_co_approvals_default_is_empty_list(self):
        col = Operation.__table__.c.co_approvals
        assert col.default is not None
        # SQLAlchemy wraps the callable — check the name rather than identity
        assert callable(col.default.arg)
        assert col.default.arg.__name__ == "list"

    def test_direct_ssh_risk_classification(self):
        from app.models.operation import classify_risk
        risk, approvals = classify_risk("direct_ssh")
        assert risk == OperationRisk.critical
        assert approvals == 2
