"""Fase 22B — Apache Guacamole REST API integration."""
from __future__ import annotations

import httpx


async def _auth(config: dict) -> tuple[str, str]:
    """Returns (authToken, dataSource)."""
    base = config["url"].rstrip("/")
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=15) as client:
        r = await client.post(
            f"{base}/api/tokens",
            data={"username": config["username"], "password": config["password"]},
        )
        r.raise_for_status()
        data = r.json()
        return data["authToken"], data.get("dataSource", "postgresql")


async def test_connection(config: dict) -> tuple[bool, str]:
    try:
        token, ds = await _auth(config)
        return True, f"Conexão OK (dataSource: {ds})"
    except Exception as e:
        return False, str(e)


async def get_user(config: dict, username: str) -> dict | None:
    try:
        token, ds = await _auth(config)
        base = config["url"].rstrip("/")
        async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=15) as client:
            r = await client.get(
                f"{base}/api/session/data/{ds}/users/{username}",
                headers={"Guacamole-Token": token},
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


async def create_user(config: dict, username: str, password: str, display_name: str | None = None) -> dict:
    token, ds = await _auth(config)
    base = config["url"].rstrip("/")
    payload = {
        "username": username,
        "password": password,
        "attributes": {
            "disabled": "",
            "expired": "",
            "access-window-start": "",
            "access-window-end": "",
            "valid-from": "",
            "valid-until": "",
            "timezone": None,
            "guac-full-name": display_name or username,
            "guac-email-address": "",
            "guac-organizational-role": "",
        },
    }
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=15) as client:
        r = await client.post(
            f"{base}/api/session/data/{ds}/users",
            json=payload,
            headers={"Guacamole-Token": token, "Content-Type": "application/json"},
        )
        r.raise_for_status()
        return r.json()


async def disable_user(config: dict, username: str) -> None:
    token, ds = await _auth(config)
    base = config["url"].rstrip("/")
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=15) as client:
        r = await client.patch(
            f"{base}/api/session/data/{ds}/users/{username}",
            json=[{"op": "replace", "path": "/attributes/disabled", "value": "true"}],
            headers={"Guacamole-Token": token, "Content-Type": "application/json"},
        )
        r.raise_for_status()


async def delete_user(config: dict, username: str) -> None:
    token, ds = await _auth(config)
    base = config["url"].rstrip("/")
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=15) as client:
        r = await client.delete(
            f"{base}/api/session/data/{ds}/users/{username}",
            headers={"Guacamole-Token": token},
        )
        if r.status_code != 404:
            r.raise_for_status()
