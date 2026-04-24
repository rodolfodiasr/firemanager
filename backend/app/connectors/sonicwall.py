"""SonicWall SonicOS 6/7/8 REST API connector."""
import contextlib
import json
import time
from typing import Any, AsyncGenerator

import httpx

from app.connectors.base import (
    BaseConnector,
    ConnectionResult,
    ExecutionResult,
    FirewallRule,
    GroupSpec,
    RuleSpec,
)


class SonicWallConnector(BaseConnector):
    """SonicOS 6.5/7.x/8.x REST API connector.

    SonicOS 7+ uses session-based auth: POST /api/sonicos/auth to get a
    session cookie, then use the cookie for all subsequent requests.
    SonicOS 6 requires an explicit commit after mutations.
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        os_version: int = 7,
        verify_ssl: bool = False,
    ) -> None:
        self.base_url = host.rstrip("/")
        self.username = username
        self.password = password
        self.os_version = os_version
        self.verify_ssl = verify_ssl

    @contextlib.asynccontextmanager
    async def _session(self) -> AsyncGenerator[httpx.AsyncClient, None]:
        """Open an authenticated SonicOS session and yield the client.

        SonicOS 7+: POST /api/sonicos/auth with Basic Auth → session cookie.
        SonicOS 6.x: also tries Digest Auth per-request as fallback.
        """
        auth_body = {
            "override": True,
            "user": {"name": self.username, "password": self.password},
        }
        base_headers = {"Content-Type": "application/json", "Accept": "application/json"}

        # Try Basic Auth first, then Digest Auth as fallback
        for auth in (
            httpx.BasicAuth(self.username, self.password),
            httpx.DigestAuth(self.username, self.password),
        ):
            async with httpx.AsyncClient(
                base_url=self.base_url,
                verify=self.verify_ssl,
                headers=base_headers,
                timeout=30.0,
            ) as client:
                resp = await client.post("/api/sonicos/auth", json=auth_body, auth=auth)
                if resp.status_code == 401:
                    continue  # try next auth method

                if not resp.is_success:
                    raise Exception(
                        f"SonicWall auth failed: HTTP {resp.status_code} — {resp.text[:300]}"
                    )

                try:
                    body = resp.json()
                    status_obj = body.get("status", {})
                    if status_obj.get("success") is False:
                        info = status_obj.get("info", [{}])
                        reason = info[0].get("message", "Unauthorized") if info else "Unauthorized"
                        raise Exception(f"SonicWall auth rejected: {reason}")
                except (ValueError, KeyError):
                    pass

                try:
                    yield client
                    return
                finally:
                    try:
                        await client.delete("/api/sonicos/auth")
                    except Exception:
                        pass

        raise Exception("SonicWall auth failed: both Basic and Digest auth returned 401")

    async def _commit(self, client: httpx.AsyncClient) -> None:
        """SonicOS 6 requires explicit commit to persist changes."""
        if self.os_version == 6:
            await client.post("/api/sonicos/config/pending")

    async def test_connection(self) -> ConnectionResult:
        start = time.monotonic()
        try:
            async with self._session() as client:
                latency = (time.monotonic() - start) * 1000

                firmware = "unknown"
                try:
                    dev_resp = await client.get("/api/sonicos/device")
                    if dev_resp.status_code == 200:
                        dev_data = dev_resp.json()
                        firmware = (
                            dev_data.get("device", {}).get("firmware_version")
                            or dev_data.get("firmware_version")
                            or "unknown"
                        )
                except Exception:
                    pass

                return ConnectionResult(success=True, latency_ms=latency, firmware_version=firmware)
        except Exception as exc:
            return ConnectionResult(success=False, error=str(exc))

    async def list_rules(self) -> list[FirewallRule]:
        async with self._session() as client:
            resp = await client.get("/api/sonicos/access-rules/ipv4")
            resp.raise_for_status()
            data = resp.json()
            rules = []
            for r in data.get("access_rules", {}).get("ipv4", []):
                rules.append(
                    FirewallRule(
                        rule_id=str(r.get("rule_id", r.get("uuid", ""))),
                        name=r.get("name", ""),
                        src=r.get("source", {}).get("address", {}).get("name", "Any"),
                        dst=r.get("destination", {}).get("address", {}).get("name", "Any"),
                        service=r.get("service", {}).get("name", "Any"),
                        action=r.get("action", "allow"),
                        enabled=r.get("enable", True),
                        raw=r,
                    )
                )
            return rules

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        payload: dict[str, Any] = {
            "access_rules": {
                "ipv4": [
                    {
                        "name": spec.name,
                        "action": {"action": spec.action},
                        "from": {"zone": "LAN"},
                        "to": {"zone": "WAN"},
                        "source": {"address": {"name": spec.src_address}},
                        "destination": {"address": {"name": spec.dst_address}},
                        "service": {"name": spec.service},
                        "comment": spec.comment or "",
                        "enable": True,
                    }
                ]
            }
        }
        async with self._session() as client:
            resp = await client.post("/api/sonicos/access-rules/ipv4", json=payload)
            await self._commit(client)
            if resp.status_code in (200, 201):
                data = resp.json()
                return ExecutionResult(success=True, raw_response=data)
            return ExecutionResult(success=False, error=resp.text)

    async def create_group(self, spec: GroupSpec) -> ExecutionResult:
        payload = {
            "address_groups": {
                "ipv4": [{"name": spec.name, "address_objects": [{"name": m} for m in spec.members]}]
            }
        }
        async with self._session() as client:
            resp = await client.post("/api/sonicos/address-groups/ipv4", json=payload)
            await self._commit(client)
            if resp.status_code in (200, 201):
                return ExecutionResult(success=True, rule_id=spec.name, raw_response=resp.json())
            return ExecutionResult(success=False, error=resp.text)

    async def delete_rule(self, rule_id: str) -> ExecutionResult:
        async with self._session() as client:
            resp = await client.delete(f"/api/sonicos/access-rules/ipv4/uuid/{rule_id}")
            await self._commit(client)
            if resp.status_code in (200, 204):
                return ExecutionResult(success=True, rule_id=rule_id)
            return ExecutionResult(success=False, error=resp.text)

    async def edit_rule(self, rule_id: str, spec: RuleSpec) -> ExecutionResult:
        payload: dict[str, Any] = {
            "access_rules": {
                "ipv4": [
                    {
                        "name": spec.name,
                        "source": {"address": {"name": spec.src_address}},
                        "destination": {"address": {"name": spec.dst_address}},
                        "service": {"name": spec.service},
                        "action": {"action": spec.action},
                        "comment": spec.comment or "",
                    }
                ]
            }
        }
        async with self._session() as client:
            resp = await client.put(f"/api/sonicos/access-rules/ipv4/uuid/{rule_id}", json=payload)
            await self._commit(client)
            if resp.status_code in (200, 204):
                return ExecutionResult(success=True, rule_id=rule_id)
            return ExecutionResult(success=False, error=resp.text)

    async def get_config_snapshot(self) -> str:
        async with self._session() as client:
            resp = await client.get("/api/sonicos/access-rules/ipv4")
            resp.raise_for_status()
            return json.dumps(resp.json(), indent=2)
