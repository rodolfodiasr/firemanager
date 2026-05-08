"""Fase 20 — SQL Server database audit connector (pymssql, sync via thread)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any


def _connect(host: str, port: int, database: str, username: str, password: str):
    import pymssql
    return pymssql.connect(
        server=host, port=port, database=database,
        user=username, password=password, timeout=15, login_timeout=10,
    )


def _run_sync(host: str, port: int, database: str, username: str, password: str) -> dict:
    conn = _connect(host, port, database, username, password)
    try:
        cur = conn.cursor(as_dict=True)

        cur.execute("SELECT @@VERSION AS version")
        ver = cur.fetchone()
        version = ver["version"].splitlines()[0] if ver else "unknown"

        cur.execute("""
            SELECT
                sp.name,
                sp.type_desc,
                sp.is_disabled,
                sp.create_date,
                sp.modify_date,
                ISNULL(sl.last_batch, sp.modify_date) AS last_login,
                CASE WHEN srm.role_principal_id IS NOT NULL THEN 1 ELSE 0 END AS is_sysadmin
            FROM sys.server_principals sp
            LEFT JOIN sys.syslogins sl ON sp.name = sl.name
            LEFT JOIN sys.server_role_members srm
                ON srm.member_principal_id = sp.principal_id
               AND srm.role_principal_id = SUSER_ID('sysadmin')
            WHERE sp.type IN ('S', 'U', 'G')
              AND sp.name NOT LIKE '##%'
            ORDER BY sp.name
        """)
        raw_users = cur.fetchall()

        now = datetime.now(timezone.utc)
        users: list[dict] = []
        for row in raw_users:
            ll = row.get("last_login")
            if ll and hasattr(ll, "tzinfo"):
                ll_aware = ll.replace(tzinfo=timezone.utc) if ll.tzinfo is None else ll
                days_idle = (now - ll_aware).days
            else:
                days_idle = None

            users.append({
                "name": row["name"],
                "is_superuser": bool(row.get("is_sysadmin")),
                "can_createdb": False,
                "can_createrole": bool(row.get("is_sysadmin")),
                "can_login": not bool(row.get("is_disabled")),
                "is_system": row["type_desc"] in ("WINDOWS_LOGIN", "CERTIFICATE_MAPPED_LOGIN"),
                "password_expires": None,
                "password_never_expires": False,
                "last_login": ll.isoformat() if ll else None,
                "days_since_login": days_idle,
                "type_desc": row.get("type_desc", ""),
            })

        return {"version": version, "users": users, "grants": []}
    finally:
        conn.close()


class SQLServerDbConnector:
    def __init__(self, host: str, port: int, database: str, username: str, password: str, ssl: bool = False):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password

    async def test_connection(self) -> tuple[bool, str]:
        try:
            await asyncio.to_thread(_connect, self.host, self.port, self.database, self.username, self.password)
            return True, "Conexão bem-sucedida"
        except ImportError:
            return False, "pymssql não instalado — instale com: pip install pymssql"
        except Exception as exc:
            return False, str(exc)

    async def collect_info(self) -> dict:
        return await asyncio.to_thread(
            _run_sync, self.host, self.port, self.database, self.username, self.password
        )
