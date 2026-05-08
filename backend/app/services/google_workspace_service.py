"""Google Workspace Directory API via service account JWT (domain-wide delegation)."""
from __future__ import annotations

import base64
import json
import time

import httpx

_DIR = "https://admin.googleapis.com/admin/directory/v1"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SCOPE = "https://www.googleapis.com/auth/admin.directory.user"


def _make_jwt(service_account: dict, admin_email: str) -> str:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    now = int(time.time())
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
    ).rstrip(b"=")
    payload = base64.urlsafe_b64encode(json.dumps({
        "iss": service_account["client_email"],
        "sub": admin_email,
        "aud": _TOKEN_URL,
        "scope": _SCOPE,
        "iat": now,
        "exp": now + 3600,
    }).encode()).rstrip(b"=")

    message = header + b"." + payload
    private_key = serialization.load_pem_private_key(
        service_account["private_key"].encode(), password=None
    )
    sig = private_key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    return (message + b"." + base64.urlsafe_b64encode(sig).rstrip(b"=")).decode()


async def _token(config: dict) -> str:
    jwt = _make_jwt(config["service_account"], config["admin_email"])
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(_TOKEN_URL, data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": jwt,
        })
        r.raise_for_status()
        return r.json()["access_token"]


async def list_users(config: dict) -> list[dict]:
    token = await _token(config)
    domain = config["domain"]
    headers = {"Authorization": f"Bearer {token}"}
    users: list[dict] = []
    url = f"{_DIR}/users?domain={domain}&maxResults=500&projection=full"
    async with httpx.AsyncClient(timeout=30) as c:
        while url:
            r = await c.get(url, headers=headers)
            r.raise_for_status()
            body = r.json()
            users.extend(body.get("users", []))
            page = body.get("nextPageToken")
            url = f"{_DIR}/users?domain={domain}&maxResults=500&projection=full&pageToken={page}" if page else None
    return users


async def find_user(config: dict, username: str) -> dict | None:
    token = await _token(config)
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{_DIR}/users/{username}", headers=headers)
        if r.status_code == 200:
            return r.json()
        return None


async def suspend_user(config: dict, user_key: str) -> None:
    token = await _token(config)
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.patch(f"{_DIR}/users/{user_key}", headers=hdrs, json={"suspended": True})
        r.raise_for_status()


async def add_user_to_groups(config: dict, user_email: str, group_names: list[str]) -> None:
    token = await _token(config)
    domain = config["domain"]
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15) as c:
        for group_name in group_names:
            r = await c.get(f"{_DIR}/groups?domain={domain}&query=name={group_name}", headers=hdrs)
            r.raise_for_status()
            groups = r.json().get("groups", [])
            if not groups:
                raise ValueError(f"Grupo '{group_name}' não encontrado no Google Workspace")
            group_key = groups[0]["email"]
            r = await c.post(
                f"{_DIR}/groups/{group_key}/members",
                headers=hdrs,
                json={"email": user_email, "role": "MEMBER"},
            )
            if r.status_code not in (200, 409):
                r.raise_for_status()
