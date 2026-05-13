import hashlib
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.edge_agents import EdgeAgent, MarketplacePlugin, RbacCustomRole, SsoConfig, TenantPlugin

_BUILTIN_PLUGINS = [
    {
        "name": "Fortinet FortiGate Connector",
        "slug": "fortinet-fortigate",
        "version": "1.0.0",
        "category": "connector",
        "description": "Full REST + SSH connector for FortiGate devices (FortiOS 7.x)",
        "is_builtin": True,
    },
    {
        "name": "SonicWall SonicOS Connector",
        "slug": "sonicwall-sonicos",
        "version": "1.0.0",
        "category": "connector",
        "description": "REST connector for SonicWall SonicOS 6.x and 7.x",
        "is_builtin": True,
    },
    {
        "name": "Wazuh SIEM Integration",
        "slug": "wazuh-siem",
        "version": "1.0.0",
        "category": "connector",
        "description": "Bidirectional Wazuh SIEM integration with webhook and API polling",
        "is_builtin": True,
    },
    {
        "name": "LGPD Compliance Pack",
        "slug": "lgpd-compliance",
        "version": "1.0.0",
        "category": "report",
        "description": "Automated LGPD controls assessment with evidence collection",
        "is_builtin": True,
    },
    {
        "name": "Executive Risk Dashboard",
        "slug": "executive-risk-dashboard",
        "version": "1.0.0",
        "category": "report",
        "description": "Executive-level risk score dashboard with PDF export",
        "is_builtin": True,
    },
]


def generate_agent_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, token_hash


async def create_agent(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    name: str,
    notes: str | None,
    created_by: uuid.UUID,
) -> tuple[EdgeAgent, str]:
    raw_token, token_hash = generate_agent_token()
    agent = EdgeAgent(
        tenant_id=tenant_id,
        name=name,
        token_hash=token_hash,
        notes=notes,
        created_by=created_by,
        status="offline",
    )
    db.add(agent)
    await db.flush()
    await db.refresh(agent)
    return agent, raw_token


async def seed_marketplace_plugins(db: AsyncSession) -> list[MarketplacePlugin]:
    created = []
    for p in _BUILTIN_PLUGINS:
        existing = await db.scalar(
            select(MarketplacePlugin).where(MarketplacePlugin.slug == p["slug"])
        )
        if existing:
            continue
        plugin = MarketplacePlugin(**p)
        db.add(plugin)
        created.append(plugin)
    await db.flush()
    for p in created:
        await db.refresh(p)
    return created


async def install_plugin(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    plugin_id: uuid.UUID,
    installed_by: uuid.UUID,
) -> TenantPlugin:
    existing = await db.scalar(
        select(TenantPlugin).where(
            TenantPlugin.tenant_id == tenant_id,
            TenantPlugin.plugin_id == plugin_id,
        )
    )
    if existing:
        return existing

    plugin = await db.get(MarketplacePlugin, plugin_id)
    if not plugin:
        raise ValueError("Plugin not found")

    install = TenantPlugin(
        tenant_id=tenant_id,
        plugin_id=plugin_id,
        installed_by=installed_by,
    )
    db.add(install)

    plugin.download_count = (plugin.download_count or 0) + 1
    await db.flush()
    await db.refresh(install)
    return install
