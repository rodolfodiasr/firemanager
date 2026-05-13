from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_module_reviewer
from app.database import get_db
from app.models.edge_agents import (
    EdgeAgent, MarketplacePlugin, RbacCustomRole, RbacRoleAssignment,
    SsoConfig, TenantPlugin,
)
from app.services.edge_agent_service import (
    create_agent, install_plugin, seed_marketplace_plugins,
)

router = APIRouter()
_require_admin = require_module_reviewer("compliance")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class EdgeAgentCreate(BaseModel):
    name: str
    notes: Optional[str] = None


class EdgeAgentRead(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    version: Optional[str]
    last_seen: Optional[datetime]
    ip_address: Optional[str]
    device_ids: Optional[Any]
    notes: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class EdgeAgentWithToken(EdgeAgentRead):
    token: str


class SsoConfigCreate(BaseModel):
    provider: str = "azure_ad"
    client_id: str
    client_secret: Optional[str] = None
    discovery_url: str
    group_claim: str = "groups"
    group_mapping: Optional[dict] = None
    sso_required: bool = False


class SsoConfigRead(BaseModel):
    id: uuid.UUID
    provider: str
    client_id: str
    discovery_url: str
    group_claim: Optional[str]
    group_mapping: Optional[Any]
    sso_required: bool
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class PluginRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    version: str
    category: str
    description: Optional[str]
    is_builtin: bool
    download_count: int
    approved_at: Optional[datetime]
    model_config = {"from_attributes": True}


class TenantPluginRead(BaseModel):
    id: uuid.UUID
    plugin_id: uuid.UUID
    installed_at: datetime
    plugin: PluginRead
    model_config = {"from_attributes": True}


class RbacRoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: Optional[dict] = None


class RbacRoleRead(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    permissions: Optional[Any]
    created_at: datetime
    model_config = {"from_attributes": True}


class RbacAssignRequest(BaseModel):
    user_id: uuid.UUID
    role_id: uuid.UUID


class RbacAssignmentRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    role_id: uuid.UUID
    assigned_at: datetime
    model_config = {"from_attributes": True}


# ── Edge Agents ───────────────────────────────────────────────────────────────

@router.get("/agents", response_model=list[EdgeAgentRead])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    rows = await db.execute(select(EdgeAgent).where(EdgeAgent.tenant_id == ctx.tenant.id))
    return rows.scalars().all()


@router.post("/agents", response_model=EdgeAgentWithToken, status_code=201)
async def register_agent(
    body: EdgeAgentCreate,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    agent, raw_token = await create_agent(db, ctx.tenant.id, body.name, body.notes, ctx.user.id)
    data = EdgeAgentRead.model_validate(agent).model_dump()
    return {**data, "token": raw_token}


@router.patch("/agents/{agent_id}", response_model=EdgeAgentRead)
async def update_agent(
    agent_id: uuid.UUID,
    body: EdgeAgentCreate,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    agent = await db.scalar(
        select(EdgeAgent).where(EdgeAgent.id == agent_id, EdgeAgent.tenant_id == ctx.tenant.id)
    )
    if not agent:
        raise HTTPException(404, "Agent not found")
    agent.name = body.name
    if body.notes is not None:
        agent.notes = body.notes
    await db.flush()
    await db.refresh(agent)
    return agent


@router.delete("/agents/{agent_id}", status_code=204, response_model=None)
async def delete_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    agent = await db.scalar(
        select(EdgeAgent).where(EdgeAgent.id == agent_id, EdgeAgent.tenant_id == ctx.tenant.id)
    )
    if not agent:
        raise HTTPException(404, "Agent not found")
    await db.delete(agent)


# ── SSO Configs ───────────────────────────────────────────────────────────────

@router.get("/sso", response_model=Optional[SsoConfigRead])
async def get_sso_config(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    return await db.scalar(select(SsoConfig).where(SsoConfig.tenant_id == ctx.tenant.id))


@router.put("/sso", response_model=SsoConfigRead)
async def upsert_sso_config(
    body: SsoConfigCreate,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    existing = await db.scalar(select(SsoConfig).where(SsoConfig.tenant_id == ctx.tenant.id))
    if existing:
        for k, v in body.model_dump(exclude={"client_secret"}).items():
            setattr(existing, k, v)
        if body.client_secret:
            existing.client_secret_encrypted = body.client_secret
        await db.flush()
        await db.refresh(existing)
        return existing
    cfg = SsoConfig(
        tenant_id=ctx.tenant.id,
        client_secret_encrypted=body.client_secret,
        **body.model_dump(exclude={"client_secret"}),
    )
    db.add(cfg)
    await db.flush()
    await db.refresh(cfg)
    return cfg


@router.delete("/sso", status_code=204, response_model=None)
async def delete_sso_config(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    cfg = await db.scalar(select(SsoConfig).where(SsoConfig.tenant_id == ctx.tenant.id))
    if cfg:
        await db.delete(cfg)


# ── Marketplace ───────────────────────────────────────────────────────────────

@router.get("/marketplace", response_model=list[PluginRead])
async def list_marketplace(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = ...,
):
    rows = await db.execute(select(MarketplacePlugin))
    return rows.scalars().all()


@router.post("/marketplace/seed", response_model=list[PluginRead])
async def seed_plugins(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    return await seed_marketplace_plugins(db)


@router.get("/marketplace/installed", response_model=list[TenantPluginRead])
async def list_installed(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = ...,
):
    rows = await db.execute(
        select(TenantPlugin)
        .where(TenantPlugin.tenant_id == ctx.tenant.id)
        .options(selectinload(TenantPlugin.plugin))
    )
    return rows.scalars().all()


@router.post("/marketplace/{plugin_id}/install", response_model=TenantPluginRead, status_code=201)
async def install_plugin_endpoint(
    plugin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    install = await install_plugin(db, ctx.tenant.id, plugin_id, ctx.user.id)
    result = await db.scalar(
        select(TenantPlugin)
        .where(TenantPlugin.id == install.id)
        .options(selectinload(TenantPlugin.plugin))
    )
    return result


@router.delete("/marketplace/{plugin_id}/uninstall", status_code=204, response_model=None)
async def uninstall_plugin(
    plugin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    install = await db.scalar(
        select(TenantPlugin).where(
            TenantPlugin.tenant_id == ctx.tenant.id,
            TenantPlugin.plugin_id == plugin_id,
        )
    )
    if not install:
        raise HTTPException(404, "Plugin not installed")
    await db.delete(install)


# ── RBAC Custom Roles ─────────────────────────────────────────────────────────

@router.get("/rbac-roles", response_model=list[RbacRoleRead])
async def list_rbac_roles(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    rows = await db.execute(
        select(RbacCustomRole).where(RbacCustomRole.tenant_id == ctx.tenant.id)
    )
    return rows.scalars().all()


@router.post("/rbac-roles", response_model=RbacRoleRead, status_code=201)
async def create_rbac_role(
    body: RbacRoleCreate,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    role = RbacCustomRole(tenant_id=ctx.tenant.id, **body.model_dump())
    db.add(role)
    await db.flush()
    await db.refresh(role)
    return role


@router.delete("/rbac-roles/{role_id}", status_code=204, response_model=None)
async def delete_rbac_role(
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    role = await db.scalar(
        select(RbacCustomRole).where(
            RbacCustomRole.id == role_id, RbacCustomRole.tenant_id == ctx.tenant.id
        )
    )
    if not role:
        raise HTTPException(404, "Role not found")
    await db.delete(role)


@router.get("/rbac-assignments", response_model=list[RbacAssignmentRead])
async def list_assignments(
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    rows = await db.execute(
        select(RbacRoleAssignment).where(RbacRoleAssignment.tenant_id == ctx.tenant.id)
    )
    return rows.scalars().all()


@router.post("/rbac-assignments", response_model=RbacAssignmentRead, status_code=201)
async def assign_rbac_role(
    body: RbacAssignRequest,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    role = await db.scalar(
        select(RbacCustomRole).where(
            RbacCustomRole.id == body.role_id, RbacCustomRole.tenant_id == ctx.tenant.id
        )
    )
    if not role:
        raise HTTPException(404, "Role not found")
    assignment = RbacRoleAssignment(
        tenant_id=ctx.tenant.id,
        user_id=body.user_id,
        role_id=body.role_id,
        assigned_by=ctx.user.id,
    )
    db.add(assignment)
    await db.flush()
    await db.refresh(assignment)
    return assignment


@router.delete("/rbac-assignments/{assignment_id}", status_code=204, response_model=None)
async def remove_rbac_assignment(
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: Annotated[TenantContext, Depends(_require_admin)] = ...,
):
    a = await db.scalar(
        select(RbacRoleAssignment).where(
            RbacRoleAssignment.id == assignment_id,
            RbacRoleAssignment.tenant_id == ctx.tenant.id,
        )
    )
    if not a:
        raise HTTPException(404, "Assignment not found")
    await db.delete(a)
