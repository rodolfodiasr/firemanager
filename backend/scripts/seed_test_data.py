"""Seed script — creates test tenants, users, devices and invites.

Run inside the container:
    docker compose -f infra/docker-compose.yml exec api python scripts/seed_test_data.py

All entities are idempotent: re-running the script is safe (skips existing
records by email/slug). Passwords and tokens are printed once to stdout.
"""
from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.device import Device, DeviceCategory, VendorEnum
from app.models.invite_token import InviteToken
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.user_tenant_role import TenantRole, UserTenantRole
from app.database import Base


def _hash(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()


async def get_or_create_tenant(db: AsyncSession, name: str, slug: str) -> Tenant:
    r = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = r.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(name=name, slug=slug, is_active=True)
        db.add(tenant)
        await db.flush()
        print(f"  [+] Tenant criado: {name} ({slug})")
    else:
        print(f"  [~] Tenant já existe: {name}")
    return tenant


async def get_or_create_user(
    db: AsyncSession,
    email: str,
    name: str,
    password: str,
    role: UserRole = UserRole.operator,
    is_super_admin: bool = False,
) -> User:
    r = await db.execute(select(User).where(User.email == email))
    user = r.scalar_one_or_none()
    if not user:
        user = User(
            email=email,
            name=name,
            hashed_password=_hash(password),
            role=role,
            is_active=True,
            is_super_admin=is_super_admin,
        )
        db.add(user)
        await db.flush()
        print(f"  [+] Usuário criado: {email} / {password}")
    else:
        print(f"  [~] Usuário já existe: {email}")
    return user


async def assign_if_missing(
    db: AsyncSession, user: User, tenant: Tenant, role: TenantRole
) -> None:
    r = await db.execute(
        select(UserTenantRole).where(
            UserTenantRole.user_id == user.id,
            UserTenantRole.tenant_id == tenant.id,
        )
    )
    if not r.scalar_one_or_none():
        db.add(UserTenantRole(user_id=user.id, tenant_id=tenant.id, role=role))
        await db.flush()
        print(f"  [+] {user.email} → {tenant.slug} como {role.value}")


async def get_or_create_device(db: AsyncSession, tenant: Tenant, name: str, host: str) -> Device:
    r = await db.execute(
        select(Device).where(Device.tenant_id == tenant.id, Device.name == name)
    )
    device = r.scalar_one_or_none()
    if not device:
        device = Device(
            tenant_id=tenant.id,
            name=name,
            vendor=VendorEnum.fortinet,
            category=DeviceCategory.firewall,
            host=host,
            port=443,
            use_ssl=True,
            verify_ssl=False,
            encrypted_credentials='{"auth_type": "token", "token": "seed-token-placeholder"}',
            read_only_agent=True,  # safe default for test devices
        )
        db.add(device)
        await db.flush()
        print(f"  [+] Device criado: {name} ({host})")
    else:
        print(f"  [~] Device já existe: {name}")
    return device


async def create_invite(db: AsyncSession, email: str, tenant: Tenant, role: TenantRole) -> str:
    # Check for existing pending invite
    r = await db.execute(
        select(InviteToken).where(
            InviteToken.email == email,
            InviteToken.tenant_id == tenant.id,
            InviteToken.used_at.is_(None),
            InviteToken.expires_at > datetime.now(timezone.utc),
        )
    )
    existing = r.scalar_one_or_none()
    if existing:
        print(f"  [~] Convite pendente já existe para {email}")
        return existing.token

    raw_token = secrets.token_urlsafe(32)
    invite = InviteToken(
        token=raw_token,
        email=email,
        tenant_id=tenant.id,
        role=role.value,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(invite)
    await db.flush()
    invite_url = f"http://localhost:5173/invite/{raw_token}"
    print(f"  [+] Convite criado para {email}: {invite_url}")
    return raw_token


async def seed(db: AsyncSession) -> None:
    print("\n=== Seed: Tenants ===")
    acme = await get_or_create_tenant(db, "Acme Corp", "acme-corp")
    beta = await get_or_create_tenant(db, "Beta MSSP", "beta-mssp")

    print("\n=== Seed: Usuários ===")
    super_admin = await get_or_create_user(
        db, "superadmin@eternity.local", "Super Admin", "SuperAdmin@1234",
        role=UserRole.operator, is_super_admin=True
    )
    acme_admin = await get_or_create_user(
        db, "admin@acme.local", "Acme Admin", "AcmeAdmin@1234"
    )
    acme_analyst = await get_or_create_user(
        db, "analyst@acme.local", "Acme Analyst", "AcmeAnalyst@1234"
    )
    acme_viewer = await get_or_create_user(
        db, "viewer@acme.local", "Acme Viewer", "AcmeViewer@1234"
    )
    beta_admin = await get_or_create_user(
        db, "admin@beta.local", "Beta Admin", "BetaAdmin@1234"
    )

    print("\n=== Seed: Roles ===")
    await assign_if_missing(db, acme_admin, acme, TenantRole.admin)
    await assign_if_missing(db, acme_analyst, acme, TenantRole.analyst_n1)
    await assign_if_missing(db, acme_viewer, acme, TenantRole.readonly)
    await assign_if_missing(db, beta_admin, beta, TenantRole.admin)

    print("\n=== Seed: Devices ===")
    await get_or_create_device(db, acme, "FW-HQ-01 (Seed)", "192.0.2.1")
    await get_or_create_device(db, acme, "FW-Branch-01 (Seed)", "192.0.2.2")
    await get_or_create_device(db, beta, "FW-Beta-01 (Seed)", "192.0.2.10")

    print("\n=== Seed: Convites ===")
    await create_invite(db, "pending@acme.local", acme, TenantRole.analyst_n2)

    await db.commit()
    print("\n✅ Seed concluído com sucesso!\n")
    print("Credenciais de acesso:")
    print("  superadmin@eternity.local / SuperAdmin@1234  (super admin)")
    print("  admin@acme.local          / AcmeAdmin@1234   (admin - Acme Corp)")
    print("  analyst@acme.local        / AcmeAnalyst@1234 (analyst_n1 - Acme Corp)")
    print("  viewer@acme.local         / AcmeViewer@1234  (readonly - Acme Corp)")
    print("  admin@beta.local          / BetaAdmin@1234   (admin - Beta MSSP)")


async def main() -> None:
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        await seed(db)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
