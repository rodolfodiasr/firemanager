"""MikroTik RouterOS 7.x REST API connector."""
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


class MikroTikConnector(BaseConnector):
    """MikroTik RouterOS 7+ REST API (/rest/...).

    Auth: Basic auth (username + password).
    Credentials: auth_type=user_pass.
    REST API must be enabled: IP > Services > api-ssl (or api).
    """

    def __init__(self, host: str, username: str, password: str, verify_ssl: bool = False) -> None:
        self.base_url = host.rstrip("/")
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            auth=(self.username, self.password),
            verify=self.verify_ssl,
            timeout=30.0,
            headers={"Content-Type": "application/json"},
        )

    async def test_connection(self) -> ConnectionResult:
        start = time.monotonic()
        try:
            async with self._client() as client:
                resp = await client.get("/rest/system/resource")
                resp.raise_for_status()
                data = resp.json()
                latency = (time.monotonic() - start) * 1000
                version = data.get("version", "unknown")
                return ConnectionResult(success=True, latency_ms=latency, firmware_version=version)
        except Exception as exc:
            return ConnectionResult(success=False, error=str(exc))

    async def list_rules(self) -> list[FirewallRule]:
        async with self._client() as client:
            resp = await client.get("/rest/ip/firewall/filter")
            resp.raise_for_status()
            rules = []
            for r in resp.json():
                rules.append(FirewallRule(
                    rule_id=r.get(".id", ""),
                    name=r.get("comment", r.get(".id", "")),
                    src=r.get("src-address", "0.0.0.0/0"),
                    dst=r.get("dst-address", "0.0.0.0/0"),
                    service=r.get("dst-port", "any"),
                    action=r.get("action", "accept"),
                    enabled=not r.get("disabled", False),
                    src_zone=r.get("in-interface", ""),
                    dst_zone=r.get("out-interface", ""),
                    raw=r,
                ))
            return rules

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        action_map = {"accept": "accept", "deny": "drop", "drop": "drop", "reject": "reject"}
        payload: dict = {
            "chain": "forward",
            "src-address": spec.src_address,
            "dst-address": spec.dst_address,
            "action": action_map.get(spec.action, "accept"),
            "comment": spec.name,
        }
        if spec.service not in ("any", "Any", ""):
            payload["dst-port"] = spec.service
            payload["protocol"] = "tcp"
        async with self._client() as client:
            resp = await client.put("/rest/ip/firewall/filter", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return ExecutionResult(success=True, rule_id=data.get(".id"), raw_response=data)

    async def delete_rule(self, rule_id: str) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.delete(f"/rest/ip/firewall/filter/{rule_id}")
            resp.raise_for_status()
            return ExecutionResult(success=True)

    async def edit_rule(self, rule_id: str, spec: RuleSpec) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.patch(f"/rest/ip/firewall/filter/{rule_id}", json={
                "src-address": spec.src_address,
                "dst-address": spec.dst_address,
                "comment": spec.name,
            })
            resp.raise_for_status()
            return ExecutionResult(success=True)

    async def create_group(self, spec: GroupSpec) -> ExecutionResult:
        async with self._client() as client:
            for member in spec.members:
                await client.put("/rest/ip/firewall/address-list", json={
                    "list": spec.name,
                    "address": member,
                    "comment": spec.comment or "",
                })
            return ExecutionResult(success=True)

    async def get_config_snapshot(self) -> str:
        async with self._client() as client:
            resp = await client.get("/rest/ip/firewall/filter")
            return resp.text

    async def list_nat_policies(self) -> list[NatPolicy]:
        async with self._client() as client:
            resp = await client.get("/rest/ip/firewall/nat")
            resp.raise_for_status()
            result = []
            for r in resp.json():
                result.append(NatPolicy(
                    rule_id=r.get(".id", ""),
                    name=r.get("comment", ""),
                    inbound=r.get("in-interface", ""),
                    outbound=r.get("out-interface", ""),
                    source=r.get("src-address", "any"),
                    translated_source=r.get("to-addresses", "original"),
                    destination=r.get("dst-address", "any"),
                    translated_destination=r.get("to-addresses", "original"),
                    service=r.get("dst-port", "any"),
                    translated_service=r.get("to-ports", "original"),
                    enabled=not r.get("disabled", False),
                    comment=r.get("comment", ""),
                    raw=r,
                ))
            return result

    async def create_nat_policy(self, spec: NatSpec) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.put("/rest/ip/firewall/nat", json={
                "chain": "dstnat",
                "in-interface": spec.inbound_interface,
                "dst-address": spec.destination,
                "to-addresses": spec.translated_destination,
                "action": "dst-nat",
                "comment": spec.name or spec.comment or "",
                "disabled": "no" if spec.enable else "yes",
            })
            resp.raise_for_status()
            data = resp.json()
            return ExecutionResult(success=True, rule_id=data.get(".id"), raw_response=data)

    async def delete_nat_policy(self, rule_id: str) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.delete(f"/rest/ip/firewall/nat/{rule_id}")
            resp.raise_for_status()
            return ExecutionResult(success=True)

    async def list_route_policies(self) -> list[RoutePolicy]:
        async with self._client() as client:
            resp = await client.get("/rest/ip/route")
            resp.raise_for_status()
            result = []
            for r in resp.json():
                result.append(RoutePolicy(
                    rule_id=r.get(".id", ""),
                    name=r.get("comment", ""),
                    interface=r.get("gateway", ""),
                    source="any",
                    destination=r.get("dst-address", ""),
                    service="any",
                    gateway=r.get("gateway", ""),
                    metric=int(r.get("distance", 1)),
                    distance=int(r.get("distance", 1)),
                    route_type="static",
                    comment=r.get("comment", ""),
                    enabled=not r.get("disabled", False),
                    raw=r,
                ))
            return result

    async def create_route_policy(self, spec: RouteSpec) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.put("/rest/ip/route", json={
                "dst-address": spec.destination,
                "gateway": spec.gateway,
                "distance": spec.distance,
                "comment": spec.comment or "",
            })
            resp.raise_for_status()
            data = resp.json()
            return ExecutionResult(success=True, rule_id=data.get(".id"), raw_response=data)

    async def delete_route_policy(self, rule_id: str) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.delete(f"/rest/ip/route/{rule_id}")
            resp.raise_for_status()
            return ExecutionResult(success=True)

    # ── Security & Routing Status (P2 additions) ─────────────────────────────

    async def get_security_status(self) -> dict:
        """Return routing protocol status, VPN tunnels, and firewall stats."""
        result: dict = {}

        async with self._client() as client:
            # OSPF neighbors
            try:
                r = await client.get("/rest/routing/ospf/neighbor")
                if r.status_code == 200:
                    result["ospf_neighbors"] = r.json()
            except Exception:
                result["ospf_neighbors"] = []

            # BGP sessions (RouterOS 7.x uses /rest/routing/bgp/session)
            for bgp_path in ("/rest/routing/bgp/session", "/rest/routing/bgp/peer"):
                try:
                    r = await client.get(bgp_path)
                    if r.status_code == 200:
                        result["bgp_peers"] = r.json()
                        break
                except Exception:
                    pass
            if "bgp_peers" not in result:
                result["bgp_peers"] = []

            # IPSec active peers
            try:
                r = await client.get("/rest/ip/ipsec/active-peers")
                if r.status_code == 200:
                    result["ipsec_active_peers"] = r.json()
            except Exception:
                result["ipsec_active_peers"] = []

            # IPSec policies (configured tunnels)
            try:
                r = await client.get("/rest/ip/ipsec/policy")
                if r.status_code == 200:
                    result["ipsec_policies"] = r.json()
            except Exception:
                result["ipsec_policies"] = []

            # L7 protocol patterns (application control)
            try:
                r = await client.get("/rest/ip/firewall/layer7-protocol")
                if r.status_code == 200:
                    result["l7_protocols"] = r.json()
            except Exception:
                result["l7_protocols"] = []

            # Address lists
            try:
                r = await client.get("/rest/ip/firewall/address-list")
                if r.status_code == 200:
                    result["address_lists"] = r.json()
            except Exception:
                result["address_lists"] = []

            # System resources
            try:
                r = await client.get("/rest/system/resource")
                if r.status_code == 200:
                    result["system_resources"] = r.json()
            except Exception:
                result["system_resources"] = {}

        return result

    async def list_interfaces(self) -> list[dict]:
        """List IP addresses assigned to interfaces."""
        async with self._client() as client:
            resp = await client.get("/rest/ip/address")
            resp.raise_for_status()
            return resp.json()

    async def list_dhcp_leases(self) -> list[dict]:
        """List active DHCP server leases."""
        async with self._client() as client:
            resp = await client.get("/rest/ip/dhcp-server/lease")
            resp.raise_for_status()
            return resp.json()

    async def list_ospf_neighbors(self) -> list[dict]:
        """List active OSPF neighbors."""
        async with self._client() as client:
            resp = await client.get("/rest/routing/ospf/neighbor")
            resp.raise_for_status()
            return resp.json()

    async def list_bgp_peers(self) -> list[dict]:
        """List BGP peer sessions (RouterOS 7.x)."""
        async with self._client() as client:
            for path in ("/rest/routing/bgp/session", "/rest/routing/bgp/peer"):
                resp = await client.get(path)
                if resp.status_code == 200:
                    return resp.json()
            return []

    async def list_ipsec_policies(self) -> list[dict]:
        """List configured IPSec policies."""
        async with self._client() as client:
            resp = await client.get("/rest/ip/ipsec/policy")
            resp.raise_for_status()
            return resp.json()
