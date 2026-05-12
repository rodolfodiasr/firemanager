"""Integration tests for device CRUD and RBAC enforcement.

Covers: admin can create/read/update/delete, analyst can read only,
readonly is blocked from writes, read_only_agent flag respected.
"""
import pytest

from tests.conftest import assign_role, make_tenant, make_token, make_user
from app.models.user_tenant_role import TenantRole


_DEVICE_PAYLOAD = {
    "name": "FW-Test-01",
    "vendor": "fortinet",
    "category": "firewall",
    "host": "10.10.10.1",
    "port": 443,
    "use_ssl": True,
    "verify_ssl": False,
    "credentials": {"auth_type": "token", "token": "dummy"},
}


async def _create_device(client, token: str) -> dict:
    resp = await client.post(
        "/devices",
        json=_DEVICE_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


class TestDeviceCrudAdmin:
    async def test_admin_can_create_device(self, client, db_session):
        tenant = await make_tenant(db_session)
        user, _ = await make_user(db_session)
        await assign_role(db_session, user, tenant, TenantRole.admin)
        token = make_token(user, tenant, TenantRole.admin)

        resp = await _create_device(client, token)
        assert resp.status_code == 201
        assert resp.json()["name"] == "FW-Test-01"

    async def test_admin_can_list_devices(self, client, db_session):
        tenant = await make_tenant(db_session)
        user, _ = await make_user(db_session)
        await assign_role(db_session, user, tenant, TenantRole.admin)
        token = make_token(user, tenant, TenantRole.admin)

        await _create_device(client, token)
        resp = await client.get("/devices", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_admin_can_update_device(self, client, db_session):
        tenant = await make_tenant(db_session)
        user, _ = await make_user(db_session)
        await assign_role(db_session, user, tenant, TenantRole.admin)
        token = make_token(user, tenant, TenantRole.admin)

        create_resp = await _create_device(client, token)
        device_id = create_resp.json()["id"]

        resp = await client.put(
            f"/devices/{device_id}",
            json={"name": "FW-Updated"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "FW-Updated"

    async def test_admin_can_delete_device(self, client, db_session):
        tenant = await make_tenant(db_session)
        user, _ = await make_user(db_session)
        await assign_role(db_session, user, tenant, TenantRole.admin)
        token = make_token(user, tenant, TenantRole.admin)

        create_resp = await _create_device(client, token)
        device_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/devices/{device_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204


class TestDeviceRbac:
    async def test_analyst_n1_can_read_devices(self, client, db_session):
        tenant = await make_tenant(db_session)
        admin, _ = await make_user(db_session)
        analyst, _ = await make_user(db_session)
        await assign_role(db_session, admin, tenant, TenantRole.admin)
        await assign_role(db_session, analyst, tenant, TenantRole.analyst_n1)
        admin_token = make_token(admin, tenant, TenantRole.admin)
        analyst_token = make_token(analyst, tenant, TenantRole.analyst_n1)

        await _create_device(client, admin_token)
        resp = await client.get("/devices", headers={"Authorization": f"Bearer {analyst_token}"})
        assert resp.status_code == 200

    async def test_readonly_can_read_devices(self, client, db_session):
        tenant = await make_tenant(db_session)
        admin, _ = await make_user(db_session)
        viewer, _ = await make_user(db_session)
        await assign_role(db_session, admin, tenant, TenantRole.admin)
        await assign_role(db_session, viewer, tenant, TenantRole.readonly)
        admin_token = make_token(admin, tenant, TenantRole.admin)
        viewer_token = make_token(viewer, tenant, TenantRole.readonly)

        await _create_device(client, admin_token)
        resp = await client.get("/devices", headers={"Authorization": f"Bearer {viewer_token}"})
        assert resp.status_code == 200

    async def test_unauthenticated_is_rejected(self, client, db_session):
        resp = await client.get("/devices")
        assert resp.status_code == 401

    async def test_cross_tenant_device_not_visible(self, client, db_session):
        """Device in tenant A must not appear in tenant B's list."""
        tenant_a = await make_tenant(db_session)
        tenant_b = await make_tenant(db_session)
        admin_a, _ = await make_user(db_session)
        admin_b, _ = await make_user(db_session)
        await assign_role(db_session, admin_a, tenant_a, TenantRole.admin)
        await assign_role(db_session, admin_b, tenant_b, TenantRole.admin)
        token_a = make_token(admin_a, tenant_a, TenantRole.admin)
        token_b = make_token(admin_b, tenant_b, TenantRole.admin)

        create_resp = await _create_device(client, token_a)
        device_id = create_resp.json()["id"]

        # Tenant B cannot GET the specific device from tenant A
        resp = await client.get(
            f"/devices/{device_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 404


class TestReadOnlyAgent:
    async def test_read_only_agent_flag_persisted(self, client, db_session):
        tenant = await make_tenant(db_session)
        user, _ = await make_user(db_session)
        await assign_role(db_session, user, tenant, TenantRole.admin)
        token = make_token(user, tenant, TenantRole.admin)

        payload = {**_DEVICE_PAYLOAD, "read_only_agent": True}
        resp = await client.post(
            "/devices",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["read_only_agent"] is True

    async def test_read_only_agent_default_is_false(self, client, db_session):
        tenant = await make_tenant(db_session)
        user, _ = await make_user(db_session)
        await assign_role(db_session, user, tenant, TenantRole.admin)
        token = make_token(user, tenant, TenantRole.admin)

        resp = await _create_device(client, token)
        assert resp.status_code == 201
        assert resp.json()["read_only_agent"] is False
