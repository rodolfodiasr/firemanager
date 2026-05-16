"""RMM Script Templates API."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.services import rmm_template_service

router = APIRouter()

VALID_CATEGORIES = ("monitoring", "security", "maintenance", "network", "general", "incident_response", "identity", "compliance", "forensics")
VALID_SHELLS = ("powershell", "cmd", "python", "bash")
VALID_RUN_TYPES = ("command", "script")


class TemplateCreate(BaseModel):
    name: str
    body: str
    shell: str = "powershell"
    run_type: str = "command"
    category: str = "general"
    description: str | None = None


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    shell: str | None = None
    run_type: str | None = None
    body: str | None = None


class TemplateRead(BaseModel):
    id: UUID
    tenant_id: UUID | None
    name: str
    description: str | None
    category: str
    shell: str
    run_type: str
    body: str
    is_builtin: bool
    created_at: datetime
    model_config = {"from_attributes": True}


@router.get("", response_model=list[TemplateRead])
async def list_templates(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = None,
) -> list[TemplateRead]:
    templates = await rmm_template_service.list_templates(db, ctx.tenant.id, category)
    if not templates:
        await rmm_template_service.seed_builtin_templates(db)
        await db.commit()
        templates = await rmm_template_service.list_templates(db, ctx.tenant.id, category)
    return [TemplateRead.model_validate(t) for t in templates]


@router.post("/seed", status_code=200)
async def seed_templates(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    added = await rmm_template_service.seed_builtin_templates(db)
    await db.commit()
    return {"added": added, "message": f"{added} template(s) builtin adicionado(s)"}


@router.post("", response_model=TemplateRead, status_code=201)
async def create_template(
    data: TemplateCreate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TemplateRead:
    if data.shell not in VALID_SHELLS:
        raise HTTPException(status_code=400, detail=f"shell inválido. Aceitos: {VALID_SHELLS}")
    if data.run_type not in VALID_RUN_TYPES:
        raise HTTPException(status_code=400, detail=f"run_type inválido. Aceitos: {VALID_RUN_TYPES}")
    if data.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category inválida. Aceitas: {VALID_CATEGORIES}")
    tmpl = await rmm_template_service.create_template(
        db,
        tenant_id=ctx.tenant.id,
        name=data.name,
        body=data.body,
        shell=data.shell,
        run_type=data.run_type,
        category=data.category,
        description=data.description,
    )
    await db.commit()
    return TemplateRead.model_validate(tmpl)


@router.patch("/{template_id}", response_model=TemplateRead)
async def update_template(
    template_id: UUID,
    data: TemplateUpdate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TemplateRead:
    tmpl = await rmm_template_service.get_template(db, template_id, ctx.tenant.id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template não encontrado.")
    if tmpl.is_builtin:
        raise HTTPException(status_code=403, detail="Templates builtin não podem ser editados.")
    if data.shell and data.shell not in VALID_SHELLS:
        raise HTTPException(status_code=400, detail=f"shell inválido. Aceitos: {VALID_SHELLS}")
    if data.run_type and data.run_type not in VALID_RUN_TYPES:
        raise HTTPException(status_code=400, detail=f"run_type inválido. Aceitos: {VALID_RUN_TYPES}")
    if data.category and data.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category inválida. Aceitas: {VALID_CATEGORIES}")
    tmpl = await rmm_template_service.update_template(
        db, tmpl,
        name=data.name,
        description=data.description,
        category=data.category,
        shell=data.shell,
        run_type=data.run_type,
        body=data.body,
    )
    await db.commit()
    return TemplateRead.model_validate(tmpl)


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    tmpl = await rmm_template_service.get_template(db, template_id, ctx.tenant.id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template não encontrado.")
    if tmpl.is_builtin:
        raise HTTPException(status_code=403, detail="Templates builtin não podem ser removidos.")
    await rmm_template_service.delete_template(db, tmpl)
    await db.commit()
    return Response(status_code=204)
