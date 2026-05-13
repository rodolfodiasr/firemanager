"""Service — F39.cont Self-Service Portal: AD reports + catalog CRUD."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.selfservice_portal import AccessCatalogItem, AccessRequest


# ── Access Catalog ────────────────────────────────────────────────────────────

async def list_catalog(
    db: AsyncSession, tenant_id: uuid.UUID, category: str | None = None
) -> list[AccessCatalogItem]:
    q = (
        select(AccessCatalogItem)
        .where(AccessCatalogItem.tenant_id == tenant_id, AccessCatalogItem.is_active == True)
    )
    if category:
        q = q.where(AccessCatalogItem.category == category)
    q = q.order_by(AccessCatalogItem.sort_order, AccessCatalogItem.name)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_catalog_item(
    db: AsyncSession, tenant_id: uuid.UUID, item_id: uuid.UUID
) -> AccessCatalogItem | None:
    result = await db.execute(
        select(AccessCatalogItem).where(
            AccessCatalogItem.id == item_id,
            AccessCatalogItem.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_catalog_item(
    db: AsyncSession, tenant_id: uuid.UUID, data: dict
) -> AccessCatalogItem:
    obj = AccessCatalogItem(tenant_id=tenant_id, **data)
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    await db.commit()
    return obj


async def update_catalog_item(
    db: AsyncSession, item: AccessCatalogItem, data: dict
) -> AccessCatalogItem:
    for k, v in data.items():
        setattr(item, k, v)
    await db.flush()
    await db.refresh(item)
    await db.commit()
    return item


# ── Access Requests ───────────────────────────────────────────────────────────

async def list_access_requests(
    db: AsyncSession, tenant_id: uuid.UUID, status: str | None = None, limit: int = 100
) -> list[AccessRequest]:
    q = select(AccessRequest).where(AccessRequest.tenant_id == tenant_id)
    if status:
        q = q.where(AccessRequest.status == status)
    q = q.order_by(AccessRequest.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_access_request(
    db: AsyncSession, tenant_id: uuid.UUID, request_id: uuid.UUID
) -> AccessRequest | None:
    result = await db.execute(
        select(AccessRequest).where(
            AccessRequest.id == request_id, AccessRequest.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def submit_access_request(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    catalog_item_id: uuid.UUID,
    requester_email: str,
    requester_name: str | None,
    justification: str | None,
) -> AccessRequest:
    item = await get_catalog_item(db, tenant_id, catalog_item_id)
    if not item:
        raise ValueError("Item do catálogo não encontrado")
    obj = AccessRequest(
        tenant_id=tenant_id,
        catalog_item_id=catalog_item_id,
        item_name=item.name,
        requester_email=requester_email,
        requester_name=requester_name,
        business_justification=justification,
        status="pending" if item.approval_required else "approved",
    )
    if not item.approval_required:
        obj.provisioned_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    await db.commit()
    return obj


async def approve_access_request(
    db: AsyncSession, req: AccessRequest, approver_id: uuid.UUID
) -> AccessRequest:
    req.status = "approved"
    req.approved_by = approver_id
    req.approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    req.provisioned_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()
    await db.refresh(req)
    await db.commit()
    return req


async def reject_access_request(
    db: AsyncSession, req: AccessRequest, approver_id: uuid.UUID, reason: str
) -> AccessRequest:
    req.status = "rejected"
    req.approved_by = approver_id
    req.approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    req.rejection_reason = reason
    await db.flush()
    await db.refresh(req)
    await db.commit()
    return req


# ── AD Reports ────────────────────────────────────────────────────────────────

async def report_expired_passwords(
    db: AsyncSession, tenant_id: uuid.UUID, max_age_days: int = 90
) -> list[dict]:
    """Users whose password hasn't been changed in max_age_days (from ad_users)."""
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT u.display_name, u.sam_account_name, u.email,
                   u.password_last_set, u.is_enabled,
                   EXTRACT(DAY FROM NOW() - u.password_last_set)::int AS days_since_change
            FROM ad_users u
            JOIN identity_connectors c ON c.id = u.connector_id
            WHERE c.tenant_id = :tid
              AND u.is_enabled = true
              AND u.password_last_set IS NOT NULL
              AND u.password_last_set < NOW() - INTERVAL ':days days'
            ORDER BY u.password_last_set ASC
            LIMIT 500
        """.replace(":days days", f"{max_age_days} days")),
        {"tid": tenant_id},
    )
    return [dict(row._mapping) for row in result.all()]


async def report_inactive_accounts(
    db: AsyncSession, tenant_id: uuid.UUID, inactive_days: int = 60
) -> list[dict]:
    """Enabled accounts with last_logon more than inactive_days ago."""
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT u.display_name, u.sam_account_name, u.email,
                   u.last_logon, u.is_enabled,
                   EXTRACT(DAY FROM NOW() - u.last_logon)::int AS days_inactive
            FROM ad_users u
            JOIN identity_connectors c ON c.id = u.connector_id
            WHERE c.tenant_id = :tid
              AND u.is_enabled = true
              AND u.last_logon IS NOT NULL
              AND u.last_logon < NOW() - INTERVAL ':days days'
            ORDER BY u.last_logon ASC
            LIMIT 500
        """.replace(":days days", f"{inactive_days} days")),
        {"tid": tenant_id},
    )
    return [dict(row._mapping) for row in result.all()]


async def report_admins_without_mfa(db: AsyncSession, tenant_id: uuid.UUID) -> list[dict]:
    """Admin users (in privileged groups) who have MFA disabled."""
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT DISTINCT u.display_name, u.sam_account_name, u.email,
                   u.is_enabled, u.last_logon
            FROM ad_users u
            JOIN ad_group_memberships m ON m.user_id = u.id
            JOIN ad_groups g ON g.id = m.group_id
            JOIN identity_connectors c ON c.id = u.connector_id
            WHERE c.tenant_id = :tid
              AND u.is_enabled = true
              AND (u.mfa_enabled IS NULL OR u.mfa_enabled = false)
              AND (
                g.name ILIKE '%admin%'
                OR g.name ILIKE '%Domain Admins%'
                OR g.name ILIKE '%Enterprise Admins%'
              )
            ORDER BY u.display_name
            LIMIT 200
        """),
        {"tid": tenant_id},
    )
    return [dict(row._mapping) for row in result.all()]


async def report_group_members(
    db: AsyncSession, tenant_id: uuid.UUID, group_name: str
) -> list[dict]:
    """List all members of a specific AD group."""
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT u.display_name, u.sam_account_name, u.email,
                   u.is_enabled, u.last_logon, u.job_title
            FROM ad_users u
            JOIN ad_group_memberships m ON m.user_id = u.id
            JOIN ad_groups g ON g.id = m.group_id
            JOIN identity_connectors c ON c.id = u.connector_id
            WHERE c.tenant_id = :tid
              AND g.name ILIKE :group_name
            ORDER BY u.display_name
            LIMIT 1000
        """),
        {"tid": tenant_id, "group_name": f"%{group_name}%"},
    )
    return [dict(row._mapping) for row in result.all()]
