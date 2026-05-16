"""Fase 22B — Tactical RMM REST API integration."""
from __future__ import annotations

import httpx


def _headers(config: dict) -> dict:
    return {"X-API-KEY": config["api_key"], "Content-Type": "application/json"}


def _base_url(config: dict) -> str:
    return (config.get("base_url") or config.get("url", "")).rstrip("/")


async def test_connection(config: dict) -> tuple[bool, str]:
    try:
        base = _base_url(config)
        async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=15) as client:
            r = await client.get(f"{base}/accounts/users/", headers=_headers(config))
            r.raise_for_status()
            users = r.json()
            return True, f"Conexão OK ({len(users)} usuário(s))"
    except Exception as e:
        return False, str(e)


async def list_users(config: dict) -> list[dict]:
    base = _base_url(config)
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=15) as client:
        r = await client.get(f"{base}/accounts/users/", headers=_headers(config))
        r.raise_for_status()
        return r.json()


async def get_user(config: dict, username: str) -> dict | None:
    try:
        users = await list_users(config)
        for u in users:
            if u.get("username", "").lower() == username.lower():
                return u
        return None
    except Exception:
        return None


async def create_user(config: dict, username: str, email: str, password: str, role: str = "user") -> dict:
    base = _base_url(config)
    payload = {"username": username, "email": email, "password": password, "role": role}
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=15) as client:
        r = await client.post(f"{base}/accounts/users/", json=payload, headers=_headers(config))
        r.raise_for_status()
        return r.json()


async def disable_user(config: dict, user_id: int) -> None:
    base = _base_url(config)
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True), timeout=15) as client:
        r = await client.patch(
            f"{base}/accounts/users/{user_id}/",
            json={"is_active": False},
            headers=_headers(config),
        )
        r.raise_for_status()
