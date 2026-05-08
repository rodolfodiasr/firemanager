"""Palo Alto PAN-OS REST API connector."""
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


class PaloAltoConnector(BaseConnector):
    """Palo Alto PAN-OS REST API (API Key auth)."""

    def __init__(
        self,
        host: str,
        api_key: str,
        vsys: str = "vsys1",
        verify_ssl: bool = False,
    ) -> None:
        self.base_url = host.rstrip("/")
        self.api_key = api_key
        self.vsys = vsys
        self.verify_ssl = verify_ssl
        self._api_base = f"{self.base_url}/restapi/v10.2"

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers={"X-PAN-KEY": self.api_key},
            verify=self.verify_ssl,
            timeout=30.0,
        )

    async def test_connection(self) -> ConnectionResult:
        if not self.api_key or not self.api_key.strip():
            return ConnectionResult(
                success=False,
                error="API Key não configurada. Edite o dispositivo e informe a chave de API.",
            )
        start = time.monotonic()
        try:
            async with self._client() as client:
                resp = await client.get(f"{self._api_base}/Device/System")
                if resp.status_code == 401:
                    return ConnectionResult(
                        success=False,
                        error="API Key inválida ou sem permissão (HTTP 401).",
                    )
                if resp.status_code == 403:
                    return ConnectionResult(
                        success=False,
                        error="Acesso negado (HTTP 403). Verifique as permissões da API Key.",
                    )
                resp.raise_for_status()
                data = resp.json()
                latency = (time.monotonic() - start) * 1000
                entry = data.get("result", {}).get("system", {})
                version = entry.get("sw-version", "unknown")
                return ConnectionResult(success=True, latency_ms=latency, firmware_version=version)
        except Exception as exc:
            return ConnectionResult(success=False, error=str(exc))

    async def get_policies(self) -> list[dict[str, Any]]:
        """Retrieve security rules from vsys1."""
        async with self._client() as client:
            resp = await client.get(
                f"{self._api_base}/Policies/SecurityRules",
                params={"location": "vsys", "vsys": self.vsys},
            )
            resp.raise_for_status()
            return resp.json().get("result", {}).get("entry", [])

    async def get_address_objects(self) -> list[dict[str, Any]]:
        """Retrieve address objects from vsys."""
        async with self._client() as client:
            resp = await client.get(
                f"{self._api_base}/Objects/Addresses",
                params={"location": "vsys", "vsys": self.vsys},
            )
            resp.raise_for_status()
            return resp.json().get("result", {}).get("entry", [])

    # ── BaseConnector abstract implementations ───────────────────────────────

    async def list_rules(self) -> list[FirewallRule]:
        rules: list[FirewallRule] = []
        try:
            entries = await self.get_policies()
            for r in entries:
                action = r.get("action", "deny")
                src_list = r.get("from", {}).get("member", ["any"])
                dst_list = r.get("to", {}).get("member", ["any"])
                src_addr = r.get("source", {}).get("member", ["any"])
                dst_addr = r.get("destination", {}).get("member", ["any"])
                svc_list = r.get("service", {}).get("member", ["any"])
                rules.append(FirewallRule(
                    rule_id=r.get("@name", ""),
                    name=r.get("@name", ""),
                    src=", ".join(src_addr) if src_addr else "any",
                    dst=", ".join(dst_addr) if dst_addr else "any",
                    service=", ".join(svc_list) if svc_list else "any",
                    action=action,
                    enabled=r.get("disabled", "no") != "yes",
                    raw=r,
                ))
        except Exception as exc:
            logger.warning("PaloAlto list_rules failed: %s", exc)
        return rules

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        rule_name = spec.name
        src = spec.src_address or "any"
        dst = spec.dst_address or "any"
        action = "allow" if spec.action in ("accept", "allow", "permit", "pass") else "deny"
        payload: dict[str, Any] = {
            "@name": rule_name,
            "from": {"member": ["any"]},
            "to": {"member": ["any"]},
            "source": {"member": [src]},
            "destination": {"member": [dst]},
            "service": {"member": ["any"]},
            "action": action,
            "description": spec.comment or "",
        }
        async with self._client() as client:
            resp = await client.post(
                f"{self._api_base}/Policies/SecurityRules",
                params={"location": "vsys", "vsys": self.vsys, "name": rule_name},
                json={"entry": payload},
            )
            if resp.status_code in (200, 201):
                return ExecutionResult(success=True, rule_id=rule_name, raw_response=resp.json())
            logger.error("PaloAlto create_rule failed %s: %s", resp.status_code, resp.text)
            return ExecutionResult(success=False, error=resp.text)

    async def delete_rule(self, rule_id: str) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.delete(
                f"{self._api_base}/Policies/SecurityRules",
                params={"location": "vsys", "vsys": self.vsys, "name": rule_id},
            )
            if resp.status_code in (200, 204):
                return ExecutionResult(success=True, rule_id=rule_id)
            return ExecutionResult(success=False, error=resp.text)

    async def edit_rule(self, rule_id: str, spec: RuleSpec) -> ExecutionResult:
        src = spec.src_address or "any"
        dst = spec.dst_address or "any"
        action = "allow" if spec.action in ("accept", "allow", "permit", "pass") else "deny"
        payload: dict[str, Any] = {
            "@name": rule_id,
            "from": {"member": ["any"]},
            "to": {"member": ["any"]},
            "source": {"member": [src]},
            "destination": {"member": [dst]},
            "service": {"member": ["any"]},
            "action": action,
            "description": spec.comment or "",
        }
        async with self._client() as client:
            resp = await client.put(
                f"{self._api_base}/Policies/SecurityRules",
                params={"location": "vsys", "vsys": self.vsys, "name": rule_id},
                json={"entry": payload},
            )
            if resp.status_code in (200, 204):
                return ExecutionResult(success=True, rule_id=rule_id)
            return ExecutionResult(success=False, error=resp.text)

    async def create_group(self, spec: GroupSpec) -> ExecutionResult:
        payload: dict[str, Any] = {
            "@name": spec.name,
            "static": {"member": spec.members},
        }
        async with self._client() as client:
            resp = await client.post(
                f"{self._api_base}/Objects/AddressGroups",
                params={"location": "vsys", "vsys": self.vsys, "name": spec.name},
                json={"entry": payload},
            )
            if resp.status_code in (200, 201):
                return ExecutionResult(success=True, rule_id=spec.name, raw_response=resp.json())
            return ExecutionResult(success=False, error=resp.text)

    async def get_config_snapshot(self) -> str:
        entries = await self.get_policies()
        return json.dumps(entries, indent=2)

    # ── NAT ──────────────────────────────────────────────────────────────────

    async def list_nat_policies(self) -> list[NatPolicy]:
        nat_policies: list[NatPolicy] = []
        try:
            async with self._client() as client:
                resp = await client.get(
                    f"{self._api_base}/Policies/NatRules",
                    params={"location": "vsys", "vsys": self.vsys},
                )
                if resp.status_code == 200:
                    for r in resp.json().get("result", {}).get("entry", []):
                        nat_policies.append(NatPolicy(
                            rule_id=r.get("@name", ""),
                            name=r.get("@name", ""),
                            inbound="any",
                            outbound="any",
                            source="any",
                            translated_source="",
                            destination="any",
                            translated_destination="",
                            service="any",
                            translated_service="",
                            enabled=r.get("disabled", "no") != "yes",
                            comment=r.get("description", ""),
                            raw=r,
                        ))
        except Exception as exc:
            logger.warning("PaloAlto list_nat_policies failed: %s", exc)
        return nat_policies

    async def create_nat_policy(self, spec: NatSpec) -> ExecutionResult:
        return ExecutionResult(success=False, error="NAT creation not implemented for PAN-OS REST")

    async def delete_nat_policy(self, rule_id: str) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.delete(
                f"{self._api_base}/Policies/NatRules",
                params={"location": "vsys", "vsys": self.vsys, "name": rule_id},
            )
            if resp.status_code in (200, 204):
                return ExecutionResult(success=True, rule_id=rule_id)
            return ExecutionResult(success=False, error=resp.text)

    # ── Routes ────────────────────────────────────────────────────────────────

    async def list_route_policies(self) -> list[RoutePolicy]:
        return []

    async def create_route_policy(self, spec: RouteSpec) -> ExecutionResult:
        return ExecutionResult(success=False, error="Route management not implemented for PAN-OS REST")

    async def delete_route_policy(self, rule_id: str) -> ExecutionResult:
        return ExecutionResult(success=False, error="Route management not implemented for PAN-OS REST")

    # ── Stats ─────────────────────────────────────────────────────────────────

    async def get_rule_statistics(self) -> dict[str, int]:
        return {}

    async def get_security_status(self) -> dict:
        return {}
