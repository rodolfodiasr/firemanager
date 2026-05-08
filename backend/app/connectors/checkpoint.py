"""Check Point R80+ Management API connector."""
import json
import logging
import time
from typing import Any

import httpx

from app.connectors.base import (
    BaseConnector,
    ConnectionResult,
    ExecutionResult,
    FirewallRule,
    GroupSpec,
    NatPolicy,
    NatSpec,
    RoutePolicy,
    RouteSpec,
    RuleSpec,
)

logger = logging.getLogger(__name__)


class CheckPointConnector(BaseConnector):
    """Check Point R80+ Management REST API (session-based auth)."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        verify_ssl: bool = False,
    ) -> None:
        self.base_url = host.rstrip("/")
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self._sid: str | None = None  # session ID after login

    def _client(self, sid: str | None = None) -> httpx.AsyncClient:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if sid:
            headers["X-chkp-sid"] = sid
        return httpx.AsyncClient(
            verify=self.verify_ssl,
            timeout=30.0,
            headers=headers,
        )

    async def login(self) -> str:
        """POST /web_api/login → returns session_id."""
        async with self._client() as client:
            resp = await client.post(
                f"{self.base_url}/web_api/login",
                json={"user": self.username, "password": self.password},
            )
            resp.raise_for_status()
            sid = resp.json().get("sid", "")
            if not sid:
                raise RuntimeError("Check Point login did not return a session ID")
            self._sid = sid
            return sid

    async def logout(self, sid: str) -> None:
        """POST /web_api/logout to invalidate the session."""
        try:
            async with self._client(sid=sid) as client:
                await client.post(f"{self.base_url}/web_api/logout", json={})
        except Exception as exc:
            logger.warning("CheckPoint logout failed: %s", exc)

    async def test_connection(self) -> ConnectionResult:
        if not self.username or not self.password:
            return ConnectionResult(
                success=False,
                error="Credenciais não configuradas. Informe usuário e senha.",
            )
        start = time.monotonic()
        sid: str | None = None
        try:
            sid = await self.login()
            async with self._client(sid=sid) as client:
                resp = await client.post(
                    f"{self.base_url}/web_api/show-api-versions", json={}
                )
                resp.raise_for_status()
                data = resp.json()
            latency = (time.monotonic() - start) * 1000
            version = data.get("current-version", "unknown")
            return ConnectionResult(success=True, latency_ms=latency, firmware_version=version)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                return ConnectionResult(success=False, error="Credenciais inválidas (HTTP 401).")
            return ConnectionResult(success=False, error=str(exc))
        except Exception as exc:
            return ConnectionResult(success=False, error=str(exc))
        finally:
            if sid:
                await self.logout(sid)

    async def get_policies(self, layer: str = "Network") -> list[dict[str, Any]]:
        """POST /web_api/show-access-rulebase — returns all rules in the given layer."""
        sid = await self.login()
        try:
            async with self._client(sid=sid) as client:
                resp = await client.post(
                    f"{self.base_url}/web_api/show-access-rulebase",
                    json={"name": layer, "limit": 500},
                )
                resp.raise_for_status()
                return resp.json().get("rulebase", [])
        finally:
            await self.logout(sid)

    # ── BaseConnector abstract implementations ───────────────────────────────

    async def list_rules(self) -> list[FirewallRule]:
        rules: list[FirewallRule] = []
        try:
            entries = await self.get_policies()
            for r in entries:
                rule_type = r.get("type", "")
                if rule_type not in ("access-rule", "rule"):
                    continue
                action_obj = r.get("action", {})
                action = action_obj.get("name", "Drop").lower()
                if action in ("accept", "allow"):
                    action = "allow"
                else:
                    action = "deny"
                src_list = [s.get("name", "Any") for s in r.get("source", [])]
                dst_list = [d.get("name", "Any") for d in r.get("destination", [])]
                svc_list = [s.get("name", "Any") for s in r.get("service", [])]
                enabled = r.get("enabled", True)
                rules.append(FirewallRule(
                    rule_id=str(r.get("uid", r.get("rule-number", ""))),
                    name=r.get("name", ""),
                    src=", ".join(src_list) or "Any",
                    dst=", ".join(dst_list) or "Any",
                    service=", ".join(svc_list) or "Any",
                    action=action,
                    enabled=enabled,
                    raw=r,
                ))
        except Exception as exc:
            logger.warning("CheckPoint list_rules failed: %s", exc)
        return rules

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        action = "Accept" if spec.action in ("accept", "allow", "permit", "pass") else "Drop"
        sid = await self.login()
        try:
            async with self._client(sid=sid) as client:
                payload: dict[str, Any] = {
                    "layer": "Network",
                    "position": "bottom",
                    "name": spec.name,
                    "source": [spec.src_address or "Any"],
                    "destination": [spec.dst_address or "Any"],
                    "service": [spec.service or "Any"],
                    "action": action,
                    "track": {"type": "Log"},
                    "comments": spec.comment or "",
                }
                resp = await client.post(
                    f"{self.base_url}/web_api/add-access-rule", json=payload
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    # Publish changes
                    await client.post(f"{self.base_url}/web_api/publish", json={})
                    return ExecutionResult(
                        success=True,
                        rule_id=data.get("uid", spec.name),
                        raw_response=data,
                    )
                logger.error("CheckPoint create_rule failed %s: %s", resp.status_code, resp.text)
                return ExecutionResult(success=False, error=resp.text)
        finally:
            await self.logout(sid)

    async def delete_rule(self, rule_id: str) -> ExecutionResult:
        sid = await self.login()
        try:
            async with self._client(sid=sid) as client:
                resp = await client.post(
                    f"{self.base_url}/web_api/delete-access-rule",
                    json={"uid": rule_id, "layer": "Network"},
                )
                if resp.status_code in (200, 204):
                    await client.post(f"{self.base_url}/web_api/publish", json={})
                    return ExecutionResult(success=True, rule_id=rule_id)
                return ExecutionResult(success=False, error=resp.text)
        finally:
            await self.logout(sid)

    async def edit_rule(self, rule_id: str, spec: RuleSpec) -> ExecutionResult:
        action = "Accept" if spec.action in ("accept", "allow", "permit", "pass") else "Drop"
        sid = await self.login()
        try:
            async with self._client(sid=sid) as client:
                payload: dict[str, Any] = {
                    "uid": rule_id,
                    "layer": "Network",
                    "source": [spec.src_address or "Any"],
                    "destination": [spec.dst_address or "Any"],
                    "service": [spec.service or "Any"],
                    "action": action,
                    "comments": spec.comment or "",
                }
                resp = await client.post(
                    f"{self.base_url}/web_api/set-access-rule", json=payload
                )
                if resp.status_code in (200, 204):
                    await client.post(f"{self.base_url}/web_api/publish", json={})
                    return ExecutionResult(success=True, rule_id=rule_id)
                return ExecutionResult(success=False, error=resp.text)
        finally:
            await self.logout(sid)

    async def create_group(self, spec: GroupSpec) -> ExecutionResult:
        sid = await self.login()
        try:
            async with self._client(sid=sid) as client:
                resp = await client.post(
                    f"{self.base_url}/web_api/add-address-range",
                    json={"name": spec.name, "members": spec.members},
                )
                if resp.status_code in (200, 201):
                    await client.post(f"{self.base_url}/web_api/publish", json={})
                    return ExecutionResult(success=True, rule_id=spec.name, raw_response=resp.json())
                return ExecutionResult(success=False, error=resp.text)
        finally:
            await self.logout(sid)

    async def get_config_snapshot(self) -> str:
        entries = await self.get_policies()
        return json.dumps(entries, indent=2)

    # ── NAT ──────────────────────────────────────────────────────────────────

    async def list_nat_policies(self) -> list[NatPolicy]:
        nat_policies: list[NatPolicy] = []
        try:
            sid = await self.login()
            try:
                async with self._client(sid=sid) as client:
                    resp = await client.post(
                        f"{self.base_url}/web_api/show-nat-rulebase",
                        json={"package": "standard", "limit": 500},
                    )
                    if resp.status_code == 200:
                        for r in resp.json().get("rulebase", []):
                            nat_policies.append(NatPolicy(
                                rule_id=str(r.get("uid", "")),
                                name=r.get("name", ""),
                                inbound="any",
                                outbound="any",
                                source="any",
                                translated_source="",
                                destination="any",
                                translated_destination="",
                                service="any",
                                translated_service="",
                                enabled=r.get("enabled", True),
                                comment=r.get("comments", ""),
                                raw=r,
                            ))
            finally:
                await self.logout(sid)
        except Exception as exc:
            logger.warning("CheckPoint list_nat_policies failed: %s", exc)
        return nat_policies

    async def create_nat_policy(self, spec: NatSpec) -> ExecutionResult:
        return ExecutionResult(success=False, error="NAT creation not implemented for Check Point REST")

    async def delete_nat_policy(self, rule_id: str) -> ExecutionResult:
        return ExecutionResult(success=False, error="NAT deletion not implemented for Check Point REST")

    # ── Routes ────────────────────────────────────────────────────────────────

    async def list_route_policies(self) -> list[RoutePolicy]:
        return []

    async def create_route_policy(self, spec: RouteSpec) -> ExecutionResult:
        return ExecutionResult(success=False, error="Route management not implemented for Check Point REST")

    async def delete_route_policy(self, rule_id: str) -> ExecutionResult:
        return ExecutionResult(success=False, error="Route management not implemented for Check Point REST")

    # ── Stats ─────────────────────────────────────────────────────────────────

    async def get_rule_statistics(self) -> dict[str, int]:
        return {}

    async def get_security_status(self) -> dict:
        return {}
