"""Permission resolution service.

Single source of truth for determining a user's effective role on a device.
Resolution order: category-specific role > tenant-wide role > None (deny).
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import DeviceCategory
from app.models.user_device_category_role import UserDeviceCategoryRole
from app.models.user_tenant_role import TenantRole, UserTenantRole


async def resolve_device_role(
    db: AsyncSession,
    user_id: UUID,
    tenant_id: UUID,
    device_category: DeviceCategory,
) -> TenantRole | None:
    """Return the effective TenantRole for a user on a given device category.

    Returns None only when the user has no membership in the tenant at all.
    Category roles override the tenant-wide role; absence of a category role
    falls back to the tenant-wide role.
    """
    result = await db.execute(
        select(UserDeviceCategoryRole).where(
            UserDeviceCategoryRole.user_id == user_id,
            UserDeviceCategoryRole.tenant_id == tenant_id,
            UserDeviceCategoryRole.category == device_category,
        )
    )
    cat_role = result.scalar_one_or_none()
    if cat_role is not None:
        return cat_role.role

    result2 = await db.execute(
        select(UserTenantRole).where(
            UserTenantRole.user_id == user_id,
            UserTenantRole.tenant_id == tenant_id,
        )
    )
    utr = result2.scalar_one_or_none()
    return utr.role if utr else None


async def upsert_category_role(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    category: DeviceCategory,
    role: TenantRole,
    granted_by: UUID,
) -> UserDeviceCategoryRole:
    result = await db.execute(
        select(UserDeviceCategoryRole).where(
            UserDeviceCategoryRole.user_id == user_id,
            UserDeviceCategoryRole.tenant_id == tenant_id,
            UserDeviceCategoryRole.category == category,
        )
    )
    entry = result.scalar_one_or_none()
    if entry:
        entry.role = role
        entry.granted_by = granted_by
    else:
        entry = UserDeviceCategoryRole(
            user_id=user_id,
            tenant_id=tenant_id,
            category=category,
            role=role,
            granted_by=granted_by,
        )
        db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


async def delete_category_role(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    category: DeviceCategory,
) -> bool:
    result = await db.execute(
        select(UserDeviceCategoryRole).where(
            UserDeviceCategoryRole.user_id == user_id,
            UserDeviceCategoryRole.tenant_id == tenant_id,
            UserDeviceCategoryRole.category == category,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        return False
    await db.delete(entry)
    await db.flush()
    return True


async def get_user_category_roles(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
) -> list[UserDeviceCategoryRole]:
    result = await db.execute(
        select(UserDeviceCategoryRole).where(
            UserDeviceCategoryRole.tenant_id == tenant_id,
            UserDeviceCategoryRole.user_id == user_id,
        )
    )
    return list(result.scalars().all())


async def get_all_tenant_category_roles(
    db: AsyncSession,
    tenant_id: UUID,
) -> list[UserDeviceCategoryRole]:
    result = await db.execute(
        select(UserDeviceCategoryRole).where(
            UserDeviceCategoryRole.tenant_id == tenant_id,
        ).order_by(UserDeviceCategoryRole.user_id, UserDeviceCategoryRole.category)
    )
    return list(result.scalars().all())
