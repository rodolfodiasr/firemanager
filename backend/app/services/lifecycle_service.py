"""Lifecycle orchestration: discovery and offboarding execution."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import (
    IdentityProvider, LifecycleAction, LifecycleTask,
    ActionStatus, ProviderType, SystemType, TaskStatus,
)
from app.models.server import Server, ServerOsType
from app.utils.crypto import decrypt_credentials


# ── Discovery ─────────────────────────────────────────────────────────────────

async def discover_user_accesses(
    db: AsyncSession, tenant_id, action: LifecycleAction
) -> list[LifecycleTask]:
    username = action.target_username
    tasks: list[LifecycleTask] = []

    # 1. Identity providers (Azure AD, Google Workspace)
    providers = (await db.execute(
        select(IdentityProvider).where(
            IdentityProvider.tenant_id == tenant_id,
            IdentityProvider.is_active.is_(True),
        )
    )).scalars().all()

    for provider in providers:
        found = await _check_identity_provider(provider, username)
        if found:
            if provider.provider_type == ProviderType.azure_ad:
                stype = SystemType.azure_ad
            elif provider.provider_type == ProviderType.google_workspace:
                stype = SystemType.google_workspace
            else:
                stype = SystemType.local_ad
            tasks.append(LifecycleTask(
                id=uuid4(),
                action_id=action.id,
                system_type=stype,
                system_id=str(provider.id),
                system_name=provider.name,
                status=TaskStatus.pending,
            ))

    # 2. Linux servers (SSH)
    servers = (await db.execute(
        select(Server).where(Server.tenant_id == tenant_id, Server.is_active.is_(True))
    )).scalars().all()

    check_tasks = []
    for server in servers:
        check_tasks.append(_check_ssh_user(server, username))
    ssh_results = await asyncio.gather(*check_tasks, return_exceptions=True)

    for server, found in zip(servers, ssh_results):
        if server.os_type == ServerOsType.linux and found is True:
            tasks.append(LifecycleTask(
                id=uuid4(),
                action_id=action.id,
                system_type=SystemType.ssh_linux,
                system_id=str(server.id),
                system_name=server.name,
                status=TaskStatus.pending,
            ))
        elif server.os_type == ServerOsType.windows and found is True:
            tasks.append(LifecycleTask(
                id=uuid4(),
                action_id=action.id,
                system_type=SystemType.winrm_windows,
                system_id=str(server.id),
                system_name=server.name,
                status=TaskStatus.pending,
            ))

    # 3. Database connectors
    from app.models.database_connector import DatabaseConnector
    connectors = (await db.execute(
        select(DatabaseConnector).where(
            DatabaseConnector.tenant_id == tenant_id,
            DatabaseConnector.is_active.is_(True),
        )
    )).scalars().all()

    db_checks = [_check_db_user(c, username) for c in connectors]
    db_results = await asyncio.gather(*db_checks, return_exceptions=True)

    for connector, found in zip(connectors, db_results):
        if found is True:
            tasks.append(LifecycleTask(
                id=uuid4(),
                action_id=action.id,
                system_type=SystemType.database,
                system_id=str(connector.id),
                system_name=connector.name,
                status=TaskStatus.pending,
            ))

    return tasks


async def _check_identity_provider(provider: IdentityProvider, username: str) -> bool:
    try:
        config = decrypt_credentials(provider.encrypted_config)
        if provider.provider_type == ProviderType.azure_ad:
            from app.services.azure_ad_service import find_user
        elif provider.provider_type == ProviderType.google_workspace:
            from app.services.google_workspace_service import find_user
        else:
            from app.services.local_ad_service import find_user
        user = await find_user(config, username)
        return user is not None
    except Exception:
        return False


async def _check_ssh_user(server: Server, username: str) -> bool:
    if server.os_type != ServerOsType.linux:
        return False
    try:
        creds = decrypt_credentials(server.encrypted_credentials)
        from app.connectors.ssh_linux import SshLinuxConnector
        conn = SshLinuxConnector(
            host=server.host,
            port=server.ssh_port,
            username=creds.get("username", "root"),
            password=creds.get("password", ""),
            private_key=creds.get("private_key", ""),
            timeout=10,
        )
        out, _ = await conn.run_commands([f"id {username} 2>/dev/null && echo __EXISTS__ || echo __NOT_FOUND__"])
        return "__EXISTS__" in out
    except Exception:
        return False


async def _check_winrm_user(server: Server, username: str) -> bool:
    if server.os_type != ServerOsType.windows:
        return False
    try:
        creds = decrypt_credentials(server.encrypted_credentials)
        from app.connectors.winrm_windows import WinRMConnector
        conn = WinRMConnector(
            host=server.host,
            port=server.ssh_port,
            username=creds.get("username", "Administrator"),
            password=creds.get("password", ""),
            auth_type=creds.get("auth_type", "ntlm"),
            verify_ssl=creds.get("verify_ssl", False),
        )
        script = f"try{{Get-LocalUser -Name '{username}' -EA Stop;Write-Output '__EXISTS__'}}catch{{Write-Output '__NOT_FOUND__'}}"
        out, _ = await conn.run_commands([script])
        return "__EXISTS__" in out
    except Exception:
        return False


async def _check_db_user(connector, username: str) -> bool:
    try:
        creds = decrypt_credentials(connector.encrypted_credentials)
        users = await _collect_db_usernames(connector, creds)
        return any(u.lower() == username.lower() for u in users)
    except Exception:
        return False


async def _collect_db_usernames(connector, creds: dict) -> list[str]:
    db_type = connector.db_type if isinstance(connector.db_type, str) else connector.db_type.value
    host = connector.host
    port = connector.port
    db_name = connector.database_name
    user = creds.get("username", "")
    pwd = creds.get("password", "")

    if db_type == "postgresql":
        import asyncpg
        conn = await asyncpg.connect(host=host, port=port, database=db_name, user=user, password=pwd, timeout=8)
        try:
            rows = await conn.fetch("SELECT rolname FROM pg_roles WHERE rolcanlogin")
            return [r["rolname"] for r in rows]
        finally:
            await conn.close()

    elif db_type in ("mysql", "mariadb"):
        import aiomysql
        conn = await aiomysql.connect(host=host, port=port, db=db_name, user=user, password=pwd, connect_timeout=8)
        try:
            async with conn.cursor() as cur:
                await cur.execute("SELECT User FROM mysql.user")
                rows = await cur.fetchall()
                return [r[0] for r in rows]
        finally:
            conn.close()

    elif db_type == "sqlserver":
        import pymssql

        def _q():
            c = pymssql.connect(host, user, pwd, db_name)
            try:
                cur = c.cursor()
                cur.execute("SELECT name FROM sys.server_principals WHERE type_desc IN ('SQL_LOGIN','WINDOWS_LOGIN')")
                return [r[0] for r in cur.fetchall()]
            finally:
                c.close()

        return await asyncio.to_thread(_q)

    elif db_type == "oracle":
        import oracledb

        def _q():
            c = oracledb.connect(user=user, password=pwd, dsn=f"{host}:{port}/{db_name}")
            try:
                cur = c.cursor()
                cur.execute("SELECT username FROM dba_users WHERE account_status = 'OPEN'")
                return [r[0] for r in cur.fetchall()]
            finally:
                c.close()

        return await asyncio.to_thread(_q)

    return []


# ── Execution ─────────────────────────────────────────────────────────────────

async def run_offboarding(db: AsyncSession, action: LifecycleAction) -> None:
    action.status = ActionStatus.running
    await db.flush()

    for task in action.tasks:
        await _execute_task(db, task, action.target_username)
        await db.flush()

    all_ok = all(
        t.status in (TaskStatus.success, TaskStatus.not_found, TaskStatus.skipped)
        for t in action.tasks
    )
    action.status = ActionStatus.completed if all_ok else ActionStatus.failed
    action.completed_at = datetime.now(timezone.utc)
    await db.commit()


async def _execute_task(db: AsyncSession, task: LifecycleTask, username: str) -> None:
    task.status = TaskStatus.running
    task.executed_at = datetime.now(timezone.utc)

    try:
        if task.system_type == SystemType.azure_ad:
            ok, msg = await _revoke_azure(db, task.system_id, username)
        elif task.system_type == SystemType.google_workspace:
            ok, msg = await _revoke_google(db, task.system_id, username)
        elif task.system_type == SystemType.local_ad:
            ok, msg = await _revoke_local_ad(db, task.system_id, username)
        elif task.system_type == SystemType.ssh_linux:
            ok, msg = await _revoke_ssh(db, task.system_id, username)
        elif task.system_type == SystemType.winrm_windows:
            ok, msg = await _revoke_winrm(db, task.system_id, username)
        elif task.system_type == SystemType.database:
            ok, msg = await _revoke_db(db, task.system_id, username)
        else:
            ok, msg = False, "Tipo de sistema não suportado"
    except Exception as e:
        ok, msg = False, str(e)

    if ok:
        task.status = TaskStatus.success
        task.result = msg
    else:
        task.status = TaskStatus.failed
        task.error = msg


async def _revoke_local_ad(db: AsyncSession, provider_id: str, username: str) -> tuple[bool, str]:
    from uuid import UUID
    provider = await db.get(IdentityProvider, UUID(provider_id))
    if not provider:
        return False, "Provider não encontrado"
    config = decrypt_credentials(provider.encrypted_config)
    from app.services.local_ad_service import find_user, disable_user
    user = await find_user(config, username)
    if not user:
        return True, "Usuário não encontrado no AD Local (já removido ou inexistente)"
    await disable_user(config, user["dn"])
    name = user.get("display_name") or username
    return True, f"Conta '{name}' desabilitada no Active Directory Local"


async def _revoke_azure(db: AsyncSession, provider_id: str, username: str) -> tuple[bool, str]:
    from uuid import UUID
    provider = await db.get(IdentityProvider, UUID(provider_id))
    if not provider:
        return False, "Provider não encontrado"
    config = decrypt_credentials(provider.encrypted_config)
    from app.services.azure_ad_service import find_user, disable_user
    user = await find_user(config, username)
    if not user:
        return True, "Usuário não encontrado no Azure AD (já removido)"
    await disable_user(config, user["id"])
    return True, f"Conta desabilitada e sessões revogadas no Azure AD"


async def _revoke_google(db: AsyncSession, provider_id: str, username: str) -> tuple[bool, str]:
    from uuid import UUID
    provider = await db.get(IdentityProvider, UUID(provider_id))
    if not provider:
        return False, "Provider não encontrado"
    config = decrypt_credentials(provider.encrypted_config)
    from app.services.google_workspace_service import find_user, suspend_user
    user = await find_user(config, username)
    if not user:
        return True, "Usuário não encontrado no Google Workspace (já removido)"
    await suspend_user(config, user["id"])
    return True, "Conta suspensa no Google Workspace"


async def _revoke_ssh(db: AsyncSession, server_id: str, username: str) -> tuple[bool, str]:
    from uuid import UUID
    server = await db.get(Server, UUID(server_id))
    if not server:
        return False, "Servidor não encontrado"
    creds = decrypt_credentials(server.encrypted_credentials)
    from app.connectors.ssh_linux import SshLinuxConnector
    conn = SshLinuxConnector(
        host=server.host,
        port=server.ssh_port,
        username=creds.get("username", "root"),
        password=creds.get("password", ""),
        private_key=creds.get("private_key", ""),
        timeout=15,
    )
    out, ok = await conn.run_commands([
        f"usermod -L {username} 2>&1 || true",
        f"pkill -KILL -u {username} 2>/dev/null || true",
        "echo __DONE__",
    ])
    if "__DONE__" in out:
        return True, f"Usuário {username} bloqueado em {server.name}"
    return False, out


async def _revoke_winrm(db: AsyncSession, server_id: str, username: str) -> tuple[bool, str]:
    from uuid import UUID
    server = await db.get(Server, UUID(server_id))
    if not server:
        return False, "Servidor não encontrado"
    creds = decrypt_credentials(server.encrypted_credentials)
    from app.connectors.winrm_windows import WinRMConnector
    conn = WinRMConnector(
        host=server.host,
        port=server.ssh_port,
        username=creds.get("username", "Administrator"),
        password=creds.get("password", ""),
        auth_type=creds.get("auth_type", "ntlm"),
        verify_ssl=creds.get("verify_ssl", False),
    )
    script = (
        f"try{{Disable-LocalUser -Name '{username}' -EA Stop;"
        "Write-Output '__DONE__'}}"
        f"catch{{Write-Output \"ERRO: $_\"}}"
    )
    out, _ = await conn.run_commands([script])
    if "__DONE__" in out:
        return True, f"Usuário {username} desabilitado em {server.name}"
    return False, out


async def _revoke_db(db: AsyncSession, connector_id: str, username: str) -> tuple[bool, str]:
    from uuid import UUID
    from app.models.database_connector import DatabaseConnector
    connector = await db.get(DatabaseConnector, UUID(connector_id))
    if not connector:
        return False, "Conector não encontrado"
    creds = decrypt_credentials(connector.encrypted_credentials)
    db_type = connector.db_type if isinstance(connector.db_type, str) else connector.db_type.value
    host, port, db_name = connector.host, connector.port, connector.database_name
    adm_user, adm_pass = creds.get("username", ""), creds.get("password", "")

    try:
        if db_type == "postgresql":
            import asyncpg
            conn = await asyncpg.connect(host=host, port=port, database=db_name, user=adm_user, password=adm_pass)
            try:
                await conn.execute(f'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM "{username}"')
                await conn.execute(f'DROP USER IF EXISTS "{username}"')
            finally:
                await conn.close()
            return True, f"Usuário {username} removido do PostgreSQL {connector.name}"

        elif db_type in ("mysql", "mariadb"):
            import aiomysql
            conn = await aiomysql.connect(host=host, port=port, db=db_name, user=adm_user, password=adm_pass)
            try:
                async with conn.cursor() as cur:
                    await cur.execute(f"DROP USER IF EXISTS '{username}'@'%'")
                await conn.commit()
            finally:
                conn.close()
            return True, f"Usuário {username} removido do MySQL/MariaDB {connector.name}"

        elif db_type == "sqlserver":
            import pymssql

            def _drop():
                c = pymssql.connect(host, adm_user, adm_pass, db_name)
                try:
                    cur = c.cursor()
                    cur.execute(
                        "IF EXISTS (SELECT 1 FROM sys.server_principals WHERE name=%s)"
                        f" ALTER LOGIN [{username}] DISABLE",
                        (username,),
                    )
                    c.commit()
                finally:
                    c.close()

            await asyncio.to_thread(_drop)
            return True, f"Login {username} desabilitado no SQL Server {connector.name}"

        elif db_type == "oracle":
            import oracledb

            def _lock():
                c = oracledb.connect(user=adm_user, password=adm_pass, dsn=f"{host}:{port}/{db_name}")
                try:
                    cur = c.cursor()
                    cur.execute(f"ALTER USER {username} ACCOUNT LOCK")
                    c.commit()
                finally:
                    c.close()

            await asyncio.to_thread(_lock)
            return True, f"Usuário {username} bloqueado no Oracle {connector.name}"

        return False, "Tipo de banco não suportado"
    except Exception as e:
        return False, str(e)
