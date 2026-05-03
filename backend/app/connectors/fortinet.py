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

    # Built-in FortiOS service names — avoid creating custom objects for these
    _BUILTIN_SERVICES: dict[tuple[str, str], str] = {
        ("TCP", "80"): "HTTP", ("TCP", "443"): "HTTPS", ("TCP", "8443"): "HTTPS",
        ("TCP", "22"): "SSH", ("TCP", "21"): "FTP", ("TCP", "23"): "TELNET",
        ("TCP", "25"): "SMTP", ("TCP", "110"): "POP3", ("TCP", "143"): "IMAP",
        ("TCP", "993"): "IMAPS", ("TCP", "995"): "POP3S", ("TCP", "465"): "SMTPS",
        ("TCP", "3389"): "RDP", ("TCP", "3306"): "MYSQL", ("TCP", "1433"): "MS-SQL",
        ("TCP", "5432"): "HTTPS",  # no built-in for postgres
        ("UDP", "53"): "DNS", ("TCP", "53"): "DNS",
        ("UDP", "67"): "DHCP", ("UDP", "68"): "DHCP",
        ("UDP", "161"): "SNMP", ("UDP", "162"): "SNMP-TRAP",
        ("TCP", "514"): "SYSLOG", ("UDP", "514"): "SYSLOG",
        ("UDP", "123"): "NTP",
        ("TCP", "8080"): "HTTP",  # common alt-HTTP — FortiOS treats as HTTP
    }

    async def _ensure_service(self, client: httpx.AsyncClient, svc: str) -> str | None:
        """Return FortiGate service object name, creating custom one if needed.
        Returns None if the service cannot be created (permissions issue).
        Raises ValueError for invalid port numbers (out of 1-65535 range)."""
        if svc.upper() in ("ANY", "ALL", ""):
            return "ALL"
        parts = svc.upper().split("/")
        if len(parts) != 2:
            # Assume it's already an object name — use as-is
            return svc
        proto, port = parts

        # Validate port range before hitting the FortiOS API
        try:
            port_num = int(port)
        except ValueError:
            raise ValueError(f"Porta '{port}' não é um número válido no serviço '{svc}'.")
        if not (1 <= port_num <= 65535):
            raise ValueError(
                f"Porta {port_num} está fora do intervalo válido (1–65535). "
                f"Verifique se digitou corretamente — por exemplo, '{svc}' parece um typo."
            )

        # 1. Try built-in service first (no creation needed)
        builtin = self._BUILTIN_SERVICES.get((proto, port))
        if builtin:
            logger.info("Fortinet: using built-in service %s for %s", builtin, svc)
            return builtin

        # 2. Check if custom object already exists
        name = self._svc_obj_name(svc)
        check = await client.get(f"/api/v2/cmdb/firewall.service/custom/{name}?vdom={self.vdom}")
        if check.status_code == 200:
            logger.debug("Fortinet service object already exists: %s", name)
            return name

        # 3. Try to create custom service
        svc_payload: dict[str, Any] = {"name": name, "protocol": "TCP/UDP/SCTP"}
        if proto == "TCP":
            svc_payload["tcp-portrange"] = port
        elif proto == "UDP":
            svc_payload["udp-portrange"] = port
        else:
            svc_payload["tcp-portrange"] = port
        r = await client.post(f"/api/v2/cmdb/firewall.service/custom?vdom={self.vdom}", json=svc_payload)
        if r.status_code not in (200, 201):
            logger.error("Fortinet: cannot create service object %s (HTTP %s): %s", name, r.status_code, r.text)
            return None  # signal permissions failure
        logger.info("Fortinet: created service object %s", name)
        return name

    async def _resolve_interface(self, client: httpx.AsyncClient, name: str) -> str:
        """Resolve interface or zone name case-insensitively. Falls back to 'any'."""
        if not name or name.lower() == "any":
            return "any"
        # Try exact match on interface
        r = await client.get(f"/api/v2/cmdb/system/interface/{name}?vdom={self.vdom}")
        if r.status_code == 200:
            return name
        # Case-insensitive scan of all interfaces
        r = await client.get(f"/api/v2/cmdb/system/interface?vdom={self.vdom}&format=name")
        if r.status_code == 200:
            for intf in r.json().get("results", []):
                if intf.get("name", "").lower() == name.lower():
                    logger.info("Fortinet: resolved interface '%s' → '%s'", name, intf["name"])
                    return intf["name"]
        # Case-insensitive scan of zones
        r = await client.get(f"/api/v2/cmdb/system/zone?vdom={self.vdom}&format=name")
        if r.status_code == 200:
            for zone in r.json().get("results", []):
                if zone.get("name", "").lower() == name.lower():
                    logger.info("Fortinet: resolved zone '%s' → '%s'", name, zone["name"])
                    return zone["name"]
        logger.warning("Fortinet: interface/zone '%s' not found on device, using 'any'", name)
        return "any"

    # ── Rules ────────────────────────────────────────────────────────────────

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        async with self._client() as client:
            src_name = await self._ensure_address(client, spec.src_address)
            dst_name = await self._ensure_address(client, spec.dst_address)
            try:
                svc_name = await self._ensure_service(client, spec.service)
            except ValueError as exc:
                return ExecutionResult(success=False, error=str(exc))
            if svc_name is None:
                return ExecutionResult(
                    success=False,
                    error=(
                        f"Não foi possível criar o objeto de serviço para '{spec.service}'. "
                        "Verifique se o token da API tem permissão Read-Write em Firewall. "
                        "No FortiGate: System > Administrators > edite o REST API Admin > "
                        "selecione um perfil com acesso a 'Firewall'."
                    ),
                )

            # Resolve interface/zone names — FortiOS is case-sensitive
            src_intf = await self._resolve_interface(client, spec.src_zone or "any")
            dst_intf = await self._resolve_interface(client, spec.dst_zone or "any")

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
                "schedule": "always",
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
        async with self._client() as client:
            src_name = await self._ensure_address(client, spec.src_address)
            dst_name = await self._ensure_address(client, spec.dst_address)
            try:
                svc_name = await self._ensure_service(client, spec.service)
            except ValueError as exc:
                return ExecutionResult(success=False, error=str(exc))
            if svc_name is None:
                return ExecutionResult(
                    success=False,
                    error=f"Não foi possível resolver o serviço '{spec.service}'.",
                )
            src_intf = await self._resolve_interface(client, spec.src_zone or "any")
            dst_intf = await self._resolve_interface(client, spec.dst_zone or "any")
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
                "schedule": "always",
                "comments": spec.comment or "",
            }
            for k, v in spec.extra.items():
                if k in _VALID_EXTRA:
                    payload[k] = v
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

    # ── Statistics & Security Status ─────────────────────────────────────────

    async def get_rule_statistics(self) -> dict[str, int]:
        """Return {policy_id: hit_count} from the FortiOS monitor endpoint."""
        stats: dict[str, int] = {}
        try:
            async with self._client() as client:
                resp = await client.get(f"/api/v2/monitor/firewall/policy?vdom={self.vdom}")
                if resp.status_code != 200:
                    return stats
                for entry in resp.json().get("results", []):
                    pid = str(entry.get("policyid", ""))
                    count = int(entry.get("hit_count", 0) or 0)
                    if pid:
                        stats[pid] = count
        except Exception:
            pass
        return stats

    async def get_security_status(self) -> dict:
        """Collect security service profiles and VPN tunnel status."""
        result: dict[str, Any] = {}

        _profile_endpoints: list[tuple[str, str]] = [
            (f"/api/v2/cmdb/antivirus/profile?vdom={self.vdom}&format=name,scan-mode,http,ftp",
             "av_profiles"),
            (f"/api/v2/cmdb/ips/sensor?vdom={self.vdom}&format=name,comment",
             "ips_sensors"),
            (f"/api/v2/cmdb/webfilter/profile?vdom={self.vdom}&format=name,comment",
             "webfilter_profiles"),
            (f"/api/v2/cmdb/application/list?vdom={self.vdom}&format=name,comment",
             "app_control_lists"),
            (f"/api/v2/cmdb/firewall/ssl-ssh-profile?vdom={self.vdom}&format=name,comment,ssl",
             "ssl_profiles"),
            (f"/api/v2/cmdb/dnsfilter/profile?vdom={self.vdom}&format=name,comment",
             "dns_filter_profiles"),
        ]

        async with self._client() as client:
            # ── Configuration profiles ────────────────────────────────────────
            for url, key in _profile_endpoints:
                try:
                    r = await client.get(url)
                    if r.status_code == 200:
                        result[key] = r.json().get("results", [])
                except Exception:
                    result[key] = []

            # ── Geo-IP blocked countries (address objects of type geography) ──
            try:
                r = await client.get(
                    f"/api/v2/cmdb/firewall/address?vdom={self.vdom}"
                    f"&filter=type==geography&format=name,country"
                )
                if r.status_code == 200:
                    result["geo_blocked"] = r.json().get("results", [])
            except Exception:
                result["geo_blocked"] = []

            # ── VPN IPSec tunnel status (monitor, live data) ──────────────────
            try:
                r = await client.get(f"/api/v2/monitor/vpn/ipsec?vdom={self.vdom}")
                if r.status_code == 200:
                    result["vpn_ipsec"] = r.json().get("results", [])
            except Exception:
                result["vpn_ipsec"] = []

            # ── VPN SSL active sessions ───────────────────────────────────────
            try:
                r = await client.get(f"/api/v2/monitor/vpn/ssl?vdom={self.vdom}")
                if r.status_code == 200:
                    result["vpn_ssl_sessions"] = r.json().get("results", [])
            except Exception:
                result["vpn_ssl_sessions"] = []

            # ── VPN IPSec tunnel config (configured tunnels, not just active) ─
            try:
                r = await client.get(
                    f"/api/v2/cmdb/vpn.ipsec/phase1-interface?vdom={self.vdom}"
                    f"&format=name,status,remote-gw,comments"
                )
                if r.status_code == 200:
                    result["vpn_ipsec_config"] = r.json().get("results", [])
            except Exception:
                result["vpn_ipsec_config"] = []

        return result
