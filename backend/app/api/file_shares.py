"""F36.ext — File Share Governance API."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.services import file_share_service

router = APIRouter()


class FileShareConfigCreate(BaseModel):
    name: str
    server_hostname: str
    unc_root: str
    edge_agent_id: UUID | None = None
    credentials: dict | None = None
    scan_depth: int = 2


class FileShareConfigRead(BaseModel):
    id: UUID
    name: str
    server_hostname: str
    unc_root: str
    edge_agent_id: UUID | None
    scan_depth: int
    is_active: bool
    last_scan_at: datetime | None
    last_scan_status: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class FileShareShareRead(BaseModel):
    id: UUID
    share_name: str
    unc_path: str
    description: str | None
    abe_enabled: bool | None
    health_status: str
    health_issues: Any | None
    acl_count: int
    scanned_at: datetime | None
    model_config = {"from_attributes": True}


class FileShareAclRead(BaseModel):
    id: UUID
    folder_path: str
    principal_name: str
    principal_type: str
    permission_type: str
    inherited: bool
    is_deny: bool
    depth: int
    model_config = {"from_attributes": True}


class ScanResultPayload(BaseModel):
    shares: list[dict]
    acls: list[dict]


@router.get("", response_model=list[FileShareConfigRead])
async def list_configs(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[FileShareConfigRead]:
    configs = await file_share_service.list_configs(db, ctx.tenant.id)
    return [FileShareConfigRead.model_validate(c) for c in configs]


@router.post("", response_model=FileShareConfigRead, status_code=201)
async def create_config(
    data: FileShareConfigCreate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileShareConfigRead:
    config = await file_share_service.create_config(
        db,
        tenant_id=ctx.tenant.id,
        name=data.name.strip(),
        server_hostname=data.server_hostname.strip(),
        unc_root=data.unc_root.strip(),
        edge_agent_id=data.edge_agent_id,
        credentials=data.credentials,
        scan_depth=data.scan_depth,
    )
    await db.commit()
    return FileShareConfigRead.model_validate(config)


@router.delete("/{config_id}", status_code=204)
async def delete_config(
    config_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    config = await file_share_service.get_config(db, config_id, ctx.tenant.id)
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada.")
    await file_share_service.delete_config(db, config)
    await db.commit()
    return Response(status_code=204)


@router.get("/{config_id}/script")
async def get_scan_script(
    config_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    config = await file_share_service.get_config(db, config_id, ctx.tenant.id)
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada.")
    script = file_share_service.get_powershell_script(config.unc_root, config.scan_depth)
    return {"script": script, "language": "powershell"}


@router.post("/{config_id}/scan-result")
async def submit_scan_result(
    config_id: UUID,
    data: ScanResultPayload,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    config = await file_share_service.get_config(db, config_id, ctx.tenant.id)
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada.")
    result = await file_share_service.process_scan_result(
        db, config, {"shares": data.shares, "acls": data.acls}
    )
    await db.commit()
    return result


@router.get("/{config_id}/shares", response_model=list[FileShareShareRead])
async def list_shares(
    config_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[FileShareShareRead]:
    config = await file_share_service.get_config(db, config_id, ctx.tenant.id)
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada.")
    shares = await file_share_service.get_shares(db, config_id, ctx.tenant.id)
    return [FileShareShareRead.model_validate(s) for s in shares]


@router.get("/{config_id}/shares/{share_id}/acls", response_model=list[FileShareAclRead])
async def list_acls(
    config_id: UUID,
    share_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[FileShareAclRead]:
    config = await file_share_service.get_config(db, config_id, ctx.tenant.id)
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada.")
    entries = await file_share_service.get_acl_entries(db, share_id, ctx.tenant.id)
    return [FileShareAclRead.model_validate(e) for e in entries]
