"""SonicWall SonicOS 6/7/8 REST API connector."""
import contextlib
import ipaddress
import json
import logging
import re
import time
from typing import Any, AsyncGenerator

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


class SonicWallConnector(BaseConnector):
    """SonicOS 6.5/7.x/8.x REST API connector.

    Auth: POST /api/sonicos/auth with Digest Auth → session cookie.
    Version auto-detected from stored firmware string:
      6.x → flat-array payload format, string action/zones
      7.x → {"ipv4":[...]} wrapper, object action/zones
    create_rule auto-creates address objects and service objects when
    raw IPs or port specs are passed (SonicWall requires named objects).
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        os_version: int = 7,
        verify_ssl: bool = False,
        known_firmware: str | None = None,
    ) -> None:
        self.base_url = host.rstrip("/")
        self.username = username
        self.password = password
        self.os_version = os_version
        self.verify_ssl = verify_ssl
        self._v6: bool | None = self._detect_v6_from_firmware(known_firmware)

    # ------------------------------------------------------------------
    # Version detection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_v6_from_firmware(firmware: str | None) -> bool | None:
        """Return True for SonicOS 6.x, False for 7.x/8.x, None if unknown."""
        if not firmware or firmware in ("unknown", ""):
            return None
        m = re.search(r"(\d+)\.\d+", firmware)
        if m:
            return int(m.group(1)) <= 6
        return None

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    @contextlib.asynccontextmanager
    async def _session(self) -> AsyncGenerator[httpx.AsyncClient, None]:
        """Authenticate via Digest Auth and yield an authenticated client."""
        async with httpx.AsyncClient(
            base_url=self.base_url,
            verify=self.verify_ssl,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=30.0,
        ) as client:
            resp = await client.post(
                "/api/sonicos/auth",
                json={"override": True},
                auth=httpx.DigestAuth(self.username, self.password),
            )
            if not resp.is_success:
                raise Exception(
                    f"SonicWall auth failed: HTTP {resp.status_code} — {resp.text[:200]}"
                )

            # Fallback: both SonicOS 6 and 7 return config_mode in auth, so use os_version hint
            if self._v6 is None:
                self._v6 = (self.os_version <= 6)

            try:
                yield client
            finally:
                try:
                    await client.delete("/api/sonicos/auth")
                except Exception:
                    pass

    async def _commit(self, client: httpx.AsyncClient) -> None:
        # Both v6 and v7 require POST /config/pending to persist staged changes
        await client.post("/api/sonicos/config/pending")

    @contextlib.asynccontextmanager
    async def hold_session(self) -> AsyncGenerator[None, None]:
        """Open a regular (non-override) API session without committing.

        Creates a preemptable 'admin at SonicOS API is editing' state so that
        SSH 'configure' shows the yes/no preempt dialog instead of requiring
        a separate enable password. Intentionally does NOT use override=True,
        which would create a privileged lock that SSH cannot preempt normally.
        """
        async with httpx.AsyncClient(
            base_url=self.base_url,
            verify=self.verify_ssl,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=30.0,
        ) as client:
            # No {"override": True} — regular session that SSH can preempt with 'yes'
            resp = await client.post(
                "/api/sonicos/auth",
                auth=httpx.DigestAuth(self.username, self.password),
            )
            if not resp.is_success:
                logger.debug("hold_session: auth returned HTTP %s", resp.status_code)
            try:
                yield
            finally:
                try:
                    await client.delete("/api/sonicos/auth")
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Firmware retrieval
    # ------------------------------------------------------------------

    async def _fetch_firmware(self, client: httpx.AsyncClient) -> str:
        candidates = [
            ("/api/sonicos/version", lambda d: d.get("firmware_version")),
            ("/api/sonicos/device", lambda d: (
                d.get("device", {}).get("firmware_version") or d.get("firmware_version")
            )),
        ]
        for path, extractor in candidates:
            try:
                r = await client.get(path)
                if r.status_code == 200:
                    val = extractor(r.json())
                    if val:
                        return str(val)
            except Exception:
                continue
        return "unknown"

    # ------------------------------------------------------------------
    # Address / service object helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _obj_name_for_ip(ip_str: str) -> str | None:
        """Return a deterministic object name if ip_str is a valid IP/CIDR, else None."""
        try:
            ipaddress.ip_network(ip_str, strict=False)
            return "fm-" + ip_str.replace("/", "_").replace(".", "-")
        except ValueError:
            return None  # already a named object

    @staticmethod
    def _decode_fm_name(name: str) -> str | None:
        """If name follows fm- convention, extract and return the original IP/CIDR, else None."""
        if not name.startswith("fm-"):
            return None
        body = name[3:]  # strip "fm-"
        ip_str = body.replace("_", "/").replace("-", ".")
        try:
            ipaddress.ip_network(ip_str, strict=False)
            return ip_str
        except ValueError:
            return None

    @staticmethod
    def _parse_port_spec(service: str) -> tuple[str, int, int] | None:
        """Parse 'TCP/1060' or 'UDP/53' → (proto, begin, end) or None."""
        m = re.match(r"^(TCP|UDP)/(\d+)(?:-(\d+))?$", service, re.IGNORECASE)
        if m:
            proto = m.group(1).upper()
            begin = int(m.group(2))
            end = int(m.group(3)) if m.group(3) else begin
            return proto, begin, end
        return None

    async def _ensure_address_object(
        self, client: httpx.AsyncClient, ip_str: str, zone: str
    ) -> str:
        """Create a host/network address object if ip_str is an IP or fm- name. Returns object name."""
        obj_name = self._obj_name_for_ip(ip_str)
        if obj_name is None:
            # Check if it's an fm- encoded name — decode and (re)create the object
            decoded = self._decode_fm_name(ip_str)
            if decoded:
                ip_str = decoded
                obj_name = self._obj_name_for_ip(decoded)
            if obj_name is None:
                return ip_str  # truly a pre-existing named object

        net = ipaddress.ip_network(ip_str, strict=False)
        is_host = net.prefixlen == (32 if net.version == 4 else 128)

        if is_host:
            addr_body: dict[str, Any] = {"host": {"ip": str(net.network_address)}}
        else:
            addr_body = {"network": {"subnet": str(net.network_address), "mask": str(net.netmask)}}

        if self._v6:
            payload: dict[str, Any] = {
                "address_objects": [{"name": obj_name, "zone": zone, **addr_body}]
            }
        else:
            # v7/v8: each entry wrapped in {"ipv4": {...}} — mirrors GET response format
            payload = {
                "address_objects": [{"ipv4": {"name": obj_name, "zone": zone, **addr_body}}]
            }

        r = await client.post("/api/sonicos/address-objects/ipv4", json=payload)
        if r.is_success:
            await self._commit(client)
        elif r.status_code == 400 and "already exists" in r.text.lower():
            logger.debug("address-object %s already exists, reusing", obj_name)
        else:
            logger.warning(
                "address-object create for %s: HTTP %s — %s", ip_str, r.status_code, r.text[:300]
            )
        return obj_name

    async def _ensure_service_object(
        self, client: httpx.AsyncClient, service: str
    ) -> str:
        """Create a service object for TCP/PORT or UDP/PORT specs. Returns object name."""
        parsed = self._parse_port_spec(service)
        if parsed is None:
            return service  # already named

        proto, begin, end = parsed
        svc_name = (
            f"fm-{proto.lower()}-{begin}"
            if begin == end
            else f"fm-{proto.lower()}-{begin}-{end}"
        )
        proto_key = proto.lower()
        # SonicOS: protocol key directly on the entry; port range flat (not nested under "port")
        payload = {
            "service_objects": [
                {
                    "name": svc_name,
                    proto_key: {"begin": begin, "end": end},
                }
            ]
        }
        r = await client.post("/api/sonicos/service-objects", json=payload)
        if r.is_success:
            await self._commit(client)
        elif r.status_code == 400 and "already exists" in r.text.lower():
            logger.debug("service-object %s already exists, reusing", svc_name)
        else:
            logger.warning(
                "service-object create for %s: HTTP %s — %s", service, r.status_code, r.text[:300]
            )
        return svc_name

    # ------------------------------------------------------------------
    # Rule payload builder
    # ------------------------------------------------------------------

    _ACTION_MAP = {"accept": "allow", "permit": "allow", "drop": "discard", "reject": "deny"}

    def _normalize_action(self, action: str) -> str:
        return self._ACTION_MAP.get(action.lower(), action.lower())

    def _rule_payload(
        self, spec: RuleSpec, src_name: str, dst_name: str, svc_name: str
    ) -> dict[str, Any]:
        action = self._normalize_action(spec.action)
        rule_body: dict[str, Any] = {
            "name": spec.name,
            "enable": True,
            "action": action,
            "from": spec.src_zone,
            "to": spec.dst_zone,
            "source": {"address": {"name": src_name}},
            "destination": {"address": {"name": dst_name}},
            "service": {"name": svc_name},
            "comment": spec.comment or "",
        }
        if self._v6:
            return {"access_rules": [rule_body]}
        # v7/v8: per-entry {"ipv4": {...}} wrapper
        return {
            "access_rules": [{"ipv4": rule_body}]
        }

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    async def test_connection(self) -> ConnectionResult:
        start = time.monotonic()
        try:
            async with self._session() as client:
                resp = await client.get("/api/sonicos/access-rules/ipv4")
                if resp.status_code == 401:
                    return ConnectionResult(success=False, error="Session rejected (401)")
                resp.raise_for_status()
                latency = (time.monotonic() - start) * 1000
                firmware = await self._fetch_firmware(client)
                if firmware != "unknown":
                    self._v6 = self._detect_v6_from_firmware(firmware)
                return ConnectionResult(success=True, latency_ms=latency, firmware_version=firmware)
        except Exception as exc:
            return ConnectionResult(success=False, error=str(exc))

    def _parse_rules(self, data: dict) -> list[FirewallRule]:
        logger.debug("SonicWall raw access-rules: %s", json.dumps(data)[:600])
        access_rules = data.get("access_rules", {})
        if isinstance(access_rules, dict):
            raw_list = access_rules.get("ipv4", [])
        elif isinstance(access_rules, list):
            # v7 format: [{"ipv4": {...}}, ...] — each entry is a dict with ipv4 wrapper
            raw_list = []
            for item in access_rules:
                if isinstance(item, dict):
                    raw_list.append(item["ipv4"]) if "ipv4" in item else raw_list.append(item)
        else:
            raw_list = []

        rules = []
        for r in raw_list:
            if not isinstance(r, dict):
                continue
            action = r.get("action", "allow")
            if isinstance(action, dict):
                action = action.get("action", "allow")

            src_zone = r.get("from", "")
            if isinstance(src_zone, dict):
                src_zone = src_zone.get("name", "")

            dst_zone = r.get("to", "")
            if isinstance(dst_zone, dict):
                dst_zone = dst_zone.get("name", "")

            rules.append(
                FirewallRule(
                    rule_id=str(r.get("rule_id", r.get("uuid", ""))),
                    name=r.get("name", ""),
                    src=r.get("source", {}).get("address", {}).get("name", "Any"),
                    dst=r.get("destination", {}).get("address", {}).get("name", "Any"),
                    service=r.get("service", {}).get("name", "Any"),
                    action=action,
                    enabled=r.get("enable", True),
                    src_zone=src_zone,
                    dst_zone=dst_zone,
                    raw=r,
                )
            )
        return rules

    async def list_rules(self) -> list[FirewallRule]:
        async with self._session() as client:
            resp = await client.get("/api/sonicos/access-rules/ipv4")
            resp.raise_for_status()
            return self._parse_rules(resp.json())

    async def get_rule_statistics(self) -> dict[str, int]:
        """Fetch hit counts per rule UUID from the SonicWall statistics endpoint."""
        stats: dict[str, int] = {}
        try:
            async with self._session() as client:
                resp = await client.get("/api/sonicos/access-rules/ipv4/statistics")
                if resp.status_code != 200:
                    return stats
                data = resp.json()

                # Gen7: {"access_rules": [{"ipv4": {"uuid": ..., "packets": ...}}, ...]}
                raw_list = []
                ar = data.get("access_rules", data)
                if isinstance(ar, dict):
                    raw_list = ar.get("ipv4", [])
                elif isinstance(ar, list):
                    for item in ar:
                        if isinstance(item, dict):
                            raw_list.append(item.get("ipv4", item))

                for entry in raw_list:
                    if not isinstance(entry, dict):
                        continue
                    uid = str(entry.get("uuid", entry.get("rule_id", "")))
                    # Try common field names for hit/packet count
                    count = (
                        entry.get("hit_count")
                        or entry.get("packets")
                        or entry.get("packet_count")
                        or entry.get("connections")
                        or 0
                    )
                    if uid:
                        stats[uid] = int(count)
        except Exception:
            pass
        return stats

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        async with self._session() as client:
            src_name = await self._ensure_address_object(client, spec.src_address, spec.src_zone)
            dst_name = await self._ensure_address_object(client, spec.dst_address, spec.dst_zone)
            svc_name = await self._ensure_service_object(client, spec.service)

            payload = self._rule_payload(spec, src_name, dst_name, svc_name)
            resp = await client.post("/api/sonicos/access-rules/ipv4", json=payload)
            await self._commit(client)
            if resp.status_code in (200, 201):
                return ExecutionResult(success=True, raw_response=resp.json())
            return ExecutionResult(success=False, error=resp.text)

    async def create_group(self, spec: GroupSpec) -> ExecutionResult:
        if self._v6:
            payload: dict[str, Any] = {
                "address_groups": [
                    {"name": spec.name, "address_objects": [{"name": m} for m in spec.members]}
                ]
            }
        else:
            payload = {
                "address_groups": {
                    "ipv4": [
                        {"name": spec.name, "address_objects": [{"name": m} for m in spec.members]}
                    ]
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
        async with self._session() as client:
            src_name = await self._ensure_address_object(client, spec.src_address, spec.src_zone)
            dst_name = await self._ensure_address_object(client, spec.dst_address, spec.dst_zone)
            svc_name = await self._ensure_service_object(client, spec.service)
            payload = self._rule_payload(spec, src_name, dst_name, svc_name)
            resp = await client.put(
                f"/api/sonicos/access-rules/ipv4/uuid/{rule_id}", json=payload
            )
            await self._commit(client)
            if resp.status_code in (200, 204):
                return ExecutionResult(success=True, rule_id=rule_id)
            return ExecutionResult(success=False, error=resp.text)

    async def get_config_snapshot(self) -> str:
        async with self._session() as client:
            resp = await client.get("/api/sonicos/access-rules/ipv4")
            resp.raise_for_status()
            return json.dumps(resp.json(), indent=2)

    # ------------------------------------------------------------------
    # NAT Policies
    # ------------------------------------------------------------------

    @staticmethod
    def _addr_field(value: str) -> dict:
        if value.lower() in ("any", ""):
            return {"any": True}
        return {"name": value}

    @staticmethod
    def _translated_field(value: str) -> dict:
        if value.lower() in ("original", ""):
            return {"original": True}
        return {"name": value}

    def _parse_nat_addr(self, field: dict) -> str:
        if field.get("any"):
            return "Any"
        if field.get("original"):
            return "Original"
        return field.get("name") or field.get("group") or "Any"

    def _parse_nat_policies(self, data: dict) -> list[NatPolicy]:
        raw_list = data.get("nat_policies", [])
        policies = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            r = item.get("ipv4", item)
            policies.append(
                NatPolicy(
                    rule_id=str(r.get("uuid", "")),
                    name=r.get("name", ""),
                    inbound=r.get("inbound", ""),
                    outbound=r.get("outbound", ""),
                    source=self._parse_nat_addr(r.get("source", {})),
                    translated_source=self._parse_nat_addr(r.get("translated_source", {})),
                    destination=self._parse_nat_addr(r.get("destination", {})),
                    translated_destination=self._parse_nat_addr(r.get("translated_destination", {})),
                    service=self._parse_nat_addr(r.get("service", {})),
                    translated_service=self._parse_nat_addr(r.get("translated_service", {})),
                    enabled=r.get("enable", True),
                    comment=r.get("comment", ""),
                    raw=r,
                )
            )
        return policies

    async def list_nat_policies(self) -> list[NatPolicy]:
        async with self._session() as client:
            resp = await client.get("/api/sonicos/nat-policies/ipv4")
            resp.raise_for_status()
            return self._parse_nat_policies(resp.json())

    def _nat_payload(self, spec: NatSpec) -> dict:
        body = {
            "name": spec.name,
            "inbound": spec.inbound_interface,
            "outbound": spec.outbound_interface,
            "source": self._addr_field(spec.source),
            "translated_source": self._translated_field(spec.translated_source),
            "destination": self._addr_field(spec.destination),
            "translated_destination": self._translated_field(spec.translated_destination),
            "service": self._addr_field(spec.service),
            "translated_service": self._translated_field(spec.translated_service),
            "enable": spec.enable,
            "priority": {"auto": True},
            "comment": spec.comment or "",
        }
        return {"nat_policies": [{"ipv4": body}]}

    async def _resolve_nat_addr(self, client: httpx.AsyncClient, value: str, zone: str) -> str:
        """Return address object name, creating one if value is a raw IP/CIDR."""
        if not value or value.lower() in ("any", "original", ""):
            return value
        # Direct IP/CIDR
        if self._obj_name_for_ip(value):
            return await self._ensure_address_object(client, value, zone)
        # Fallback: extract embedded IP from LLM-invented names like "OBJ-192.168.1.1"
        m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?)", value)
        if m:
            extracted = m.group(1)
            if self._obj_name_for_ip(extracted):
                return await self._ensure_address_object(client, extracted, zone)
        return value

    async def _resolve_nat_service(self, client: httpx.AsyncClient, value: str) -> str:
        """Return service object name, creating one if value is a port spec like TCP/8080."""
        if not value or value.lower() in ("any", "original", ""):
            return value
        if self._parse_port_spec(value):
            return await self._ensure_service_object(client, value)
        return value

    async def create_nat_policy(self, spec: NatSpec) -> ExecutionResult:
        async with self._session() as client:
            inbound_zone = "WAN"
            outbound_zone = "LAN"

            src = await self._resolve_nat_addr(client, spec.source, inbound_zone)
            t_src = await self._resolve_nat_addr(client, spec.translated_source, outbound_zone)
            dst = await self._resolve_nat_addr(client, spec.destination, inbound_zone)
            t_dst = await self._resolve_nat_addr(client, spec.translated_destination, outbound_zone)
            svc = await self._resolve_nat_service(client, spec.service)
            t_svc = await self._resolve_nat_service(client, spec.translated_service)

            resolved = NatSpec(
                name=spec.name,
                inbound_interface=spec.inbound_interface,
                outbound_interface=spec.outbound_interface,
                source=src,
                translated_source=t_src,
                destination=dst,
                translated_destination=t_dst,
                service=svc,
                translated_service=t_svc,
                comment=spec.comment,
                enable=spec.enable,
            )
            payload = self._nat_payload(resolved)
            resp = await client.post("/api/sonicos/nat-policies/ipv4", json=payload)
            await self._commit(client)
            if resp.status_code in (200, 201):
                return ExecutionResult(success=True, raw_response=resp.json())
            return ExecutionResult(success=False, error=resp.text)

    async def delete_nat_policy(self, rule_id: str) -> ExecutionResult:
        async with self._session() as client:
            resp = await client.delete(f"/api/sonicos/nat-policies/ipv4/uuid/{rule_id}")
            await self._commit(client)
            if resp.status_code in (200, 204):
                return ExecutionResult(success=True, rule_id=rule_id)
            return ExecutionResult(success=False, error=resp.text)

    # ------------------------------------------------------------------
    # Route Policies
    # ------------------------------------------------------------------

    def _parse_route_policies(self, data: dict) -> list[RoutePolicy]:
        raw_list = data.get("route_policies", [])
        policies = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            r = item.get("ipv4", item)
            gw = r.get("gateway", {})
            if gw.get("default"):
                gateway = "default"
            else:
                gateway = gw.get("ip", "default")
            policies.append(
                RoutePolicy(
                    rule_id=str(r.get("uuid", "")),
                    name=r.get("name", ""),
                    interface=r.get("interface", ""),
                    source=self._parse_nat_addr(r.get("source", {})),
                    destination=self._parse_nat_addr(r.get("destination", {})),
                    service=self._parse_nat_addr(r.get("service", {})),
                    gateway=gateway,
                    metric=r.get("metric", 20),
                    distance=r.get("distance", {}).get("value", 20),
                    route_type=r.get("type", "standard"),
                    comment=r.get("comment", ""),
                    enabled=not r.get("disable_on_interface_down", False),
                    raw=r,
                )
            )
        return policies

    async def list_route_policies(self) -> list[RoutePolicy]:
        async with self._session() as client:
            resp = await client.get("/api/sonicos/route-policies/ipv4")
            resp.raise_for_status()
            return self._parse_route_policies(resp.json())

    async def create_route_policy(self, spec: RouteSpec) -> ExecutionResult:
        async with self._session() as client:
            iface_upper = spec.interface.upper()
            iface_zone = "WAN" if iface_upper == "X1" else "LAN"

            # Auto-create address object for destination CIDR
            dst_name = spec.destination
            if self._obj_name_for_ip(spec.destination):
                dst_name = await self._ensure_address_object(client, spec.destination, iface_zone)
            dst_field = self._addr_field(dst_name)

            # Auto-create address object for source CIDR
            src_name = spec.source
            if self._obj_name_for_ip(spec.source):
                src_name = await self._ensure_address_object(client, spec.source, "LAN")
            src_field = self._addr_field(src_name)

            # Gateway: default or named address object (SonicOS requires named object, not raw IP)
            gw = spec.gateway
            if not gw or gw.lower() in ("default", "any", ""):
                gw_field: dict = {"default": True}
            else:
                # Auto-create host address object for the gateway IP
                gw_obj = self._obj_name_for_ip(gw)
                if gw_obj:
                    await self._ensure_address_object(client, gw, iface_zone)
                    gw_field = {"name": gw_obj}
                else:
                    gw_field = {"name": gw}

            body: dict = {
                "interface": spec.interface,
                "source": src_field,
                "destination": dst_field,
                "service": self._addr_field(spec.service),
                "gateway": gw_field,
                "metric": spec.metric,
                "distance": {"value": spec.distance},
                "name": spec.name,
                "type": spec.route_type,
                "comment": spec.comment or "",
                "disable_on_interface_down": spec.disable_on_interface_down,
                "vpn_precedence": False,
                "tcp_acceleration": False,
                "probe": "",
            }
            payload = {"route_policies": [{"ipv4": body}]}
            resp = await client.post("/api/sonicos/route-policies/ipv4", json=payload)
            await self._commit(client)
            if resp.status_code in (200, 201):
                return ExecutionResult(success=True, raw_response=resp.json())
            return ExecutionResult(success=False, error=resp.text)

    async def delete_route_policy(self, rule_id: str) -> ExecutionResult:
        async with self._session() as client:
            resp = await client.delete(f"/api/sonicos/route-policies/ipv4/uuid/{rule_id}")
            await self._commit(client)
            if resp.status_code in (200, 204):
                return ExecutionResult(success=True, rule_id=rule_id)
            return ExecutionResult(success=False, error=resp.text)

    # ------------------------------------------------------------------
    # Snapshot helpers — read-only extended data in a single session
    # ------------------------------------------------------------------

    _BUILTIN_ADDR_PREFIXES = (
        "X0 ", "X1 ", "X2 ", "X3 ", "X4 ", "X5 ", "X6 ", "X7 ", "X8 ", "X9 ",
        "LAN ", "WAN ", "DMZ ", "MGMT ", "VPN ", "WLAN ", "OPT ", "All ", "Default ",
        "MULTICAST ", "Firewalled ", "Non-Firewalled ",
    )
    _BUILTIN_ADDR_NAMES: frozenset = frozenset({
        "Any", "Any (Non-Firewalled)", "RFC1918 Networks",
        "SonicWall Management", "IPv4 Multicast Range",
    })
    _BUILTIN_SVC_NAMES: frozenset = frozenset({
        "Any", "HTTP", "HTTPS", "HTTP CONNECT", "FTP", "FTP Data",
        "SMTP", "POP3", "IMAP4", "IMAP", "DNS", "DHCP Server", "DHCP Client",
        "ICMP Any", "PING", "Echo", "Telnet", "SSH", "SNMP", "NTP",
        "TCP (ANY)", "UDP (ANY)", "NetBIOS", "LDAP", "LDAPS", "Syslog",
        "BGP", "OSPF", "RIP", "RADIUS", "TACACS+", "SIP", "SIP-TLS",
        "H.323", "L2TP", "PPTP", "GRE", "ESP", "AH", "IKE", "TFTP",
        "RTSP", "MGCP", "SCTP", "IGMP", "MS SQL", "MySQL", "Oracle",
        "PostgreSQL", "RDP", "VNC", "RTMP", "NetMeeting", "Gopher",
        "Finger", "Whois", "HTTPS Management",
    })
    _BUILTIN_SVC_GROUP_NAMES: frozenset = frozenset({
        "Any", "Common Peer-to-Peer Applications", "FTP Services",
        "Mail Services", "Remote Access Services", "Web Services",
        "NetBIOS Services", "SQL Services", "Voice Services",
        "Social Networking Sites", "Custom Port Scan Filter Services",
    })

    @classmethod
    def _is_custom_addr(cls, obj: dict) -> bool:
        if obj.get("read_only"):
            return False
        name = obj.get("name", "")
        if not name or name in cls._BUILTIN_ADDR_NAMES:
            return False
        return not any(name.startswith(p) for p in cls._BUILTIN_ADDR_PREFIXES)

    @classmethod
    def _is_custom_svc(cls, obj: dict) -> bool:
        if obj.get("read_only"):
            return False
        name = obj.get("name", "")
        return bool(name) and name not in cls._BUILTIN_SVC_NAMES

    @classmethod
    def _is_custom_svc_group(cls, obj: dict) -> bool:
        if obj.get("read_only"):
            return False
        name = obj.get("name", "")
        return bool(name) and name not in cls._BUILTIN_SVC_GROUP_NAMES

    @staticmethod
    def _addr_obj_value(obj: dict) -> tuple[str, str]:
        if "host" in obj:
            return "host", obj["host"].get("ip", "")
        if "network" in obj:
            n = obj["network"]
            return "network", f"{n.get('subnet', '')}/{n.get('mask', '')}"
        if "range" in obj:
            r = obj["range"]
            return "range", f"{r.get('begin', '')} – {r.get('end', '')}"
        if "fqdn" in obj:
            return "fqdn", obj["fqdn"].get("domain", "")
        if "mac" in obj:
            return "mac", obj["mac"].get("address", "")
        return "other", ""

    @staticmethod
    def _svc_obj_value(obj: dict) -> tuple[str, str]:
        for p in ("tcp", "udp", "icmp", "icmpv6"):
            if p in obj:
                pdata = obj[p]
                b, e = str(pdata.get("begin", "")), str(pdata.get("end", ""))
                port = b if b == e else f"{b}-{e}"
                return p.upper(), port
        return "other", ""

    async def collect_extended_snapshot(self) -> dict:
        """Collect address objects, services, content filter, app rules, and security
        settings in a single authenticated session for use in BookStack snapshots."""
        result: dict[str, Any] = {
            "address_objects": [],
            "address_groups": [],
            "service_objects": [],
            "service_groups": [],
            "content_filter": [],
            "app_rules": [],
            "security_settings": {},
        }
        try:
            async with self._session() as client:

                # ── Address Objects ───────────────────────────────────────────
                try:
                    r = await client.get("/api/sonicos/address-objects/ipv4")
                    if r.status_code == 200:
                        for entry in r.json().get("address_objects", []):
                            obj = entry.get("ipv4", entry) if isinstance(entry, dict) else {}
                            if not self._is_custom_addr(obj):
                                continue
                            kind, value = self._addr_obj_value(obj)
                            result["address_objects"].append({
                                "name": obj.get("name", ""),
                                "type": kind,
                                "value": value,
                                "zone": obj.get("zone", ""),
                            })
                except Exception:
                    pass

                # ── Address Groups ────────────────────────────────────────────
                try:
                    r = await client.get("/api/sonicos/address-groups/ipv4")
                    if r.status_code == 200:
                        ag = r.json().get("address_groups", [])
                        raw_ag = ag.get("ipv4", []) if isinstance(ag, dict) else ag
                        for entry in raw_ag:
                            obj = entry.get("ipv4", entry) if isinstance(entry, dict) else {}
                            if not self._is_custom_addr(obj):
                                continue
                            members = [
                                m.get("name", str(m)) for m in obj.get("address_objects", [])
                            ]
                            result["address_groups"].append({
                                "name": obj.get("name", ""),
                                "members": members,
                            })
                except Exception:
                    pass

                # ── Service Objects ───────────────────────────────────────────
                try:
                    r = await client.get("/api/sonicos/service-objects")
                    if r.status_code == 200:
                        for obj in r.json().get("service_objects", []):
                            if not isinstance(obj, dict) or not self._is_custom_svc(obj):
                                continue
                            proto, port = self._svc_obj_value(obj)
                            result["service_objects"].append({
                                "name": obj.get("name", ""),
                                "proto": proto,
                                "port": port,
                            })
                except Exception:
                    pass

                # ── Service Groups ────────────────────────────────────────────
                try:
                    r = await client.get("/api/sonicos/service-groups")
                    if r.status_code == 200:
                        for obj in r.json().get("service_groups", []):
                            if not isinstance(obj, dict) or not self._is_custom_svc_group(obj):
                                continue
                            members = [
                                m.get("name", str(m)) for m in obj.get("service_objects", [])
                            ]
                            result["service_groups"].append({
                                "name": obj.get("name", ""),
                                "members": members,
                            })
                except Exception:
                    pass

                # ── Content Filter Policies ───────────────────────────────────
                try:
                    r = await client.get("/api/sonicos/content-filter/policies")
                    if r.status_code != 200:
                        r = await client.get("/api/sonicos/content-filter/uri-list-policies")
                    if r.status_code == 200:
                        data = r.json()
                        raw_cf = (
                            data.get("policies")
                            or data.get("content_filter_policies")
                            or data.get("uri_list_policies")
                            or []
                        )
                        for p in raw_cf:
                            if not isinstance(p, dict):
                                continue
                            inner = p.get("content_filter", p.get("uri_list", p))
                            name = inner.get("name", "")
                            if not name:
                                continue
                            enabled = inner.get("enable", inner.get("enabled", True))
                            cats_raw = (
                                inner.get("blocked_categories")
                                or inner.get("categories")
                                or []
                            )
                            cats = [
                                (c.get("name", str(c)) if isinstance(c, dict) else str(c))
                                for c in cats_raw[:15]
                            ]
                            result["content_filter"].append({
                                "name": name,
                                "enabled": enabled,
                                "blocked_categories": cats,
                            })
                except Exception:
                    pass

                # ── App Rules ─────────────────────────────────────────────────
                try:
                    r = await client.get("/api/sonicos/app-rules/policies")
                    if r.status_code == 200:
                        data = r.json()
                        raw_ar = (
                            data.get("policies")
                            or data.get("app_rules_policies")
                            or []
                        )
                        for p in raw_ar:
                            if not isinstance(p, dict):
                                continue
                            inner = p.get("app_rules", p)
                            name = inner.get("name", "")
                            if not name:
                                continue
                            enabled = inner.get("enable", inner.get("enabled", True))
                            action = inner.get("action", {})
                            action_name = (
                                action.get("name", action.get("action", str(action)))
                                if isinstance(action, dict) else str(action)
                            )
                            app = inner.get("application", {})
                            app_name = (
                                app.get("name", app.get("application", str(app)))
                                if isinstance(app, dict) else str(app)
                            )
                            result["app_rules"].append({
                                "name": name,
                                "application": app_name,
                                "action": action_name,
                                "enabled": enabled,
                            })
                except Exception:
                    pass

                # ── Security Services ─────────────────────────────────────────
                for endpoint, key, field_names in [
                    ("/api/sonicos/security-services/gateway-av", "gateway_av",
                     ("gateway_antivirus", "gateway_av")),
                    ("/api/sonicos/security-services/anti-spyware", "anti_spyware",
                     ("anti_spyware",)),
                    ("/api/sonicos/security-services/intrusion-prevention", "ips",
                     ("intrusion_prevention", "ips")),
                ]:
                    try:
                        r = await client.get(endpoint)
                        if r.status_code == 200:
                            data = r.json()
                            inner: dict = {}
                            for f in field_names:
                                if f in data:
                                    inner = data[f]
                                    break
                            if not inner:
                                inner = data
                            result["security_settings"][key] = {
                                "enabled": inner.get("enable", inner.get("enabled", False)),
                                "inbound": inner.get(
                                    "inbound_inspection", inner.get("inbound", False)
                                ),
                                "outbound": inner.get(
                                    "outbound_inspection", inner.get("outbound", False)
                                ),
                            }
                    except Exception:
                        result["security_settings"][key] = {"enabled": False}

        except Exception:
            pass
        return result

