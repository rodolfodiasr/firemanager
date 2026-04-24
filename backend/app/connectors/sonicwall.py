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
        if self._v6:
            await client.post("/api/sonicos/config/pending")

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
        """Create a host/network address object if ip_str is an IP. Returns object name."""
        obj_name = self._obj_name_for_ip(ip_str)
        if obj_name is None:
            return ip_str  # already named

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

    def _rule_payload(
        self, spec: RuleSpec, src_name: str, dst_name: str, svc_name: str
    ) -> dict[str, Any]:
        if self._v6:
            return {
                "access_rules": [
                    {
                        "name": spec.name,
                        "enable": True,
                        "action": spec.action,
                        "from": "LAN",
                        "to": "WAN",
                        "source": {"address": {"name": src_name}},
                        "destination": {"address": {"name": dst_name}},
                        "service": {"name": svc_name},
                        "comment": spec.comment or "",
                    }
                ]
            }
        # v7/v8: array of per-entry {"ipv4": {...}} wrappers (same pattern as address-objects)
        return {
            "access_rules": [
                {
                    "ipv4": {
                        "name": spec.name,
                        "enable": True,
                        "action": {"action": spec.action},
                        "from": {"zone": "LAN"},
                        "to": {"zone": "WAN"},
                        "source": {"address": {"name": src_name}},
                        "destination": {"address": {"name": dst_name}},
                        "service": {"name": svc_name},
                        "comment": spec.comment or "",
                    }
                }
            ]
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
            raw_list = []
            for item in access_rules:
                if isinstance(item, dict):
                    raw_list.extend(item["ipv4"]) if "ipv4" in item else raw_list.append(item)
        else:
            raw_list = []

        rules = []
        for r in raw_list:
            if not isinstance(r, dict):
                continue
            action = r.get("action", "allow")
            if isinstance(action, dict):
                action = action.get("action", "allow")
            rules.append(
                FirewallRule(
                    rule_id=str(r.get("rule_id", r.get("uuid", ""))),
                    name=r.get("name", ""),
                    src=r.get("source", {}).get("address", {}).get("name", "Any"),
                    dst=r.get("destination", {}).get("address", {}).get("name", "Any"),
                    service=r.get("service", {}).get("name", "Any"),
                    action=action,
                    enabled=r.get("enable", True),
                    raw=r,
                )
            )
        return rules

    async def list_rules(self) -> list[FirewallRule]:
        async with self._session() as client:
            resp = await client.get("/api/sonicos/access-rules/ipv4")
            resp.raise_for_status()
            return self._parse_rules(resp.json())

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        async with self._session() as client:
            # Ensure address objects exist for raw IPs
            src_name = await self._ensure_address_object(client, spec.src_address, "LAN")
            dst_name = await self._ensure_address_object(client, spec.dst_address, "WAN")
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
            src_name = await self._ensure_address_object(client, spec.src_address, "LAN")
            dst_name = await self._ensure_address_object(client, spec.dst_address, "WAN")
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
