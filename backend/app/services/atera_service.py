"""Atera RMM REST API v3 — X-API-KEY header."""
from __future__ import annotations

import httpx

_BASE = "https://app.atera.com/api/v3"


def _headers(config: dict) -> dict:
    return {"X-API-KEY": config["api_key"], "Content-Type": "application/json"}


def _base(config: dict) -> str:
    return config.get("base_url", _BASE).rstrip("/")


async def test_connection(config: dict) -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=15) as client:
            r = await client.get(f"{_base(config)}/customers", headers=_headers(config), params={"page": 1, "itemsInPage": 1})
            r.raise_for_status()
            data = r.json()
            total = data.get("totalPages", 0)
            return True, f"Conexão OK ({total} página(s) de clientes)"
    except Exception as e:
        return False, str(e)


async def list_devices(config: dict) -> list[dict]:
    devices: list[dict] = []
    page = 1
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=30) as client:
        while True:
            r = await client.get(
                f"{_base(config)}/agents",
                headers=_headers(config),
                params={"page": page, "itemsInPage": 50},
            )
            r.raise_for_status()
            data = r.json()
            items = data.get("items", [])
            devices.extend(items)
            if page >= data.get("totalPages", 1):
                break
            page += 1
    return devices


async def list_alerts(config: dict) -> list[dict]:
    alerts: list[dict] = []
    page = 1
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=20) as client:
        while True:
            r = await client.get(
                f"{_base(config)}/alerts",
                headers=_headers(config),
                params={"page": page, "itemsInPage": 50},
            )
            r.raise_for_status()
            data = r.json()
            items = data.get("items", [])
            alerts.extend(items)
            if page >= data.get("totalPages", 1):
                break
            page += 1
    return alerts


def normalize_device(raw: dict) -> dict:
    online_status = str(raw.get("OnlineStatus", "")).lower()
    return {
        "external_id": str(raw.get("AgentID", "")),
        "hostname": raw.get("MachineName") or raw.get("ComputerName", ""),
        "os_name": raw.get("OSType", ""),
        "ip_address": raw.get("IpAddresses", [None])[0] if raw.get("IpAddresses") else raw.get("InternalIP"),
        "status": "online" if online_status == "online" else "offline",
        "last_seen": raw.get("LastPatchManagementReceived") or raw.get("LastSeenDate"),
        "patches_pending": raw.get("PatchesRequireReboot", 0) or 0,
        "alerts_count": 0,
        "raw_data": raw,
    }
