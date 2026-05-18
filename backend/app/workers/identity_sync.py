"""Celery tasks — sincronização de inventário AD/M365 (F36)."""
from __future__ import annotations

import structlog
from celery import shared_task

log = structlog.get_logger()


@shared_task(name="identity_sync.sync_connector", bind=True, max_retries=2)
def sync_identity_connector(self, connector_id: str) -> dict:
    """Sincroniza usuários e grupos de um IdentityConnector específico."""
    import asyncio
    from uuid import UUID

    async def _run() -> dict:
        from app.database import AsyncSessionLocal
        from app.models.identity_governance import IdentityConnector, AdUser, AdGroup, AdGroupMembership
        from app.services import local_ad_service as ldap
        from app.utils.crypto import decrypt_credentials
        from sqlalchemy import select, delete
        from datetime import datetime, timezone

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(IdentityConnector).where(IdentityConnector.id == UUID(connector_id))
            )
            conn = result.scalar_one_or_none()
            if not conn:
                return {"error": "Conector não encontrado"}

            config = decrypt_credentials(conn.config_encrypted)
            tenant_id = conn.tenant_id
            now = datetime.now(timezone.utc)

            try:
                # Sync users
                raw_users = await ldap.list_users(config)
                # Limpar usuários antigos e recriar (delta simples)
                await db.execute(delete(AdUser).where(AdUser.connector_id == conn.id))
                await db.flush()

                for u in raw_users:
                    ad_user = AdUser(
                        tenant_id=tenant_id,
                        connector_id=conn.id,
                        source=conn.source,
                        upn=u.get("username") or u.get("dn", ""),
                        sam_account=u.get("username"),
                        display_name=u.get("display_name"),
                        email=u.get("email"),
                        department=u.get("department"),
                        job_title=u.get("job_title"),
                        is_enabled=u.get("is_enabled", True),
                        synced_at=now,
                    )
                    db.add(ad_user)

                # Sync groups
                raw_groups = await ldap.list_groups(config)
                await db.execute(delete(AdGroup).where(AdGroup.connector_id == conn.id))
                await db.flush()

                for g in raw_groups:
                    ad_group = AdGroup(
                        tenant_id=tenant_id,
                        connector_id=conn.id,
                        source=conn.source,
                        display_name=g.get("name", ""),
                        dn=g.get("dn"),
                        member_count=g.get("member_count", 0),
                        synced_at=now,
                    )
                    db.add(ad_group)

                conn.last_sync_at = now
                conn.last_sync_status = "success"
                conn.last_sync_error = None
                await db.commit()

                log.info("identity_sync.completed", connector_id=connector_id, users=len(raw_users), groups=len(raw_groups))
                return {"users": len(raw_users), "groups": len(raw_groups)}

            except Exception as exc:
                conn.last_sync_at = now
                conn.last_sync_status = "error"
                conn.last_sync_error = str(exc)[:500]
                await db.commit()
                log.error("identity_sync.failed", connector_id=connector_id, error=str(exc))
                raise

    return asyncio.run(_run())


@shared_task(name="identity_sync.expire_jit", bind=True)
def expire_jit_requests(self) -> dict:
    """Revoga JIT requests expirados. Celery beat a cada minuto."""
    import asyncio

    async def _run() -> dict:
        from app.database import AsyncSessionLocal
        from app.services.ad_governance_service import jit_expire_check

        async with AsyncSessionLocal() as db:
            count = await jit_expire_check(db)
            if count:
                log.info("jit_expire.revoked", count=count)
            return {"revoked": count}

    return asyncio.run(_run())


@shared_task(name="identity_sync.check_sod_all", bind=True)
def check_sod_all_tenants(self) -> dict:
    """Verifica violações de SoD em todos os tenants ativos. Celery beat diário."""
    import asyncio

    async def _run() -> dict:
        from app.database import AsyncSessionLocal
        from app.models.identity_governance import IdentityConnector, AdUser, AdGroupMembership, AdGroup
        from app.services.ad_governance_service import sod_check_user
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            connectors_result = await db.execute(
                select(IdentityConnector).where(IdentityConnector.is_active.is_(True))
            )
            connectors = connectors_result.scalars().all()
            total_violations = 0

            for conn in connectors:
                users_result = await db.execute(
                    select(AdUser).where(AdUser.connector_id == conn.id, AdUser.is_enabled.is_(True))
                )
                users = users_result.scalars().all()

                for user in users:
                    # Obter grupos do usuário via memberships
                    memberships_result = await db.execute(
                        select(AdGroup.display_name)
                        .join(AdGroupMembership, AdGroupMembership.group_id == AdGroup.id)
                        .where(AdGroupMembership.user_id == user.id)
                    )
                    groups = [row[0] for row in memberships_result.all()]
                    violations = await sod_check_user(db, conn.tenant_id, user.id, groups)
                    total_violations += len(violations)

            log.info("sod_check.completed", violations=total_violations)
            return {"violations_detected": total_violations}

    return asyncio.run(_run())
