"""OPNsense REST API connector."""
import base64
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


class OPNsenseConnector(BaseConnector):
    """OPNsense built-in REST API.

    Auth: Basic auth with API key + API secret.
    Credentials: auth_type=user_pass, username=<api_key>, password=<api_secret>.
    API keys are created in System > Access > Users > Edit > API Keys.
    """

    def __init__(self, host: str, api_key: str, api_secret: str, verify_ssl: bool = False) -> None:
        self.base_url = host.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.verify_ssl = verify_ssl

    def _client(self) -> httpx.AsyncClient:
        creds = base64.b64encode(f"{self.api_key}:{self.api_secret}".encode()).decode()
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Basic {creds}"},
            verify=self.verify_ssl,
            timeout=30.0,
        )

    async def test_connection(self) -> ConnectionResult:
        start = time.monotonic()
        try:
            async with self._client() as client:
                resp = await client.get("/api/core/firmware/status")
                resp.raise_for_status()
                data = resp.json()
                latency = (time.monotonic() - start) * 1000
                version = data.get("product_version", "unknown")
                return ConnectionResult(success=True, latency_ms=latency, firmware_version=version)
        except Exception as exc:
            return ConnectionResult(success=False, error=str(exc))

    async def list_rules(self) -> list[FirewallRule]:
        async with self._client() as client:
            resp = await client.post(
                "/api/firewall/filter/searchRule",
                json={"current": 1, "rowCount": 500},
            )
            resp.raise_for_status()
            rules = []
            for r in resp.json().get("rows", []):
                rules.append(FirewallRule(
                    rule_id=r.get("uuid", ""),
                    name=r.get("description", ""),
                    src=r.get("source_net", "any"),
                    dst=r.get("destination_net", "any"),
                    service=r.get("destination_port", "any"),
                    action=r.get("action", "pass"),
                    enabled=r.get("enabled", "1") == "1",
                    src_zone=r.get("interface", ""),
                    raw=r,
                ))
            return rules

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        async with self._client() as client:
            payload = {"rule": {
                "action": spec.action if spec.action in ("pass", "block", "reject") else "pass",
                "interface": spec.src_zone or "lan",
                "description": spec.name,
                "source_net": spec.src_address,
                "destination_net": spec.dst_address,
                "destination_port": spec.service,
                "enabled": "1",
            }}
            resp = await client.post("/api/firewall/filter/addRule", json=payload)
            resp.raise_for_status()
            await client.post("/api/firewall/filter/apply", json={})
            data = resp.json()
            return ExecutionResult(success=True, rule_id=data.get("uuid"), raw_response=data)

    async def delete_rule(self, rule_id: str) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.post(f"/api/firewall/filter/delRule/{rule_id}")
            resp.raise_for_status()
            await client.post("/api/firewall/filter/apply", json={})
            return ExecutionResult(success=True)

    async def edit_rule(self, rule_id: str, spec: RuleSpec) -> ExecutionResult:
        async with self._client() as client:
            payload = {"rule": {
                "description": spec.name,
                "source_net": spec.src_address,
                "destination_net": spec.dst_address,
                "destination_port": spec.service,
            }}
            resp = await client.post(f"/api/firewall/filter/setRule/{rule_id}", json=payload)
            resp.raise_for_status()
            await client.post("/api/firewall/filter/apply", json={})
            return ExecutionResult(success=True)

    async def create_group(self, spec: GroupSpec) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.post("/api/firewall/alias/addItem", json={"alias": {
                "name": spec.name,
                "type": "host",
                "content": "\n".join(spec.members),
                "description": spec.comment or "",
            }})
            resp.raise_for_status()
            await client.post("/api/firewall/alias/reconfigure", json={})
            return ExecutionResult(success=True)

    async def get_config_snapshot(self) -> str:
        async with self._client() as client:
            resp = await client.get("/api/core/backup/download/this")
            return resp.text

    async def list_nat_policies(self) -> list[NatPolicy]:
        async with self._client() as client:
            resp = await client.post(
                "/api/firewall/nat/searchRule",
                json={"current": 1, "rowCount": 500},
            )
            resp.raise_for_status()
            result = []
            for r in resp.json().get("rows", []):
                result.append(NatPolicy(
                    rule_id=r.get("uuid", ""),
                    name=r.get("description", ""),
                    inbound=r.get("interface", ""),
                    outbound="",
                    source=r.get("source_net", "any"),
                    translated_source="original",
                    destination=r.get("destination_net", "any"),
                    translated_destination=r.get("target", ""),
                    service=r.get("destination_port", "any"),
                    translated_service=r.get("local_port", "any"),
                    enabled=r.get("enabled", "1") == "1",
                    comment=r.get("description", ""),
                    raw=r,
                ))
            return result

    async def create_nat_policy(self, spec: NatSpec) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.post("/api/firewall/nat/addRule", json={"rule": {
                "interface": spec.inbound_interface,
                "source_net": spec.source,
                "destination_net": spec.destination,
                "target": spec.translated_destination,
                "description": spec.name or spec.comment or "",
                "enabled": "1" if spec.enable else "0",
            }})
            resp.raise_for_status()
            await client.post("/api/firewall/nat/apply", json={})
            return ExecutionResult(success=True)

    async def delete_nat_policy(self, rule_id: str) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.post(f"/api/firewall/nat/delRule/{rule_id}")
            resp.raise_for_status()
            await client.post("/api/firewall/nat/apply", json={})
            return ExecutionResult(success=True)

    async def list_route_policies(self) -> list[RoutePolicy]:
        return []

    async def create_route_policy(self, spec: RouteSpec) -> ExecutionResult:
        return ExecutionResult(success=False, error="Not implemented for OPNsense")

    async def delete_route_policy(self, rule_id: str) -> ExecutionResult:
        return ExecutionResult(success=False, error="Not implemented for OPNsense")
