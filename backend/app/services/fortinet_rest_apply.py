"""Fase 26 — Fortinet REST applier for Golden Bundle sections."""
from __future__ import annotations

import httpx


class FortinetRestApply:
    """Applies Golden Bundle sections to Fortinet via REST API."""

    def __init__(self, host: str, token: str, vdom: str = "root", verify_ssl: bool = False) -> None:
        self.base = host
        self.headers = {"Authorization": f"Bearer {token}"}
        self.vdom = vdom
        self.verify_ssl = verify_ssl

    async def apply_address_objects(self, objects: list[dict]) -> dict:
        """POST /api/v2/cmdb/firewall/address for each object."""
        results = []
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            for obj in objects:
                obj["vdom"] = self.vdom
                r = await client.post(
                    f"{self.base}/api/v2/cmdb/firewall/address",
                    headers=self.headers,
                    json=obj,
                )
                results.append({
                    "name": obj.get("name"),
                    "status": r.status_code,
                    "ok": r.status_code in (200, 201),
                })
        return {"results": results}

    async def apply_policies(self, policies: list[dict]) -> dict:
        """POST /api/v2/cmdb/firewall/policy for each policy."""
        results = []
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            for policy in policies:
                policy["vdom"] = self.vdom
                r = await client.post(
                    f"{self.base}/api/v2/cmdb/firewall/policy",
                    headers=self.headers,
                    json=policy,
                )
                results.append({
                    "name": policy.get("name"),
                    "status": r.status_code,
                    "ok": r.status_code in (200, 201),
                })
        return {"results": results}

    async def apply_webfilter_profile(self, profile: dict) -> dict:
        """POST /api/v2/cmdb/webfilter/profile."""
        profile["vdom"] = self.vdom
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            r = await client.post(
                f"{self.base}/api/v2/cmdb/webfilter/profile",
                headers=self.headers,
                json=profile,
            )
        return {"status": r.status_code, "ok": r.status_code in (200, 201)}

    async def apply_geo_ip(self, country_list: list[str], action: str = "block") -> dict:
        """Create a geo-IP address group for the given countries."""
        payload = {
            "name": "fm-geo-block",
            "type": "geography",
            "country": [{"name": c} for c in country_list],
            "vdom": self.vdom,
        }
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            r = await client.post(
                f"{self.base}/api/v2/cmdb/firewall/address",
                headers=self.headers,
                json=payload,
            )
        return {"status": r.status_code, "ok": r.status_code in (200, 201)}

    async def apply_ipsec_vpn(self, phase1: dict, phase2: dict) -> dict:
        """POST VPN phase1-interface and phase2-interface."""
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            r1 = await client.post(
                f"{self.base}/api/v2/cmdb/vpn.ipsec/phase1-interface",
                headers=self.headers,
                json=phase1,
            )
            r2 = await client.post(
                f"{self.base}/api/v2/cmdb/vpn.ipsec/phase2-interface",
                headers=self.headers,
                json=phase2,
            )
        return {
            "phase1": {"status": r1.status_code},
            "phase2": {"status": r2.status_code},
            "ok": r1.is_success and r2.is_success,
        }
