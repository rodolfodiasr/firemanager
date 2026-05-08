"""Fase 20 — MySQL/MariaDB database audit connector."""
from __future__ import annotations

from datetime import datetime, timezone


class MySQLDbConnector:
    def __init__(self, host: str, port: int, database: str, username: str, password: str, ssl: bool = False):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.ssl = ssl

    async def test_connection(self) -> tuple[bool, str]:
        try:
            import aiomysql
            conn = await aiomysql.connect(
                host=self.host, port=self.port, db=self.database,
                user=self.username, password=self.password,
                ssl=self.ssl, connect_timeout=10,
            )
            conn.close()
            return True, "Conexão bem-sucedida"
        except ImportError:
            return False, "aiomysql não instalado — instale com: pip install aiomysql"
        except Exception as exc:
            return False, str(exc)

    async def collect_info(self) -> dict:
        import aiomysql
        conn = await aiomysql.connect(
            host=self.host, port=self.port, db=self.database,
            user=self.username, password=self.password,
            ssl=self.ssl, connect_timeout=15,
        )
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT VERSION() AS version")
                ver = await cur.fetchone()
                version = ver["version"] if ver else "unknown"

                await cur.execute("""
                    SELECT
                        User                 AS name,
                        Host                 AS host,
                        password_expired     AS password_expired,
                        account_locked       AS is_locked,
                        Password_lifetime    AS password_lifetime,
                        password_last_changed AS password_last_changed
                    FROM mysql.user
                    ORDER BY User
                """)
                raw_users = await cur.fetchall()

                await cur.execute("""
                    SELECT User, Host, Super_priv, Create_user_priv,
                           Grant_priv, Repl_slave_priv
                    FROM mysql.user
                """)
                priv_rows = await cur.fetchall()
                priv_map = {(r["User"], r["Host"]): r for r in priv_rows}

            users = []
            now = datetime.now(timezone.utc)
            for row in raw_users:
                key = (row["name"], row["host"])
                privs = priv_map.get(key, {})
                is_superuser = privs.get("Super_priv") == "Y"
                plc = row.get("password_last_changed")
                days_idle = None
                if plc:
                    plc_aware = plc.replace(tzinfo=timezone.utc) if hasattr(plc, "tzinfo") and plc.tzinfo is None else plc
                    days_idle = (now - plc_aware).days if plc_aware else None

                users.append({
                    "name": f"{row['name']}@{row['host']}",
                    "is_superuser": is_superuser,
                    "can_createdb": False,
                    "can_createrole": privs.get("Create_user_priv") == "Y",
                    "can_login": row.get("is_locked") != "Y",
                    "is_system": row["name"] in ("mysql.sys", "mysql.session", "mysql.infoschema"),
                    "password_expires": None,
                    "password_never_expires": (row.get("password_lifetime") is None),
                    "last_login": plc.isoformat() if plc else None,
                    "days_since_login": days_idle,
                    "password_expired": row.get("password_expired") == "Y",
                    "is_locked": row.get("is_locked") == "Y",
                })

            return {"version": version, "users": users, "grants": []}
        finally:
            conn.close()
