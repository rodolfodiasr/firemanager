"""Fase 22C — Unifi Network Controller REST API integration."""
from __future__ import annotations

import httpx


async def _auth(client: httpx.AsyncClient, config: dict) -> str:
    base = config["url"].rstrip("/")
    is_unifi_os = config.get("unifi_os", False)
    login_url = f"{base}/api/auth/login" if is_unifi_os else f"{base}/api/login"
    payload = {"username": config["username"], "password": config["password"]}
    r = await client.post(login_url, json=payload)
    r.raise_for_status()
    if is_unifi_os:
        return r.json().get("data", {}).get("token", "")
    return ""  # legacy uses cookies


async def test_connection(config: dict) -> tuple[bool, str]:
    try:
        base = config["url"].rstrip("/")
        site = config.get("site", "default")
        is_unifi_os = config.get("unifi_os", False)
        async with httpx.AsyncClient(verify=config.get("verify_ssl", False), timeout=15) as client:
            await _auth(client, config)
            stat_url = (
                f"{base}/proxy/network/api/s/{site}/stat/admin"
                if is_unifi_os
                else f"{base}/api/s/{site}/stat/admin"
            )
            r = await client.get(stat_url)
            r.raise_for_status()
            data = r.json().get("data", [])
            return True, f"Conexão OK ({len(data)} admin(s) no site '{site}')"
    except Exception as e:
        return False, str(e)


async def list_admins(config: dict) -> list[dict]:
    base = config["url"].rstrip("/")
    site = config.get("site", "default")
    is_unifi_os = config.get("unifi_os", False)
    async with httpx.AsyncClient(verify=config.get("verify_ssl", False), timeout=15) as client:
        await _auth(client, config)
        stat_url = (
            f"{base}/proxy/network/api/s/{site}/stat/admin"
            if is_unifi_os
            else f"{base}/api/s/{site}/stat/admin"
        )
        r = await client.get(stat_url)
        r.raise_for_status()
        return r.json().get("data", [])


async def get_admin(config: dict, username: str) -> dict | None:
    try:
        admins = await list_admins(config)
        for a in admins:
            if a.get("name", "").lower() == username.lower():
                return a
        return None
    except Exception:
        return None


async def invite_admin(config: dict, username: str, email: str, role: str = "readonly") -> dict:
    base = config["url"].rstrip("/")
    site = config.get("site", "default")
    is_unifi_os = config.get("unifi_os", False)
    async with httpx.AsyncClient(verify=config.get("verify_ssl", False), timeout=15) as client:
        await _auth(client, config)
        cmd_url = (
            f"{base}/proxy/network/api/s/{site}/cmd/sitemgr"
            if is_unifi_os
            else f"{base}/api/s/{site}/cmd/sitemgr"
        )
        payload = {
            "cmd": "invite-admin",
            "name": username,
            "email": email,
            "role": role,
            "enable_sso": False,
        }
        r = await client.post(cmd_url, json=payload)
        r.raise_for_status()
        return r.json().get("data", [{}])[0]


async def revoke_admin(config: dict, admin_id: str) -> None:
    base = config["url"].rstrip("/")
    site = config.get("site", "default")
    is_unifi_os = config.get("unifi_os", False)
    async with httpx.AsyncClient(verify=config.get("verify_ssl", False), timeout=15) as client:
        await _auth(client, config)
        cmd_url = (
            f"{base}/proxy/network/api/s/{site}/cmd/sitemgr"
            if is_unifi_os
            else f"{base}/api/s/{site}/cmd/sitemgr"
        )
        payload = {"cmd": "revoke-admin", "admin": admin_id}
        r = await client.post(cmd_url, json=payload)
        r.raise_for_status()
