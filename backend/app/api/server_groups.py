"""API — Grupos de Servidores."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.server import Server
from app.models.server_groups import ServerGroup, ServerGroupMember
from app.models.user_tenant_role import TenantRole

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ServerGroupCreate(BaseModel):
    name: str
    description: str | None = None
    server_ids: list[UUID] = []


class ServerGroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    server_ids: list[UUID] | None = None


class ServerInGroup(BaseModel):
    id: UUID
    name: str
    host: str
    os_type: str
    is_active: bool
    model_config = {"from_attributes": True}


class ServerGroupRead(BaseModel):
    id: UUID
    tenant_id: UUID
    created_by: UUID | None
    name: str
    description: str | None
    server_count: int
    created_at: str
    updated_at: str


class ServerGroupDetail(ServerGroupRead):
    servers: list[ServerInGroup]


class GroupAnalyzeRequest(BaseModel):
    question: str


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_group(db: AsyncSession, group_id: UUID, tenant_id: UUID) -> ServerGroup:
    result = await db.execute(
        select(ServerGroup).where(
            ServerGroup.id == group_id,
            ServerGroup.tenant_id == tenant_id,
        )
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    return group


async def _get_group_servers(db: AsyncSession, group_id: UUID) -> list[Server]:
    result = await db.execute(
        select(Server)
        .join(ServerGroupMember, Server.id == ServerGroupMember.server_id)
        .where(ServerGroupMember.group_id == group_id)
        .order_by(Server.name)
    )
    return list(result.scalars().all())


def _to_read(group: ServerGroup, server_count: int) -> ServerGroupRead:
    return ServerGroupRead(
        id=group.id,
        tenant_id=group.tenant_id,
        created_by=group.created_by,
        name=group.name,
        description=group.description,
        server_count=server_count,
        created_at=group.created_at.isoformat(),
        updated_at=group.updated_at.isoformat(),
    )


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ServerGroupRead])
async def list_server_groups(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[ServerGroupRead]:
    result = await db.execute(
        select(ServerGroup)
        .where(ServerGroup.tenant_id == ctx.tenant.id)
        .order_by(ServerGroup.name)
    )
    groups = list(result.scalars().all())
    if not groups:
        return []
    group_ids = [g.id for g in groups]
    count_result = await db.execute(
        select(ServerGroupMember.group_id, func.count().label("cnt"))
        .where(ServerGroupMember.group_id.in_(group_ids))
        .group_by(ServerGroupMember.group_id)
    )
    counts = {row.group_id: row.cnt for row in count_result}
    return [_to_read(g, counts.get(g.id, 0)) for g in groups]


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=ServerGroupDetail, status_code=201)
async def create_server_group(
    data: ServerGroupCreate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> ServerGroupDetail:
    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão.")
    for server_id in data.server_ids:
        r = await db.execute(
            select(Server).where(Server.id == server_id, Server.tenant_id == ctx.tenant.id)
        )
        if not r.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Servidor {server_id} não encontrado")
    group = ServerGroup(
        tenant_id=ctx.tenant.id,
        created_by=ctx.user.id,
        name=data.name,
        description=data.description,
    )
    db.add(group)
    await db.flush()
    await db.refresh(group)
    for server_id in data.server_ids:
        db.add(ServerGroupMember(group_id=group.id, server_id=server_id))
    await db.flush()
    servers = await _get_group_servers(db, group.id)
    base = _to_read(group, len(servers))
    return ServerGroupDetail(**base.model_dump(), servers=[ServerInGroup.model_validate(s) for s in servers])


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{group_id}", response_model=ServerGroupDetail)
async def get_server_group(
    group_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> ServerGroupDetail:
    group = await _get_group(db, group_id, ctx.tenant.id)
    servers = await _get_group_servers(db, group.id)
    base = _to_read(group, len(servers))
    return ServerGroupDetail(**base.model_dump(), servers=[ServerInGroup.model_validate(s) for s in servers])


# ── Update ────────────────────────────────────────────────────────────────────

@router.put("/{group_id}", response_model=ServerGroupDetail)
async def update_server_group(
    group_id: UUID,
    data: ServerGroupUpdate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> ServerGroupDetail:
    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão.")
    group = await _get_group(db, group_id, ctx.tenant.id)
    if data.name is not None:
        group.name = data.name
    if data.description is not None:
        group.description = data.description
    if data.server_ids is not None:
        for server_id in data.server_ids:
            r = await db.execute(
                select(Server).where(Server.id == server_id, Server.tenant_id == ctx.tenant.id)
            )
            if not r.scalar_one_or_none():
                raise HTTPException(status_code=404, detail=f"Servidor {server_id} não encontrado")
        await db.execute(delete(ServerGroupMember).where(ServerGroupMember.group_id == group.id))
        for server_id in data.server_ids:
            db.add(ServerGroupMember(group_id=group.id, server_id=server_id))
    await db.flush()
    await db.refresh(group)
    servers = await _get_group_servers(db, group.id)
    base = _to_read(group, len(servers))
    return ServerGroupDetail(**base.model_dump(), servers=[ServerInGroup.model_validate(s) for s in servers])


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{group_id}", status_code=204)
async def delete_server_group(
    group_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão.")
    group = await _get_group(db, group_id, ctx.tenant.id)
    await db.delete(group)


# ── Bulk Analyze ──────────────────────────────────────────────────────────────

@router.post("/{group_id}/analyze", status_code=201)
async def analyze_server_group(
    group_id: UUID,
    data: GroupAnalyzeRequest,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    from app.services.server_analysis import analyze
    from app.models.analysis_session import AnalysisSession

    group = await _get_group(db, group_id, ctx.tenant.id)
    servers = await _get_group_servers(db, group.id)
    if not servers:
        raise HTTPException(status_code=400, detail="O grupo não possui servidores.")

    server_ids = [s.id for s in servers]
    question = f"[Grupo: {group.name}] {data.question}"
    answer, sources = await analyze(
        db=db,
        tenant_id=ctx.tenant.id,
        question=question,
        server_ids=server_ids,
        integration_ids=[],
    )
    session = AnalysisSession(
        tenant_id=ctx.tenant.id,
        question=question,
        answer=answer,
        sources_used=sources,
        server_ids=[str(sid) for sid in server_ids],
        integration_ids=[],
    )
    db.add(session)
    await db.flush()
    return {"answer": answer, "sources_used": sources, "server_count": len(servers)}
