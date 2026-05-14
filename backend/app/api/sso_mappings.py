"""F31.cont — SSO Role Mappings API."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.edge_agents import SsoConfig
from app.services.sso_jit_service import (
    delete_role_mapping,
    list_role_mappings,
    upsert_role_mapping,
    VALID_ROLES,
)

router = APIRouter()


class SsoRoleMappingUpsert(BaseModel):
    external_group: str
    platform_role: str


class SsoRoleMappingRead(BaseModel):
    id: UUID
    sso_config_id: UUID
    external_group: str
    platform_role: str
    created_at: datetime
    model_config = {"from_attributes": True}


@router.get("", response_model=list[SsoRoleMappingRead])
async def list_mappings(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SsoRoleMappingRead]:
    mappings = await list_role_mappings(db, ctx.tenant.id)
    return [SsoRoleMappingRead.model_validate(m) for m in mappings]


@router.post("", response_model=SsoRoleMappingRead, status_code=201)
async def create_or_update_mapping(
    data: SsoRoleMappingUpsert,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SsoRoleMappingRead:
    sso_result = await db.execute(
        select(SsoConfig).where(SsoConfig.tenant_id == ctx.tenant.id)
    )
    sso_config = sso_result.scalar_one_or_none()
    if not sso_config:
        raise HTTPException(status_code=404, detail="Configure o SSO antes de criar mapeamentos.")
    try:
        mapping = await upsert_role_mapping(
            db,
            tenant_id=ctx.tenant.id,
            sso_config_id=sso_config.id,
            external_group=data.external_group.strip(),
            platform_role=data.platform_role,
        )
        await db.commit()
        return SsoRoleMappingRead.model_validate(mapping)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{mapping_id}", status_code=204)
async def remove_mapping(
    mapping_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    deleted = await delete_role_mapping(db, mapping_id, ctx.tenant.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Mapeamento não encontrado.")
    await db.commit()
    return Response(status_code=204)


@router.get("/roles")
async def list_available_roles(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> dict:
    return {"roles": list(VALID_ROLES)}
