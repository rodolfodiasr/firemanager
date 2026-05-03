"""pfSense REST API connector (requires pfSense-API package by jaredhendrickson13)."""
import time

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


class PfSenseConnector(BaseConnector):
    """pfSense via pfSense-API package (github.com/jaredhendrickson13/pfsense-api).

    Auth: X-API-Key header.
    Credentials: auth_type=token, token=<api_key>.
    """

    def __init__(self, host: str, api_key: str, verify_ssl: bool = False) -> None:
        self.base_url = host.rstrip("/")
        self.api_key = api_key
        self.verify_ssl = verify_ssl

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-API-Key": self.api_key},
            verify=self.verify_ssl,
            timeout=30.0,
        )

    async def test_connection(self) -> ConnectionResult:
        start = time.monotonic()
        try:
            async with self._client() as client:
                resp = await client.get("/api/v1/status/system")
                resp.raise_for_status()
                data = resp.json()
                latency = (time.monotonic() - start) * 1000
                version = data.get("data", {}).get("base_version", "unknown")
                return ConnectionResult(success=True, latency_ms=latency, firmware_version=version)
        except Exception as exc:
            return ConnectionResult(success=False, error=str(exc))

    async def list_rules(self) -> list[FirewallRule]:
        async with self._client() as client:
            resp = await client.get("/api/v1/firewall/rule")
            resp.raise_for_status()
            data = resp.json()
            rules = []
            for r in data.get("data", []):
                rules.append(FirewallRule(
                    rule_id=str(r.get("tracker", "")),
                    name=r.get("descr", ""),
                    src=r.get("src", "any"),
                    dst=r.get("dst", "any"),
                    service=str(r.get("dstport", "any")),
                    action=r.get("type", "pass"),
                    enabled=not r.get("disabled", False),
                    src_zone=r.get("interface", ""),
                    raw=r,
                ))
            return rules

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        async with self._client() as client:
            payload = {
                "type": spec.action if spec.action in ("pass", "block", "reject") else "pass",
                "interface": spec.src_zone or "lan",
                "ipprotocol": "inet",
                "protocol": "tcp",
                "src": spec.src_address,
                "dst": spec.dst_address,
                "dstport": spec.service,
                "descr": spec.name,
            }
            resp = await client.post("/api/v1/firewall/rule", json=payload)
            resp.raise_for_status()
            await client.post("/api/v1/firewall/apply")
            return ExecutionResult(success=True, raw_response=resp.json())

    async def delete_rule(self, rule_id: str) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.delete(f"/api/v1/firewall/rule?tracker={rule_id}")
            resp.raise_for_status()
            await client.post("/api/v1/firewall/apply")
            return ExecutionResult(success=True)

    async def edit_rule(self, rule_id: str, spec: RuleSpec) -> ExecutionResult:
        async with self._client() as client:
            payload = {
                "tracker": rule_id,
                "descr": spec.name,
                "src": spec.src_address,
                "dst": spec.dst_address,
                "dstport": spec.service,
            }
            resp = await client.put("/api/v1/firewall/rule", json=payload)
            resp.raise_for_status()
            await client.post("/api/v1/firewall/apply")
            return ExecutionResult(success=True)

    async def create_group(self, spec: GroupSpec) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.post("/api/v1/firewall/alias", json={
                "name": spec.name,
                "type": "host",
                "address": spec.members,
                "descr": spec.comment or "",
            })
            resp.raise_for_status()
            await client.post("/api/v1/firewall/apply")
            return ExecutionResult(success=True)

    async def get_config_snapshot(self) -> str:
        async with self._client() as client:
            resp = await client.get("/api/v1/diagnostics/config_history")
            return resp.text

    async def list_nat_policies(self) -> list[NatPolicy]:
        async with self._client() as client:
            resp = await client.get("/api/v1/firewall/nat/port_forward")
            resp.raise_for_status()
            result = []
            for r in resp.json().get("data", []):
                result.append(NatPolicy(
                    rule_id=str(r.get("tracker", "")),
                    name=r.get("descr", ""),
                    inbound=r.get("interface", ""),
                    outbound="",
                    source=r.get("src", "any"),
                    translated_source="original",
                    destination=r.get("dst", "any"),
                    translated_destination=r.get("target", ""),
                    service=str(r.get("dstport", "any")),
                    translated_service=str(r.get("local-port", "any")),
                    enabled=not r.get("disabled", False),
                    comment=r.get("descr", ""),
                    raw=r,
                ))
            return result

    async def create_nat_policy(self, spec: NatSpec) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.post("/api/v1/firewall/nat/port_forward", json={
                "interface": spec.inbound_interface,
                "src": spec.source,
                "dst": spec.destination,
                "target": spec.translated_destination,
                "descr": spec.name or spec.comment or "",
                "enable": spec.enable,
            })
            resp.raise_for_status()
            await client.post("/api/v1/firewall/apply")
            return ExecutionResult(success=True)

    async def delete_nat_policy(self, rule_id: str) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.delete(f"/api/v1/firewall/nat/port_forward?tracker={rule_id}")
            resp.raise_for_status()
            await client.post("/api/v1/firewall/apply")
            return ExecutionResult(success=True)

    async def list_route_policies(self) -> list[RoutePolicy]:
        async with self._client() as client:
            resp = await client.get("/api/v1/routing/static_route")
            resp.raise_for_status()
            result = []
            for i, r in enumerate(resp.json().get("data", [])):
                result.append(RoutePolicy(
                    rule_id=str(i),
                    name=r.get("descr", ""),
                    interface=r.get("interface", ""),
                    source="any",
                    destination=r.get("network", ""),
                    service="any",
                    gateway=r.get("gateway", ""),
                    metric=int(r.get("metric", 1) or 1),
                    distance=1,
                    route_type="static",
                    comment=r.get("descr", ""),
                    enabled=not r.get("disabled", False),
                    raw=r,
                ))
            return result

    async def create_route_policy(self, spec: RouteSpec) -> ExecutionResult:
        async with self._client() as client:
            payload = {
                "network": spec.destination,
                "gateway": spec.gateway,
                "descr": spec.name or spec.comment or "",
                "disabled": False,
            }
            resp = await client.post("/api/v1/routing/static_route", json=payload)
            resp.raise_for_status()
            await client.post("/api/v1/routing/apply")
            return ExecutionResult(success=True, raw_response=resp.json())

    async def delete_route_policy(self, rule_id: str) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.delete(f"/api/v1/routing/static_route?id={rule_id}")
            resp.raise_for_status()
            await client.post("/api/v1/routing/apply")
            return ExecutionResult(success=True)

    async def get_security_status(self) -> dict:
        """Return pfSense firewall state summary, interface info, and system status."""
        result: dict = {}
        async with self._client() as client:
            # Firewall state summary (active connections)
            try:
                r = await client.get("/api/v1/diagnostics/state_summary")
                if r.status_code == 200:
                    result["state_summary"] = r.json().get("data", {})
            except Exception:
                result["state_summary"] = {}

            # System info (CPU, memory, uptime, version)
            try:
                r = await client.get("/api/v1/status/system")
                if r.status_code == 200:
                    result["system"] = r.json().get("data", {})
            except Exception:
                result["system"] = {}

            # Configured interfaces
            try:
                r = await client.get("/api/v1/interface")
                if r.status_code == 200:
                    result["interfaces"] = r.json().get("data", [])
            except Exception:
                result["interfaces"] = []

            # Firewall aliases (address groups / blocklists)
            try:
                r = await client.get("/api/v1/firewall/alias")
                if r.status_code == 200:
                    result["aliases"] = r.json().get("data", [])
            except Exception:
                result["aliases"] = []

            # VPN status (OpenVPN — if configured)
            try:
                r = await client.get("/api/v1/vpn/openvpn/server")
                if r.status_code == 200:
                    result["openvpn_servers"] = r.json().get("data", [])
            except Exception:
                result["openvpn_servers"] = []

            # IPSec status (if configured)
            try:
                r = await client.get("/api/v1/vpn/ipsec/phase1")
                if r.status_code == 200:
                    result["ipsec_phase1"] = r.json().get("data", [])
            except Exception:
                result["ipsec_phase1"] = []

        return result
