"""API — Grupos de Agentes RMM (Estações)."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.rmm import RmmAgent, RmmIntegration, RmmScriptRun
from app.models.rmm_groups import RmmAgentGroup, RmmAgentGroupMember
from app.models.user_tenant_role import TenantRole

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class RmmGroupCreate(BaseModel):
    name: str
    description: str | None = None
    agent_ids: list[UUID] = []


class RmmGroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    agent_ids: list[UUID] | None = None


class AgentInGroup(BaseModel):
    id: UUID
    hostname: str
    os_name: str | None
    ip_address: str | None
    status: str
    model_config = {"from_attributes": True}


class RmmGroupRead(BaseModel):
    id: UUID
    tenant_id: UUID
    created_by: UUID | None
    name: str
    description: str | None
    agent_count: int
    created_at: str
    updated_at: str


class RmmGroupDetail(RmmGroupRead):
    agents: list[AgentInGroup]


class GroupBulkRunRequest(BaseModel):
    shell: str = "powershell"
    run_type: str = "command"
    body: str
    timeout: int = 60


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_group(db: AsyncSession, group_id: UUID, tenant_id: UUID) -> RmmAgentGroup:
    result = await db.execute(
        select(RmmAgentGroup).where(
            RmmAgentGroup.id == group_id,
            RmmAgentGroup.tenant_id == tenant_id,
        )
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    return group


async def _get_group_agents(db: AsyncSession, group_id: UUID) -> list[RmmAgent]:
    result = await db.execute(
        select(RmmAgent)
        .join(RmmAgentGroupMember, RmmAgent.id == RmmAgentGroupMember.agent_id)
        .where(RmmAgentGroupMember.group_id == group_id)
        .order_by(RmmAgent.hostname)
    )
    return list(result.scalars().all())


def _to_read(group: RmmAgentGroup, agent_count: int) -> RmmGroupRead:
    return RmmGroupRead(
        id=group.id,
        tenant_id=group.tenant_id,
        created_by=group.created_by,
        name=group.name,
        description=group.description,
        agent_count=agent_count,
        created_at=group.created_at.isoformat(),
        updated_at=group.updated_at.isoformat(),
    )


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[RmmGroupRead])
async def list_rmm_groups(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[RmmGroupRead]:
    result = await db.execute(
        select(RmmAgentGroup)
        .where(RmmAgentGroup.tenant_id == ctx.tenant.id)
        .order_by(RmmAgentGroup.name)
    )
    groups = list(result.scalars().all())
    if not groups:
        return []
    group_ids = [g.id for g in groups]
    count_result = await db.execute(
        select(RmmAgentGroupMember.group_id, func.count().label("cnt"))
        .where(RmmAgentGroupMember.group_id.in_(group_ids))
        .group_by(RmmAgentGroupMember.group_id)
    )
    counts = {row.group_id: row.cnt for row in count_result}
    return [_to_read(g, counts.get(g.id, 0)) for g in groups]


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=RmmGroupDetail, status_code=201)
async def create_rmm_group(
    data: RmmGroupCreate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> RmmGroupDetail:
    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão.")
    for agent_id in data.agent_ids:
        r = await db.execute(
            select(RmmAgent).where(RmmAgent.id == agent_id, RmmAgent.tenant_id == ctx.tenant.id)
        )
        if not r.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Agente {agent_id} não encontrado")
    group = RmmAgentGroup(
        tenant_id=ctx.tenant.id,
        created_by=ctx.user.id,
        name=data.name,
        description=data.description,
    )
    db.add(group)
    await db.flush()
    await db.refresh(group)
    for agent_id in data.agent_ids:
        db.add(RmmAgentGroupMember(group_id=group.id, agent_id=agent_id))
    await db.flush()
    agents = await _get_group_agents(db, group.id)
    base = _to_read(group, len(agents))
    return RmmGroupDetail(**base.model_dump(), agents=[AgentInGroup.model_validate(a) for a in agents])


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{group_id}", response_model=RmmGroupDetail)
async def get_rmm_group(
    group_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> RmmGroupDetail:
    group = await _get_group(db, group_id, ctx.tenant.id)
    agents = await _get_group_agents(db, group.id)
    base = _to_read(group, len(agents))
    return RmmGroupDetail(**base.model_dump(), agents=[AgentInGroup.model_validate(a) for a in agents])


# ── Update ────────────────────────────────────────────────────────────────────

@router.put("/{group_id}", response_model=RmmGroupDetail)
async def update_rmm_group(
    group_id: UUID,
    data: RmmGroupUpdate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> RmmGroupDetail:
    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão.")
    group = await _get_group(db, group_id, ctx.tenant.id)
    if data.name is not None:
        group.name = data.name
    if data.description is not None:
        group.description = data.description
    if data.agent_ids is not None:
        for agent_id in data.agent_ids:
            r = await db.execute(
                select(RmmAgent).where(RmmAgent.id == agent_id, RmmAgent.tenant_id == ctx.tenant.id)
            )
            if not r.scalar_one_or_none():
                raise HTTPException(status_code=404, detail=f"Agente {agent_id} não encontrado")
        await db.execute(delete(RmmAgentGroupMember).where(RmmAgentGroupMember.group_id == group.id))
        for agent_id in data.agent_ids:
            db.add(RmmAgentGroupMember(group_id=group.id, agent_id=agent_id))
    await db.flush()
    await db.refresh(group)
    agents = await _get_group_agents(db, group.id)
    base = _to_read(group, len(agents))
    return RmmGroupDetail(**base.model_dump(), agents=[AgentInGroup.model_validate(a) for a in agents])


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{group_id}", status_code=204)
async def delete_rmm_group(
    group_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão.")
    group = await _get_group(db, group_id, ctx.tenant.id)
    await db.delete(group)


# ── Bulk Run ──────────────────────────────────────────────────────────────────

@router.post("/{group_id}/run", status_code=201)
async def bulk_run_on_group(
    group_id: UUID,
    data: GroupBulkRunRequest,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    from app.utils.crypto import decrypt_credentials
    from app.services.tactical_rmm_service import run_script, run_command

    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão.")

    group = await _get_group(db, group_id, ctx.tenant.id)
    agents = await _get_group_agents(db, group.id)
    if not agents:
        raise HTTPException(status_code=400, detail="O grupo não possui agentes.")

    results = []
    for agent in agents:
        integ_result = await db.execute(
            select(RmmIntegration).where(
                RmmIntegration.id == agent.integration_id,
                RmmIntegration.is_active.is_(True),
            )
        )
        integration = integ_result.scalar_one_or_none()
        if not integration or integration.rmm_type != "tactical_rmm":
            results.append({
                "agent_id": str(agent.id),
                "hostname": agent.hostname,
                "status": "skipped",
                "output": "Integração não suportada ou inativa.",
            })
            continue

        config = decrypt_credentials(integration.config_encrypted or "{}")
        config["base_url"] = integration.base_url
        config["verify_ssl"] = integration.verify_ssl

        run = RmmScriptRun(
            integration_id=integration.id,
            tenant_id=ctx.tenant.id,
            agent_external_id=agent.external_id,
            agent_hostname=agent.hostname,
            run_type=data.run_type,
            shell=data.shell,
            body=data.body,
            status="running",
            executed_by=ctx.user.id,
        )
        db.add(run)
        await db.flush()
        await db.refresh(run)

        try:
            if data.run_type == "script":
                result = await run_script(
                    config=config,
                    agent_id=agent.external_id,
                    script_body=data.body,
                    shell=data.shell,
                    timeout=data.timeout,
                )
            else:
                result = await run_command(
                    config=config,
                    agent_id=agent.external_id,
                    command=data.body,
                    shell=data.shell,
                    timeout=data.timeout,
                )
            run.output = result.get("output", "")
            run.exit_code = result.get("retcode", 0)
            run.status = "completed"
            results.append({
                "agent_id": str(agent.id),
                "hostname": agent.hostname,
                "status": "ok",
                "output": run.output,
                "exit_code": run.exit_code,
            })
        except Exception as exc:
            run.output = str(exc)
            run.status = "failed"
            results.append({
                "agent_id": str(agent.id),
                "hostname": agent.hostname,
                "status": "error",
                "output": str(exc),
            })
        await db.flush()

    return {
        "group_name": group.name,
        "agent_count": len(agents),
        "results": results,
    }
