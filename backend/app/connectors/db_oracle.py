"""Fase 20 — Oracle database audit connector (oracledb thin mode, sync via thread)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone


def _run_sync(host: str, port: int, database: str, username: str, password: str) -> dict:
    import oracledb
    dsn = f"{host}:{port}/{database}"
    conn = oracledb.connect(user=username, password=password, dsn=dsn)
    try:
        cur = conn.cursor()

        cur.execute("SELECT * FROM v$version WHERE banner LIKE 'Oracle%'")
        ver_row = cur.fetchone()
        version = ver_row[0] if ver_row else "unknown"

        cur.execute("""
            SELECT
                username,
                account_status,
                lock_date,
                expiry_date,
                last_login,
                profile,
                CASE WHEN account_status = 'OPEN' THEN 0 ELSE 1 END AS is_locked
            FROM dba_users
            ORDER BY username
        """)
        cols = [d[0].lower() for d in cur.description]
        raw_users = [dict(zip(cols, row)) for row in cur.fetchall()]

        cur.execute("""
            SELECT grantee, privilege, admin_option
            FROM dba_sys_privs
            WHERE grantee NOT IN (
                'SYS','SYSTEM','OUTLN','DBSNMP','APPQOSSYS',
                'DBSFWUSER','GGSYS','ANONYMOUS','CTXSYS','DVSYS',
                'DVF','GSMADMIN_INTERNAL','GSMCATUSER','GSMUSER',
                'DIP','ORDPLUGINS','ORDDATA','MDSYS','OLAPSYS',
                'SI_INFORMTN_SCHEMA','XDB','WMSYS','LBACSYS'
            )
            ORDER BY grantee
        """)
        priv_cols = [d[0].lower() for d in cur.description]
        grants = [dict(zip(priv_cols, row)) for row in cur.fetchall()]

        dba_privs = {r["grantee"] for r in grants if r.get("privilege") == "DBA"}

        now = datetime.now(timezone.utc)
        users = []
        for row in raw_users:
            ll = row.get("last_login")
            if ll and isinstance(ll, str):
                try:
                    from datetime import datetime as dt
                    ll = dt.strptime(ll, "%d-%b-%y %I.%M.%S.%f %p")
                except Exception:
                    ll = None
            days_idle = None
            if ll:
                ll_aware = ll.replace(tzinfo=timezone.utc) if hasattr(ll, "tzinfo") and ll.tzinfo is None else ll
                days_idle = (now - ll_aware).days if ll_aware else None

            is_system = row["username"] in (
                "SYS", "SYSTEM", "OUTLN", "DBSNMP", "APPQOSSYS",
                "CTXSYS", "DVSYS", "MDSYS", "XDB", "WMSYS",
            )
            users.append({
                "name": row["username"],
                "is_superuser": row["username"] in ("SYS", "SYSTEM") or row["username"] in dba_privs,
                "can_createdb": False,
                "can_createrole": row["username"] in dba_privs,
                "can_login": row.get("account_status") == "OPEN",
                "is_system": is_system,
                "password_expires": row["expiry_date"].isoformat() if row.get("expiry_date") else None,
                "password_never_expires": row.get("expiry_date") is None,
                "last_login": ll.isoformat() if ll else None,
                "days_since_login": days_idle,
                "account_status": row.get("account_status"),
                "profile": row.get("profile"),
            })

        return {"version": version, "users": users, "grants": grants}
    finally:
        conn.close()


class OracleDbConnector:
    def __init__(self, host: str, port: int, database: str, username: str, password: str, ssl: bool = False):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password

    async def test_connection(self) -> tuple[bool, str]:
        try:
            import oracledb
            oracledb.init_oracle_client()  # thin mode — no-op if already initialized
        except Exception:
            pass
        try:
            await asyncio.to_thread(
                lambda: __import__("oracledb").connect(
                    user=self.username, password=self.password,
                    dsn=f"{self.host}:{self.port}/{self.database}"
                ).close()
            )
            return True, "Conexão bem-sucedida"
        except ImportError:
            return False, "oracledb não instalado — instale com: pip install oracledb"
        except Exception as exc:
            return False, str(exc)

    async def collect_info(self) -> dict:
        return await asyncio.to_thread(
            _run_sync, self.host, self.port, self.database, self.username, self.password
        )
