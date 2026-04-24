"""SonicWall SonicOS 6/7/8 REST API connector."""
import contextlib
import json
import logging
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
    Version is auto-detected from auth response:
      - SonicOS 6.x: access_rules is a flat array, action/from/to are strings
      - SonicOS 7.x: access_rules wraps {"ipv4": [...]}, nested objects
    SonicOS 6 requires an explicit commit after mutations.
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
        # Determine SonicOS format from stored firmware version when available.
        # "6.x.y" → v6 format; "7.x.y"/"8.x.y" → v7 format.
        # Falls back to auth-response heuristic when firmware is unknown.
        self._v6: bool | None = self._detect_v6_from_firmware(known_firmware)

    @staticmethod
    def _detect_v6_from_firmware(firmware: str | None) -> bool | None:
        if not firmware or firmware in ("unknown", ""):
            return None
        try:
            major = int(firmware.split(".")[0])
            return major <= 6
        except (ValueError, IndexError):
            return None

    @contextlib.asynccontextmanager
    async def _session(self) -> AsyncGenerator[httpx.AsyncClient, None]:
        """Authenticate via Digest Auth on POST /auth and yield the client."""
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

            # Auto-detect SonicOS version from auth response structure.
            # SonicOS 6.x returns detailed info (config_mode, privilege, model…)
            # inside info[0]; SonicOS 7 uses a simpler structure.
            try:
                body = resp.json()
                info = body.get("status", {}).get("info", [{}])
                if info and "config_mode" in info[0]:
                    self._v6 = True
                elif self._v6 is None:
                    self._v6 = (self.os_version <= 6)
            except Exception:
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
                # Refine format detection once we have a real firmware version
                if firmware and firmware != "unknown":
                    self._v6 = self._detect_v6_from_firmware(firmware)

                return ConnectionResult(success=True, latency_ms=latency, firmware_version=firmware)
        except Exception as exc:
            return ConnectionResult(success=False, error=str(exc))

    async def _fetch_firmware(self, client: httpx.AsyncClient) -> str:
        """Try known endpoints to retrieve firmware version string."""
        candidates = [
            # SonicOS 6.5: /version returns {"firmware_version": "..."}
            ("/api/sonicos/version", lambda d: d.get("firmware_version")),
            # SonicOS 7/8: /device nests under "device" key
            ("/api/sonicos/device", lambda d: (
                d.get("device", {}).get("firmware_version") or d.get("firmware_version")
            )),
        ]
        for path, extractor in candidates:
            try:
                r = await client.get(path)
                if r.status_code == 200:
                    data = r.json()
                    value = extractor(data)
                    if value:
                        return str(value)
            except Exception:
                continue
        return "unknown"

    def _parse_rules(self, data: dict) -> list[FirewallRule]:
        """Parse access-rules response for both SonicOS 6 and 7 formats."""
        logger.debug("SonicWall raw access-rules: %s", json.dumps(data)[:600])
        access_rules = data.get("access_rules", {})

        if isinstance(access_rules, dict):
            # SonicOS 7: {"access_rules": {"ipv4": [...]}}
            raw_list = access_rules.get("ipv4", [])
        elif isinstance(access_rules, list):
            # SonicOS 6: flat list or zone-grouped list
            raw_list = []
            for item in access_rules:
                if isinstance(item, dict):
                    if "ipv4" in item:
                        raw_list.extend(item["ipv4"])
                    else:
                        raw_list.append(item)
        else:
            raw_list = []

        rules = []
        for r in raw_list:
            if not isinstance(r, dict):
                continue
            rules.append(
                FirewallRule(
                    rule_id=str(r.get("rule_id", r.get("uuid", ""))),
                    name=r.get("name", ""),
                    src=r.get("source", {}).get("address", {}).get("name", "Any"),
                    dst=r.get("destination", {}).get("address", {}).get("name", "Any"),
                    service=r.get("service", {}).get("name", "Any"),
                    action=r.get("action", "allow"),
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

    def _rule_payload(self, spec: RuleSpec) -> dict[str, Any]:
        """Build create/edit rule payload for the detected SonicOS version."""
        if self._v6:
            # SonicOS 6.x: access_rules is a flat array; action/zones are strings
            return {
                "access_rules": [
                    {
                        "name": spec.name,
                        "enable": True,
                        "action": spec.action,
                        "from": "LAN",
                        "to": "WAN",
                        "source": {"address": {"name": spec.src_address}},
                        "destination": {"address": {"name": spec.dst_address}},
                        "service": {"name": spec.service},
                        "comment": spec.comment or "",
                    }
                ]
            }
        # SonicOS 7.x: access_rules wraps {"ipv4": [...]}; nested objects
        return {
            "access_rules": {
                "ipv4": [
                    {
                        "name": spec.name,
                        "action": {"action": spec.action},
                        "from": {"zone": "LAN"},
                        "to": {"zone": "WAN"},
                        "source": {"address": {"name": spec.src_address}},
                        "destination": {"address": {"name": spec.dst_address}},
                        "service": {"name": spec.service},
                        "comment": spec.comment or "",
                        "enable": True,
                    }
                ]
            }
        }

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        async with self._session() as client:
            payload = self._rule_payload(spec)
            resp = await client.post("/api/sonicos/access-rules/ipv4", json=payload)
            await self._commit(client)
            if resp.status_code in (200, 201):
                return ExecutionResult(success=True, raw_response=resp.json())
            return ExecutionResult(success=False, error=resp.text)

    async def create_group(self, spec: GroupSpec) -> ExecutionResult:
        if self._v6:
            payload = {
                "address_groups": [
                    {"name": spec.name, "address_objects": [{"name": m} for m in spec.members]}
                ]
            }
        else:
            payload = {
                "address_groups": {
                    "ipv4": [{"name": spec.name, "address_objects": [{"name": m} for m in spec.members]}]
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
        payload = self._rule_payload(spec)
        async with self._session() as client:
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
