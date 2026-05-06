"""Security tests: multi-tenant isolation.

Verifies that a user authenticated to Tenant A cannot read, list, or operate
on resources (devices, operations) belonging to Tenant B.

These tests cover the most critical MSSP security requirement: complete data
isolation between customer tenants.
"""
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import MagicMock

from app.api.auth import TenantContext, get_tenant_context
from app.main import app
from app.models.device import Device, DeviceCategory, VendorEnum
from app.models.operation import Operation, OperationRisk, OperationStatus
from app.models.user import User, UserRole
from app.models.user_tenant_role import TenantRole


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_tenant(tenant_id=None):
    t = MagicMock()
    t.id = tenant_id or uuid4()
    return t


def _ctx(user, tenant, role=TenantRole.admin):
    return TenantContext(user=user, tenant=tenant, role=role)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tenant_a_id():
    return uuid4()


@pytest.fixture
def tenant_b_id():
    return uuid4()


@pytest_asyncio.fixture
async def user_a(db_session: AsyncSession, tenant_a_id):
    u = User(
        id=uuid4(), email=f"user-a-{uuid4()}@example.com", name="User A",
        hashed_password="x", role=UserRole.operator,
    )
    db_session.add(u)
    await db_session.flush()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def user_b(db_session: AsyncSession, tenant_b_id):
    u = User(
        id=uuid4(), email=f"user-b-{uuid4()}@example.com", name="User B",
        hashed_password="x", role=UserRole.operator,
    )
    db_session.add(u)
    await db_session.flush()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def device_a(db_session: AsyncSession, tenant_a_id):
    d = Device(
        id=uuid4(), tenant_id=tenant_a_id, name="Firewall-TenantA",
        vendor=VendorEnum.fortinet, category=DeviceCategory.firewall,
        host="10.0.1.1", port=443, encrypted_credentials="dummy",
    )
    db_session.add(d)
    await db_session.flush()
    await db_session.refresh(d)
    return d


@pytest_asyncio.fixture
async def device_b(db_session: AsyncSession, tenant_b_id):
    d = Device(
        id=uuid4(), tenant_id=tenant_b_id, name="Firewall-TenantB",
        vendor=VendorEnum.sonicwall, category=DeviceCategory.firewall,
        host="10.0.2.1", port=443, encrypted_credentials="dummy",
    )
    db_session.add(d)
    await db_session.flush()
    await db_session.refresh(d)
    return d


@pytest_asyncio.fixture
async def operation_b(db_session: AsyncSession, user_b, device_b):
    op = Operation(
        id=uuid4(), user_id=user_b.id, device_id=device_b.id,
        natural_language_input="list rules",
        intent="list_rules",
        status=OperationStatus.completed,
        risk_level=OperationRisk.low,
        required_approvals=1,
        co_approvals=[],
    )
    db_session.add(op)
    await db_session.flush()
    await db_session.refresh(op)
    return op


# ── Device isolation ──────────────────────────────────────────────────────────

class TestDeviceTenantIsolation:
    async def test_get_device_from_other_tenant_returns_404(
        self, client, device_a, device_b, user_a, tenant_a_id
    ):
        """GET /devices/{id} must return 404 for a device belonging to another tenant."""
        tenant_a = _mock_tenant(tenant_a_id)
        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user_a, tenant_a)
        try:
            resp = await client.get(f"/devices/{device_b.id}")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 404, (
            f"SECURITY: User from tenant A received {resp.status_code} instead of 404 "
            f"when accessing device from tenant B"
        )

    async def test_list_devices_excludes_other_tenant_devices(
        self, client, device_a, device_b, user_a, tenant_a_id
    ):
        """GET /devices must only return devices belonging to the authenticated tenant."""
        tenant_a = _mock_tenant(tenant_a_id)
        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user_a, tenant_a)
        try:
            resp = await client.get("/devices")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 200
        returned_ids = {d["id"] for d in resp.json()}

        assert str(device_a.id) in returned_ids, "Own device must appear in list"
        assert str(device_b.id) not in returned_ids, (
            "SECURITY: Device from another tenant appeared in device list"
        )

    async def test_cannot_start_operation_on_other_tenant_device(
        self, client, device_b, user_a, tenant_a_id
    ):
        """POST /operations with a device_id from another tenant must return 404."""
        tenant_a = _mock_tenant(tenant_a_id)
        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user_a, tenant_a)
        try:
            resp = await client.post("/operations", json={
                "device_id": str(device_b.id),
                "natural_language_input": "list rules",
                "use_bookstack_context": False,
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 404, (
            f"SECURITY: User from tenant A could initiate operation on tenant B's device "
            f"(status {resp.status_code})"
        )

    async def test_cannot_trigger_health_check_on_other_tenant_device(
        self, client, device_b, user_a, tenant_a_id
    ):
        """POST /devices/{id}/health-check on foreign device must return 404."""
        tenant_a = _mock_tenant(tenant_a_id)
        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user_a, tenant_a)
        try:
            resp = await client.post(f"/devices/{device_b.id}/health-check")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 404


# ── Operation isolation ───────────────────────────────────────────────────────

class TestOperationTenantIsolation:
    async def test_get_operation_from_other_tenant_returns_404(
        self, client, operation_b, user_a, tenant_a_id
    ):
        """GET /operations/{id} must return 404 for an operation on another tenant's device."""
        tenant_a = _mock_tenant(tenant_a_id)
        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user_a, tenant_a)
        try:
            resp = await client.get(f"/operations/{operation_b.id}")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 404, (
            "SECURITY: User from tenant A could read an operation belonging to tenant B"
        )

    async def test_list_operations_excludes_other_tenant_operations(
        self, client, operation_b, user_a, tenant_a_id
    ):
        """GET /operations must only return operations for the authenticated tenant."""
        tenant_a = _mock_tenant(tenant_a_id)
        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user_a, tenant_a)
        try:
            resp = await client.get("/operations")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 200
        returned_ids = {o["id"] for o in resp.json()}
        assert str(operation_b.id) not in returned_ids, (
            "SECURITY: Operation from another tenant appeared in operation list"
        )

    async def test_cannot_execute_operation_from_other_tenant(
        self, client, operation_b, user_a, tenant_a_id
    ):
        """POST /operations/{id}/execute on foreign operation must return 404."""
        tenant_a = _mock_tenant(tenant_a_id)
        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user_a, tenant_a)
        try:
            resp = await client.post(f"/operations/{operation_b.id}/execute")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 404, (
            "SECURITY: User from tenant A could execute an operation belonging to tenant B"
        )

    async def test_cannot_submit_review_for_other_tenant_operation(
        self, client, operation_b, user_a, tenant_a_id
    ):
        """POST /operations/{id}/submit-review on foreign operation must return 404."""
        tenant_a = _mock_tenant(tenant_a_id)
        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user_a, tenant_a)
        try:
            resp = await client.post(f"/operations/{operation_b.id}/submit-review")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 404

    async def test_cannot_co_approve_other_tenant_operation(
        self, client, operation_b, user_a, tenant_a_id
    ):
        """POST /operations/{id}/co-approve on foreign operation must return 404."""
        tenant_a = _mock_tenant(tenant_a_id)
        app.dependency_overrides[get_tenant_context] = lambda: _ctx(user_a, tenant_a)
        try:
            resp = await client.post(f"/operations/{operation_b.id}/co-approve")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 404
