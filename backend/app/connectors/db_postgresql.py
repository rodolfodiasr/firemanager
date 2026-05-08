"""Fase 20 — PostgreSQL database audit connector."""
from __future__ import annotations

from datetime import datetime, timezone


class PostgreSQLDbConnector:
    def __init__(self, host: str, port: int, database: str, username: str, password: str, ssl: bool = False):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.ssl = ssl

    async def test_connection(self) -> tuple[bool, str]:
        try:
            import asyncpg
            conn = await asyncpg.connect(
                host=self.host, port=self.port, database=self.database,
                user=self.username, password=self.password,
                ssl="require" if self.ssl else "disable",
                timeout=10,
            )
            await conn.close()
            return True, "Conexão bem-sucedida"
        except Exception as exc:
            return False, str(exc)

    async def collect_info(self) -> dict:
        import asyncpg
        conn = await asyncpg.connect(
            host=self.host, port=self.port, database=self.database,
            user=self.username, password=self.password,
            ssl="require" if self.ssl else "disable",
            timeout=15,
        )
        try:
            version_row = await conn.fetchrow("SELECT version()")
            version = version_row[0] if version_row else "unknown"

            user_rows = await conn.fetch("""
                SELECT
                    r.rolname            AS name,
                    r.rolsuper           AS is_superuser,
                    r.rolcreatedb        AS can_createdb,
                    r.rolcreaterole      AS can_createrole,
                    r.rolcanlogin        AS can_login,
                    r.rolpassword IS NOT NULL AS has_password,
                    r.rolvaliduntil      AS password_expires,
                    r.rolname LIKE 'pg_%' AS is_system
                FROM pg_roles r
                ORDER BY r.rolname
            """)

            last_login_rows = await conn.fetch("""
                SELECT usename, backend_start
                FROM pg_stat_activity
                WHERE backend_start IS NOT NULL
                GROUP BY usename, backend_start
                ORDER BY backend_start DESC
            """)
            last_login_map: dict[str, datetime] = {}
            for row in last_login_rows:
                name = row["usename"]
                if name and name not in last_login_map:
                    last_login_map[name] = row["backend_start"]

            users = []
            for row in user_rows:
                name = row["name"]
                expires = row["password_expires"]
                ll = last_login_map.get(name)
                now = datetime.now(timezone.utc)
                days_idle = None
                if ll:
                    ll_aware = ll.replace(tzinfo=timezone.utc) if ll.tzinfo is None else ll
                    days_idle = (now - ll_aware).days

                users.append({
                    "name": name,
                    "is_superuser": bool(row["is_superuser"]),
                    "can_createdb": bool(row["can_createdb"]),
                    "can_createrole": bool(row["can_createrole"]),
                    "can_login": bool(row["can_login"]),
                    "is_system": bool(row["is_system"]),
                    "password_expires": expires.isoformat() if expires else None,
                    "password_never_expires": expires is None and bool(row["can_login"]),
                    "last_login": ll.isoformat() if ll else None,
                    "days_since_login": days_idle,
                })

            grant_rows = await conn.fetch("""
                SELECT grantee, table_schema, table_name, privilege_type
                FROM information_schema.role_table_grants
                WHERE grantee NOT IN ('PUBLIC', 'postgres')
                  AND table_schema NOT IN ('pg_catalog', 'information_schema')
                LIMIT 200
            """)
            grants = [dict(r) for r in grant_rows]

            return {"version": version, "users": users, "grants": grants}
        finally:
            await conn.close()
