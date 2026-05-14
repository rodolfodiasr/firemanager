"""NinjaRMM (NinjaOne) REST API v2 — OAuth2 client_credentials."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

_token_cache: dict[str, dict] = {}


async def _get_token(config: dict) -> str:
    key = config.get("client_id", "")
    cached = _token_cache.get(key)
    if cached and cached["expires_at"] > datetime.now(timezone.utc):
        return cached["access_token"]

    base = config["base_url"].rstrip("/")
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=15) as client:
        r = await client.post(
            f"{base}/ws/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "scope": "monitoring management",
            },
        )
        r.raise_for_status()
        data = r.json()

    access_token = data["access_token"]
    expires_in = int(data.get("expires_in", 3600))
    _token_cache[key] = {
        "access_token": access_token,
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60),
    }
    return access_token


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def test_connection(config: dict) -> tuple[bool, str]:
    try:
        token = await _get_token(config)
        base = config["base_url"].rstrip("/")
        async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=15) as client:
            r = await client.get(f"{base}/v2/organizations", headers=_headers(token))
            r.raise_for_status()
            orgs = r.json()
            return True, f"Conexão OK ({len(orgs)} organização(ões))"
    except Exception as e:
        return False, str(e)


async def list_devices(config: dict) -> list[dict]:
    token = await _get_token(config)
    base = config["base_url"].rstrip("/")
    devices: list[dict] = []
    after = None
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=30) as client:
        while True:
            params: dict[str, Any] = {"pageSize": 200}
            if after:
                params["after"] = after
            r = await client.get(f"{base}/v2/devices", headers=_headers(token), params=params)
            r.raise_for_status()
            page = r.json()
            if isinstance(page, list):
                devices.extend(page)
                break
            items = page.get("devices", page.get("results", []))
            devices.extend(items)
            after = page.get("after") or page.get("lastCursor")
            if not after or not items:
                break
    return devices


async def list_alerts(config: dict) -> list[dict]:
    token = await _get_token(config)
    base = config["base_url"].rstrip("/")
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=20) as client:
        r = await client.get(f"{base}/v2/alerts", headers=_headers(token))
        r.raise_for_status()
        return r.json()


def normalize_device(raw: dict) -> dict:
    system = raw.get("system", {})
    online = raw.get("online", False)
    return {
        "external_id": str(raw.get("id", "")),
        "hostname": system.get("name") or raw.get("dnsName", ""),
        "os_name": system.get("operatingSystem") or raw.get("os", {}).get("name", ""),
        "ip_address": raw.get("ipAddresses", [None])[0] if raw.get("ipAddresses") else None,
        "status": "online" if online else "offline",
        "last_seen": raw.get("lastContact"),
        "patches_pending": raw.get("patches", {}).get("pendingCount"),
        "alerts_count": len(raw.get("alerts", [])),
        "raw_data": raw,
    }
