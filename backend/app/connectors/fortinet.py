"""Fortinet FortiOS 7.x REST API connector."""
import json
import time
from typing import Any

import httpx

from app.connectors.base import (
    BaseConnector,
    ConnectionResult,
    ExecutionResult,
    FirewallRule,
    GroupSpec,
    RuleSpec,
)


class FortinetConnector(BaseConnector):
    """FortiOS 7.x REST API (API Token auth)."""

    def __init__(self, host: str, token: str, vdom: str = "root", verify_ssl: bool = False) -> None:
        self.base_url = host.rstrip("/")
        self.token = token
        self.vdom = vdom
        self.verify_ssl = verify_ssl

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.token}"},
            verify=self.verify_ssl,
            timeout=30.0,
        )

    async def test_connection(self) -> ConnectionResult:
        start = time.monotonic()
        try:
            async with self._client() as client:
                resp = await client.get(f"/api/v2/cmdb/system/status?vdom={self.vdom}")
                resp.raise_for_status()
                data = resp.json()
                latency = (time.monotonic() - start) * 1000
                version = data.get("results", {}).get("Version", "unknown")
                return ConnectionResult(success=True, latency_ms=latency, firmware_version=version)
        except Exception as exc:
            return ConnectionResult(success=False, error=str(exc))

    async def list_rules(self) -> list[FirewallRule]:
        async with self._client() as client:
            resp = await client.get(f"/api/v2/cmdb/firewall/policy?vdom={self.vdom}")
            resp.raise_for_status()
            data = resp.json()
            rules = []
            for r in data.get("results", []):
                rules.append(
                    FirewallRule(
                        rule_id=str(r.get("policyid", "")),
                        name=r.get("name", ""),
                        src=str(r.get("srcaddr", [{}])[0].get("name", "any")),
                        dst=str(r.get("dstaddr", [{}])[0].get("name", "any")),
                        service=str(r.get("service", [{}])[0].get("name", "ALL")),
                        action=r.get("action", "accept"),
                        enabled=r.get("status", "enable") == "enable",
                        raw=r,
                    )
                )
            return rules

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        payload: dict[str, Any] = {
            "name": spec.name,
            "srcintf": [{"name": "any"}],
            "dstintf": [{"name": "any"}],
            "srcaddr": [{"name": spec.src_address}],
            "dstaddr": [{"name": spec.dst_address}],
            "service": [{"name": spec.service}],
            "action": spec.action,
            "status": "enable",
            "comments": spec.comment or "",
        }
        payload.update(spec.extra)
        async with self._client() as client:
            resp = await client.post(
                f"/api/v2/cmdb/firewall/policy?vdom={self.vdom}", json=payload
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                rule_id = str(data.get("mkey", ""))
                return ExecutionResult(success=True, rule_id=rule_id, raw_response=data)
            return ExecutionResult(success=False, error=resp.text)

    async def create_group(self, spec: GroupSpec) -> ExecutionResult:
        payload = {
            "name": spec.name,
            "member": [{"name": m} for m in spec.members],
            "comment": spec.comment or "",
        }
        async with self._client() as client:
            resp = await client.post(
                f"/api/v2/cmdb/firewall/addrgrp?vdom={self.vdom}", json=payload
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                return ExecutionResult(success=True, rule_id=spec.name, raw_response=data)
            return ExecutionResult(success=False, error=resp.text)

    async def delete_rule(self, rule_id: str) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.delete(
                f"/api/v2/cmdb/firewall/policy/{rule_id}?vdom={self.vdom}"
            )
            if resp.status_code in (200, 204):
                return ExecutionResult(success=True, rule_id=rule_id)
            return ExecutionResult(success=False, error=resp.text)

    async def edit_rule(self, rule_id: str, spec: RuleSpec) -> ExecutionResult:
        payload: dict[str, Any] = {
            "name": spec.name,
            "srcaddr": [{"name": spec.src_address}],
            "dstaddr": [{"name": spec.dst_address}],
            "service": [{"name": spec.service}],
            "action": spec.action,
            "comments": spec.comment or "",
        }
        payload.update(spec.extra)
        async with self._client() as client:
            resp = await client.put(
                f"/api/v2/cmdb/firewall/policy/{rule_id}?vdom={self.vdom}", json=payload
            )
            if resp.status_code in (200, 204):
                return ExecutionResult(success=True, rule_id=rule_id)
            return ExecutionResult(success=False, error=resp.text)

    async def get_config_snapshot(self) -> str:
        async with self._client() as client:
            resp = await client.get(f"/api/v2/cmdb/firewall/policy?vdom={self.vdom}")
            resp.raise_for_status()
            return json.dumps(resp.json(), indent=2)
