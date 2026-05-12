import asyncio
from collections.abc import AsyncGenerator
from datetime import timedelta, timezone
from typing import Generator
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.user_tenant_role import TenantRole, UserTenantRole

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# SQLite doesn't know PostgreSQL-specific types — teach it to render them as TEXT
if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
    SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "TEXT"
if not hasattr(SQLiteTypeCompiler, "visit_TSVECTOR"):
    SQLiteTypeCompiler.visit_TSVECTOR = lambda self, type_, **kw: "TEXT"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_fortinet_connector():
    connector = AsyncMock()
    connector.test_connection.return_value = MagicMock(success=True, latency_ms=10.0, firmware_version="FortiOS v7.4")
    connector.list_rules.return_value = []
    connector.create_rule.return_value = MagicMock(success=True, rule_id="1")
    return connector


# ── Shared integration test helpers ───────────────────────────────────────────

def _hashed(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


async def make_tenant(db: AsyncSession, *, slug: str | None = None) -> Tenant:
    slug = slug or f"tenant-{uuid4().hex[:8]}"
    tenant = Tenant(name=f"Tenant {slug}", slug=slug, is_active=True)
    db.add(tenant)
    await db.flush()
    return tenant


async def make_user(
    db: AsyncSession,
    *,
    email: str | None = None,
    password: str = "Test@1234",
    role: UserRole = UserRole.operator,
    is_super_admin: bool = False,
) -> tuple[User, str]:
    """Create a user and return (user, plaintext_password)."""
    email = email or f"user-{uuid4().hex[:6]}@test.local"
    user = User(
        email=email,
        name="Test User",
        hashed_password=_hashed(password),
        role=role,
        is_active=True,
        is_super_admin=is_super_admin,
    )
    db.add(user)
    await db.flush()
    return user, password


async def assign_role(
    db: AsyncSession,
    user: User,
    tenant: Tenant,
    role: TenantRole,
) -> UserTenantRole:
    utr = UserTenantRole(user_id=user.id, tenant_id=tenant.id, role=role)
    db.add(utr)
    await db.flush()
    return utr


def make_token(user: User, tenant: Tenant | None, role: TenantRole | None) -> str:
    """Generate a real JWT for a user+tenant combo without hitting the DB."""
    from app.api.auth import _create_access_token
    return _create_access_token(user, tenant_id=tenant.id if tenant else None, role=role.value if role else None)
