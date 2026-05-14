"""ConnectWise Automate REST API v1 — Basic Auth → JWT token."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

_token_cache: dict[str, dict] = {}


async def _get_token(config: dict) -> str:
    base = config["base_url"].rstrip("/")
    key = base
    cached = _token_cache.get(key)
    if cached and cached["expires_at"] > datetime.now(timezone.utc):
        return cached["token"]

    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=15) as client:
        r = await client.post(
            f"{base}/cwa/api/v1/apitoken",
            auth=(config["username"], config["password"]),
        )
        r.raise_for_status()
        data = r.json()

    token = data.get("AccessToken") or data.get("Token") or data.get("access_token", "")
    expires_in = int(data.get("ExpiresIn", 3600))
    _token_cache[key] = {
        "token": token,
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60),
    }
    return token


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def test_connection(config: dict) -> tuple[bool, str]:
    try:
        token = await _get_token(config)
        base = config["base_url"].rstrip("/")
        async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=15) as client:
            r = await client.get(
                f"{base}/cwa/api/v1/locations",
                headers=_headers(token),
                params={"pagesize": 1},
            )
            r.raise_for_status()
            data = r.json()
            total = data.get("TotalCount", len(data) if isinstance(data, list) else 0)
            return True, f"Conexão OK ({total} localização(ões))"
    except Exception as e:
        return False, str(e)


async def list_devices(config: dict) -> list[dict]:
    token = await _get_token(config)
    base = config["base_url"].rstrip("/")
    devices: list[dict] = []
    page = 1
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=30) as client:
        while True:
            r = await client.get(
                f"{base}/cwa/api/v1/computers",
                headers=_headers(token),
                params={"page": page, "pagesize": 100},
            )
            r.raise_for_status()
            data = r.json()
            items = data if isinstance(data, list) else data.get("Computers", data.get("computers", []))
            if not items:
                break
            devices.extend(items)
            if len(items) < 100:
                break
            page += 1
    return devices


async def list_alerts(config: dict) -> list[dict]:
    token = await _get_token(config)
    base = config["base_url"].rstrip("/")
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=20) as client:
        r = await client.get(f"{base}/cwa/api/v1/alerts", headers=_headers(token))
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else data.get("Alerts", [])


def normalize_device(raw: dict) -> dict:
    status_code = int(raw.get("Status", raw.get("ComputerStatus", 0)))
    return {
        "external_id": str(raw.get("Id", raw.get("ComputerId", ""))),
        "hostname": raw.get("Name") or raw.get("ComputerName", ""),
        "os_name": raw.get("OperatingSystemName") or raw.get("OS", ""),
        "ip_address": raw.get("RemoteAddress") or raw.get("LocalAddress"),
        "status": "online" if status_code == 1 else "offline",
        "last_seen": raw.get("LastContact") or raw.get("LastCheckin"),
        "patches_pending": raw.get("PatchCount"),
        "alerts_count": raw.get("AlertCount", 0) or 0,
        "raw_data": raw,
    }
