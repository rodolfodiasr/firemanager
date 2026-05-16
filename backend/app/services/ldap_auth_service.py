"""LDAP authentication service — validates user credentials against on-premises AD.

Flow:
  1. Find the tenant's SsoConfig with provider="ldap" and extra_config populated.
  2. Bind as service account to locate the user's DN.
  3. Re-bind as the user to verify the password.
  4. Return user info + optional group → role mapping.
"""
from __future__ import annotations

import asyncio
import ssl
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


# ── Internal sync helpers ─────────────────────────────────────────────────────

def _bind_and_lookup_sync(ldap_cfg: dict, login: str, password: str) -> dict | None:
    """
    Performs a two-step LDAP bind:
      1. Service account bind → find user DN.
      2. User bind → verify credentials.

    ldap_cfg keys expected:
      ldap_url, base_dn, bind_user, bind_password (plaintext at this point),
      user_filter (optional), group_mapping (optional dict CN→role).

    Returns dict(dn, display_name, groups, mapped_role) or None on failure.
    """
    from ldap3 import Connection, Server, SIMPLE, SUBTREE, Tls

    raw_url: str = ldap_cfg.get("ldap_url", "ldap://localhost")
    use_ssl = raw_url.startswith("ldaps://")
    host = raw_url.replace("ldaps://", "").replace("ldap://", "").split(":")[0]
    port = int(ldap_cfg.get("port", 636 if use_ssl else 389))
    base_dn: str = ldap_cfg["base_dn"]
    bind_user: str = ldap_cfg["bind_user"]
    bind_pass: str = ldap_cfg["bind_password"]
    user_filter_tpl: str = ldap_cfg.get(
        "user_filter",
        "(|(mail={login})(sAMAccountName={login})(userPrincipalName={login}))",
    )
    group_mapping: dict = ldap_cfg.get("group_mapping") or {}

    tls = Tls(validate=ssl.CERT_NONE) if use_ssl else None
    server = Server(host, port=port, use_ssl=use_ssl, tls=tls)

    # Step 1: service account bind to find the user's DN
    try:
        svc = Connection(
            server, user=bind_user, password=bind_pass,
            authentication=SIMPLE, auto_bind=True,
        )
    except Exception:
        return None

    escaped = login.translate(str.maketrans({
        "*": "\\2a", "(": "\\28", ")": "\\29", "\\": "\\5c", "\x00": "\\00",
    }))
    svc.search(
        search_base=base_dn,
        search_filter=user_filter_tpl.replace("{login}", escaped),
        search_scope=SUBTREE,
        attributes=["distinguishedName", "displayName", "memberOf", "userAccountControl"],
    )
    if not svc.entries:
        svc.unbind()
        return None

    entry = svc.entries[0]
    user_dn: str = str(entry.distinguishedName)
    display_name: str | None = (
        str(entry.displayName.value) if entry.displayName else None
    )
    raw_groups = entry.memberOf.values if entry.memberOf else []
    group_cns = [g.split(",")[0].replace("CN=", "") for g in raw_groups]
    svc.unbind()

    # Step 2: re-bind as the user to verify the supplied password
    try:
        usr = Connection(
            server, user=user_dn, password=password,
            authentication=SIMPLE, auto_bind=True,
        )
        usr.unbind()
    except Exception:
        return None  # bad password or account locked

    # Map AD groups to platform role (first match wins)
    mapped_role: str | None = None
    for cn in group_cns:
        if cn in group_mapping:
            mapped_role = group_mapping[cn]
            break

    return {
        "dn": user_dn,
        "display_name": display_name,
        "groups": group_cns,
        "mapped_role": mapped_role,
    }


# ── Async public API ──────────────────────────────────────────────────────────

async def _get_ldap_config(db: AsyncSession, tenant_id: UUID) -> dict | None:
    """Returns the decrypted LDAP extra_config dict for the tenant, or None."""
    from app.models.edge_agents import SsoConfig

    result = await db.execute(
        select(SsoConfig).where(
            SsoConfig.tenant_id == tenant_id,
            SsoConfig.provider == "ldap",
            SsoConfig.is_active.is_(True),
        )
    )
    sso = result.scalar_one_or_none()
    if sso is None or not sso.extra_config:
        return None

    cfg = dict(sso.extra_config)

    # Decrypt bind_password_encrypted if present
    raw = cfg.pop("bind_password_encrypted", None)
    if raw:
        try:
            from cryptography.fernet import Fernet
            from app.config import settings
            key = settings.fernet_key
            if isinstance(key, str):
                key = key.encode()
            cfg["bind_password"] = Fernet(key).decrypt(raw.encode()).decode()
        except Exception:
            cfg["bind_password"] = raw  # fallback: use as-is (dev/test)
    else:
        cfg.setdefault("bind_password", "")

    return cfg


async def authenticate_ldap(
    db: AsyncSession,
    tenant_id: UUID,
    email: str,
    password: str,
) -> dict | None:
    """
    Authenticates *email* against the tenant's LDAP server.

    Returns dict(dn, display_name, groups, mapped_role) on success,
    or None if config is missing or credentials are invalid.
    """
    cfg = await _get_ldap_config(db, tenant_id)
    if cfg is None:
        return None
    return await asyncio.to_thread(_bind_and_lookup_sync, cfg, email, password)
