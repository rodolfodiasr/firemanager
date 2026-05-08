"""Local Active Directory via LDAP (ldap3 + asyncio.to_thread)."""
from __future__ import annotations

import asyncio
import ssl
from datetime import datetime, timedelta, timezone

_ATTRS = [
    "sAMAccountName",
    "displayName",
    "mail",
    "department",
    "title",
    "userAccountControl",
    "lastLogonTimestamp",
    "distinguishedName",
    "userPrincipalName",
]

_ACCOUNTDISABLE = 0x0002


def _str(val) -> str | None:
    if val is None:
        return None
    if isinstance(val, list):
        return str(val[0]) if val else None
    s = str(val)
    return s if s else None


def _filetime(val) -> str | None:
    """Convert Windows FILETIME or ldap3 datetime to ISO string."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    try:
        ft = int(val)
        if ft <= 0:
            return None
        epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
        return (epoch + timedelta(microseconds=ft // 10)).isoformat()
    except (TypeError, ValueError):
        return None


def _connect(config: dict):
    from ldap3 import Server, Connection, SIMPLE, Tls

    host = config["host"]
    port = int(config.get("port", 389))
    use_ssl = config.get("use_ssl", False)
    username = config["username"]
    password = config["password"]

    tls = Tls(validate=ssl.CERT_NONE) if use_ssl else None
    server = Server(host, port=port, use_ssl=use_ssl, tls=tls)
    conn = Connection(server, user=username, password=password, authentication=SIMPLE, auto_bind=True)
    return conn


# ── Sync implementations (run via asyncio.to_thread) ──────────────────────────

def _list_users_sync(config: dict) -> list[dict]:
    from ldap3 import SUBTREE

    conn = _connect(config)
    base_dn = config["base_dn"]
    search_base = config.get("user_search_base") or base_dn

    users: list[dict] = []
    for entry in conn.extend.standard.paged_search(
        search_base=search_base,
        search_filter="(&(objectClass=user)(objectCategory=person))",
        search_scope=SUBTREE,
        attributes=_ATTRS,
        paged_size=500,
        generator=True,
    ):
        if entry.get("type") != "searchResEntry":
            continue
        a = entry["attributes"]
        uac = a.get("userAccountControl") or 512
        if isinstance(uac, list):
            uac = uac[0] if uac else 512
        uac = int(uac)
        users.append({
            "dn": entry["dn"],
            "username": _str(a.get("sAMAccountName")) or "",
            "display_name": _str(a.get("displayName")),
            "email": _str(a.get("mail")),
            "department": _str(a.get("department")),
            "job_title": _str(a.get("title")),
            "is_enabled": not bool(uac & _ACCOUNTDISABLE),
            "last_logon_str": _filetime(a.get("lastLogonTimestamp")),
        })

    conn.unbind()
    return users


def _find_user_sync(config: dict, username: str) -> dict | None:
    from ldap3 import SUBTREE

    conn = _connect(config)
    base_dn = config["base_dn"]
    search_base = config.get("user_search_base") or base_dn

    # Escape LDAP special chars in username
    escaped = username.translate(str.maketrans({
        "*": "\\2a", "(": "\\28", ")": "\\29", "\\": "\\5c", "\x00": "\\00",
    }))
    search_filter = (
        f"(&(objectClass=user)(objectCategory=person)"
        f"(|(sAMAccountName={escaped})(mail={escaped})(userPrincipalName={escaped})))"
    )

    conn.search(
        search_base=search_base,
        search_filter=search_filter,
        attributes=["sAMAccountName", "displayName", "distinguishedName", "userAccountControl"],
    )

    result = None
    if conn.entries:
        e = conn.entries[0]
        result = {
            "dn": str(e.distinguishedName),
            "username": _str(e.sAMAccountName.value),
            "display_name": _str(e.displayName.value) if e.displayName else None,
        }
    conn.unbind()
    return result


def _disable_user_sync(config: dict, dn: str) -> None:
    from ldap3 import MODIFY_REPLACE, BASE

    conn = _connect(config)
    conn.search(dn, "(objectClass=*)", search_scope=BASE, attributes=["userAccountControl"])

    if not conn.entries:
        conn.unbind()
        raise ValueError(f"Objeto não encontrado no AD: {dn}")

    uac = int(conn.entries[0].userAccountControl.value or 512)
    new_uac = uac | _ACCOUNTDISABLE  # Set ACCOUNTDISABLE bit

    conn.modify(dn, {"userAccountControl": [(MODIFY_REPLACE, [new_uac])]})
    if conn.result["result"] != 0:
        conn.unbind()
        raise RuntimeError(f"Falha ao modificar AD: {conn.result['description']}")
    conn.unbind()


def _test_connection_sync(config: dict) -> tuple[bool, str]:
    try:
        conn = _connect(config)
        conn.unbind()
        return True, "Conexão LDAP estabelecida com sucesso"
    except Exception as e:
        return False, str(e)


# ── Async wrappers ─────────────────────────────────────────────────────────────

async def list_users(config: dict) -> list[dict]:
    return await asyncio.to_thread(_list_users_sync, config)


async def find_user(config: dict, username: str) -> dict | None:
    return await asyncio.to_thread(_find_user_sync, config, username)


async def disable_user(config: dict, dn: str) -> None:
    await asyncio.to_thread(_disable_user_sync, config, dn)


async def test_connection(config: dict) -> tuple[bool, str]:
    return await asyncio.to_thread(_test_connection_sync, config)
