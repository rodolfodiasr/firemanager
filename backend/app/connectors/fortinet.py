"""Fortinet FortiOS 7.x REST API connector."""
import ipaddress
import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

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
        if not self.token or not self.token.strip():
            return ConnectionResult(success=False, error="API Token não configurado. Edite o dispositivo e informe o token.")
        start = time.monotonic()
        try:
            async with self._client() as client:
                resp = await client.get(f"/api/v2/cmdb/system/status?vdom={self.vdom}")
                if resp.status_code == 401:
                    return ConnectionResult(success=False, error="Token inválido ou sem permissão (HTTP 401). Verifique o token em System > Admin > REST API Admin.")
                if resp.status_code == 403:
                    return ConnectionResult(success=False, error="Acesso negado (HTTP 403). O token não tem permissão suficiente ou o VDOM está incorreto.")
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

    # ── Object helpers ───────────────────────────────────────────────────────

    def _addr_obj_name(self, addr: str) -> str:
        return f"FM-{addr.replace('/', '-').replace('.', '-').replace(':', '-')}"

    def _svc_obj_name(self, svc: str) -> str:
        return f"FM-{svc.replace('/', '-').upper()}"

    async def _ensure_address(self, client: httpx.AsyncClient, addr: str) -> str:
        """Return existing FortiGate address object name, creating it if needed."""
        if addr.lower() in ("any", "all", ""):
            return "all"
        name = self._addr_obj_name(addr)
        check = await client.get(f"/api/v2/cmdb/firewall/address/{name}?vdom={self.vdom}")
        if check.status_code == 200:
            logger.debug("Fortinet address object already exists: %s", name)
            return name
        if "/" in addr:
            net = ipaddress.ip_network(addr, strict=False)
            subnet = f"{net.network_address} {net.netmask}"
        else:
            subnet = f"{addr} 255.255.255.255"
        r = await client.post(
            f"/api/v2/cmdb/firewall/address?vdom={self.vdom}",
            json={"name": name, "type": "ipmask", "subnet": subnet},
        )
        if r.status_code not in (200, 201):
            logger.warning("Fortinet: failed to create address object %s: %s", name, r.text)
        else:
            logger.info("Fortinet: created address object %s (%s)", name, subnet)
        return name

    async def _ensure_service(self, client: httpx.AsyncClient, svc: str) -> str:
        """Return existing FortiGate service object name, creating it if needed."""
        if svc.upper() in ("ANY", "ALL", ""):
            return "ALL"
        # If it doesn't look like "PROTO/PORT" assume it's already an object name
        parts = svc.upper().split("/")
        if len(parts) != 2:
            return svc
        proto, port = parts
        name = self._svc_obj_name(svc)
        check = await client.get(f"/api/v2/cmdb/firewall.service/custom/{name}?vdom={self.vdom}")
        if check.status_code == 200:
            logger.debug("Fortinet service object already exists: %s", name)
            return name
        svc_payload: dict[str, Any] = {"name": name, "protocol": "TCP/UDP/SCTP"}
        if proto == "TCP":
            svc_payload["tcp-portrange"] = port
        elif proto == "UDP":
            svc_payload["udp-portrange"] = port
        else:
            svc_payload["tcp-portrange"] = port
        r = await client.post(f"/api/v2/cmdb/firewall.service/custom?vdom={self.vdom}", json=svc_payload)
        if r.status_code not in (200, 201):
            logger.warning("Fortinet: failed to create service object %s: %s", name, r.text)
        else:
            logger.info("Fortinet: created service object %s", name)
        return name

    # ── Rules ────────────────────────────────────────────────────────────────

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        async with self._client() as client:
            src_name = await self._ensure_address(client, spec.src_address)
            dst_name = await self._ensure_address(client, spec.dst_address)
            svc_name = await self._ensure_service(client, spec.service)

            # Use zones from spec; FortiOS accepts interface or zone names
            src_intf = spec.src_zone if spec.src_zone else "any"
            dst_intf = spec.dst_zone if spec.dst_zone else "any"

            # Only pass known FortiOS policy fields from extra (avoid injecting invalid keys)
            _VALID_EXTRA = {"nat", "logtraffic", "schedule", "utm-status", "inspection-mode",
                            "profile-protocol-options", "ssl-ssh-profile", "av-profile",
                            "webfilter-profile", "ips-sensor", "application-list"}
            payload: dict[str, Any] = {
                "name": spec.name,
                "srcintf": [{"name": src_intf}],
                "dstintf": [{"name": dst_intf}],
                "srcaddr": [{"name": src_name}],
                "dstaddr": [{"name": dst_name}],
                "service": [{"name": svc_name}],
                "action": spec.action,
                "status": "enable",
                "comments": spec.comment or "",
            }
            for k, v in spec.extra.items():
                if k in _VALID_EXTRA:
                    payload[k] = v

            logger.info("Fortinet create_rule payload: %s", json.dumps(payload))
            resp = await client.post(
                f"/api/v2/cmdb/firewall/policy?vdom={self.vdom}", json=payload
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                rule_id = str(data.get("mkey", ""))
                return ExecutionResult(success=True, rule_id=rule_id, raw_response=data)
            logger.error("Fortinet create_rule failed %s: %s", resp.status_code, resp.text)
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

    # ── NAT (VIP — Virtual IP objects) ──────────────────────────────────────

    async def list_nat_policies(self) -> list[NatPolicy]:
        async with self._client() as client:
            resp = await client.get(f"/api/v2/cmdb/firewall/vip?vdom={self.vdom}")
            resp.raise_for_status()
            policies = []
            for r in resp.json().get("results", []):
                extip = r.get("extip", "")
                mappedip = r.get("mappedip", [{}])
                mapped = mappedip[0].get("range", "") if mappedip else ""
                policies.append(NatPolicy(
                    rule_id=str(r.get("mkey", r.get("name", ""))),
                    name=r.get("name", ""),
                    inbound=r.get("extintf", "any"),
                    outbound="any",
                    source="Any",
                    translated_source="Original",
                    destination=extip,
                    translated_destination=mapped,
                    service=str(r.get("service", [{}])[0].get("name", "Any")) if r.get("service") else "Any",
                    translated_service="Original",
                    enabled=r.get("status", "enable") == "enable",
                    comment=r.get("comment", ""),
                    raw=r,
                ))
            return policies

    async def create_nat_policy(self, spec: NatSpec) -> ExecutionResult:
        # FortiGate VIP = DNAT (external IP → mapped internal IP)
        payload: dict[str, Any] = {
            "name": spec.name,
            "extintf": spec.inbound_interface,
            "extip": spec.destination,
            "mappedip": [{"range": spec.translated_destination}],
            "comment": spec.comment or "",
        }
        async with self._client() as client:
            resp = await client.post(
                f"/api/v2/cmdb/firewall/vip?vdom={self.vdom}", json=payload
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                return ExecutionResult(success=True, rule_id=spec.name, raw_response=data)
            return ExecutionResult(success=False, error=resp.text)

    async def delete_nat_policy(self, rule_id: str) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.delete(
                f"/api/v2/cmdb/firewall/vip/{rule_id}?vdom={self.vdom}"
            )
            if resp.status_code in (200, 204):
                return ExecutionResult(success=True, rule_id=rule_id)
            return ExecutionResult(success=False, error=resp.text)

    # ── Routes (static routes) ───────────────────────────────────────────────

    async def list_route_policies(self) -> list[RoutePolicy]:
        async with self._client() as client:
            resp = await client.get(f"/api/v2/cmdb/router/static?vdom={self.vdom}")
            resp.raise_for_status()
            routes = []
            for r in resp.json().get("results", []):
                routes.append(RoutePolicy(
                    rule_id=str(r.get("seq-num", "")),
                    name=r.get("comment", ""),
                    interface=r.get("device", ""),
                    source="Any",
                    destination=r.get("dst", "Any"),
                    service="Any",
                    gateway=r.get("gateway", ""),
                    metric=int(r.get("priority", 20)),
                    distance=int(r.get("distance", 20)),
                    route_type="static",
                    comment=r.get("comment", ""),
                    enabled=r.get("status", "enable") == "enable",
                    raw=r,
                ))
            return routes

    async def create_route_policy(self, spec: RouteSpec) -> ExecutionResult:
        payload: dict[str, Any] = {
            "dst": spec.destination if spec.destination != "Any" else "0.0.0.0 0.0.0.0",
            "gateway": spec.gateway,
            "device": spec.interface,
            "priority": spec.metric,
            "distance": spec.distance,
            "comment": spec.comment or spec.name,
            "status": "enable",
        }
        async with self._client() as client:
            resp = await client.post(
                f"/api/v2/cmdb/router/static?vdom={self.vdom}", json=payload
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                rule_id = str(data.get("mkey", ""))
                return ExecutionResult(success=True, rule_id=rule_id, raw_response=data)
            return ExecutionResult(success=False, error=resp.text)

    async def delete_route_policy(self, rule_id: str) -> ExecutionResult:
        async with self._client() as client:
            resp = await client.delete(
                f"/api/v2/cmdb/router/static/{rule_id}?vdom={self.vdom}"
            )
            if resp.status_code in (200, 204):
                return ExecutionResult(success=True, rule_id=rule_id)
            return ExecutionResult(success=False, error=resp.text)
