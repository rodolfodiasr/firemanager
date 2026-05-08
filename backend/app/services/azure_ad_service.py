"""Azure AD / Entra ID via Microsoft Graph API (client_credentials flow)."""
from __future__ import annotations

import httpx

_GRAPH = "https://graph.microsoft.com/v1.0"
_LOGIN = "https://login.microsoftonline.com"


async def _token(config: dict) -> str:
    url = f"{_LOGIN}/{config['azure_tenant_id']}/oauth2/v2.0/token"
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, data={
            "grant_type": "client_credentials",
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "scope": "https://graph.microsoft.com/.default",
        })
        r.raise_for_status()
        return r.json()["access_token"]


async def list_users(config: dict) -> list[dict]:
    token = await _token(config)
    headers = {"Authorization": f"Bearer {token}"}
    users: list[dict] = []
    url = (
        f"{_GRAPH}/users"
        "?$select=id,userPrincipalName,displayName,mail,department,jobTitle"
        ",accountEnabled,signInActivity"
        "&$top=999"
    )
    async with httpx.AsyncClient(timeout=30) as c:
        while url:
            r = await c.get(url, headers=headers)
            r.raise_for_status()
            body = r.json()
            users.extend(body.get("value", []))
            url = body.get("@odata.nextLink")
    return users


async def find_user(config: dict, username: str) -> dict | None:
    token = await _token(config)
    headers = {"Authorization": f"Bearer {token}"}
    escaped = username.replace("'", "''")
    url = (
        f"{_GRAPH}/users"
        f"?$filter=userPrincipalName eq '{escaped}' or mail eq '{escaped}'"
        "&$select=id,userPrincipalName,displayName,mail,accountEnabled"
    )
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(url, headers=headers)
        r.raise_for_status()
        users = r.json().get("value", [])
        return users[0] if users else None


async def disable_user(config: dict, external_id: str) -> None:
    token = await _token(config)
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.patch(f"{_GRAPH}/users/{external_id}", headers=hdrs, json={"accountEnabled": False})
        r.raise_for_status()
        await c.post(f"{_GRAPH}/users/{external_id}/revokeSignInSessions", headers=hdrs)


async def add_user_to_groups(config: dict, user_id: str, group_names: list[str]) -> None:
    token = await _token(config)
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15) as c:
        for group_name in group_names:
            escaped = group_name.replace("'", "''")
            r = await c.get(
                f"{_GRAPH}/groups?$filter=displayName eq '{escaped}'&$select=id",
                headers=hdrs,
            )
            r.raise_for_status()
            groups = r.json().get("value", [])
            if not groups:
                raise ValueError(f"Grupo '{group_name}' não encontrado no Azure AD")
            group_id = groups[0]["id"]
            r = await c.post(
                f"{_GRAPH}/groups/{group_id}/members/$ref",
                headers=hdrs,
                json={"@odata.id": f"{_GRAPH}/directoryObjects/{user_id}"},
            )
            if r.status_code not in (204, 400):
                r.raise_for_status()
