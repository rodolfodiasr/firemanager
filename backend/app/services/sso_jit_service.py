"""F31.cont — SSO JIT Provisioning + Role Mapping service."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.edge_agents import SsoConfig, SsoRoleMapping

VALID_ROLES = ("admin", "analyst", "readonly")
DEFAULT_ROLE = "readonly"


async def list_role_mappings(db: AsyncSession, tenant_id: UUID) -> list[SsoRoleMapping]:
    result = await db.execute(
        select(SsoRoleMapping)
        .where(SsoRoleMapping.tenant_id == tenant_id)
        .order_by(SsoRoleMapping.external_group)
    )
    return list(result.scalars().all())


async def upsert_role_mapping(
    db: AsyncSession,
    tenant_id: UUID,
    sso_config_id: UUID,
    external_group: str,
    platform_role: str,
) -> SsoRoleMapping:
    if platform_role not in VALID_ROLES:
        raise ValueError(f"Role inválido: {platform_role}. Aceitos: {VALID_ROLES}")

    result = await db.execute(
        select(SsoRoleMapping).where(
            SsoRoleMapping.sso_config_id == sso_config_id,
            SsoRoleMapping.external_group == external_group,
        )
    )
    mapping = result.scalar_one_or_none()
    if mapping:
        mapping.platform_role = platform_role
    else:
        mapping = SsoRoleMapping(
            sso_config_id=sso_config_id,
            tenant_id=tenant_id,
            external_group=external_group.strip(),
            platform_role=platform_role,
        )
        db.add(mapping)
    await db.flush()
    await db.refresh(mapping)
    return mapping


async def delete_role_mapping(db: AsyncSession, mapping_id: UUID, tenant_id: UUID) -> bool:
    result = await db.execute(
        select(SsoRoleMapping).where(
            SsoRoleMapping.id == mapping_id,
            SsoRoleMapping.tenant_id == tenant_id,
        )
    )
    mapping = result.scalar_one_or_none()
    if not mapping:
        return False
    await db.delete(mapping)
    return True


async def resolve_role_from_groups(
    db: AsyncSession,
    sso_config_id: UUID,
    user_groups: list[str],
) -> str:
    """Map IdP groups to platform role. Returns highest-privilege match."""
    if not user_groups:
        return DEFAULT_ROLE

    result = await db.execute(
        select(SsoRoleMapping).where(SsoRoleMapping.sso_config_id == sso_config_id)
    )
    mappings = {m.external_group: m.platform_role for m in result.scalars().all()}

    role_priority = {"admin": 3, "analyst": 2, "readonly": 1}
    best_role = DEFAULT_ROLE
    best_priority = role_priority.get(DEFAULT_ROLE, 0)

    for group in user_groups:
        if group in mappings:
            candidate = mappings[group]
            prio = role_priority.get(candidate, 0)
            if prio > best_priority:
                best_priority = prio
                best_role = candidate

    return best_role


async def jit_provision_user(
    db: AsyncSession,
    tenant_id: UUID,
    sso_config_id: UUID,
    sub: str,
    email: str,
    name: str,
    user_groups: list[str],
) -> dict:
    """Create or update user via JIT provisioning. Returns user dict with role."""
    from app.models.user import User
    from app.models.user_tenant_role import UserTenantRole

    role = await resolve_role_from_groups(db, sso_config_id, user_groups)

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            email=email,
            name=name,
            hashed_password="",
            is_active=True,
            is_super_admin=False,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)

    utr_result = await db.execute(
        select(UserTenantRole).where(
            UserTenantRole.user_id == user.id,
            UserTenantRole.tenant_id == tenant_id,
        )
    )
    utr = utr_result.scalar_one_or_none()
    if not utr:
        utr = UserTenantRole(user_id=user.id, tenant_id=tenant_id, role=role)
        db.add(utr)
    else:
        utr.role = role

    await db.flush()
    return {"user_id": str(user.id), "email": email, "role": role, "jit": True}
