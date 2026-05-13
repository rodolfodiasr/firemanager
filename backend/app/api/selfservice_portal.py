"""API F39.cont — Self-Service Portal: catálogo de acesso + relatórios AD."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_module_reviewer
from app.database import get_db
from app.services import selfservice_reports_service as svc

router = APIRouter()
_require_admin = require_module_reviewer("identity")


# ── Schemas ───────────────────────────────────────────────────────────────────

class CatalogItemCreate(BaseModel):
    name: str
    description: str | None = None
    category: str = "general"
    connector_id: UUID | None = None
    ad_group: str | None = None
    access_type: str = "group_member"
    approval_required: bool = True
    approver_role: str = "admin"
    icon: str | None = None
    tags: list | None = None
    sort_order: int = 0


class CatalogItemRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    category: str
    ad_group: str | None
    access_type: str
    approval_required: bool
    icon: str | None
    tags: list | None
    is_active: bool
    sort_order: int
    model_config = {"from_attributes": True}


class AccessRequestCreate(BaseModel):
    catalog_item_id: UUID
    requester_email: str
    requester_name: str | None = None
    business_justification: str | None = None


class AccessRequestRead(BaseModel):
    id: UUID
    catalog_item_id: UUID | None
    item_name: str
    requester_email: str
    requester_name: str | None
    business_justification: str | None
    status: str
    approved_at: object | None
    rejection_reason: str | None
    provisioned_at: object | None
    created_at: object
    model_config = {"from_attributes": True}


class RejectBody(BaseModel):
    reason: str


# ── Catalog CRUD ──────────────────────────────────────────────────────────────

@router.get("/catalog", response_model=list[CatalogItemRead])
async def list_catalog(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = Query(default=None),
) -> list[CatalogItemRead]:
    items = await svc.list_catalog(db, ctx.tenant.id, category=category)
    return [CatalogItemRead.model_validate(i) for i in items]


@router.post("/catalog", response_model=CatalogItemRead, status_code=201)
async def create_catalog_item(
    body: CatalogItemCreate,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CatalogItemRead:
    obj = await svc.create_catalog_item(db, ctx.tenant.id, body.model_dump())
    return CatalogItemRead.model_validate(obj)


@router.patch("/catalog/{item_id}", response_model=CatalogItemRead)
async def update_catalog_item(
    item_id: UUID,
    body: CatalogItemCreate,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CatalogItemRead:
    item = await svc.get_catalog_item(db, ctx.tenant.id, item_id)
    if not item:
        raise HTTPException(404, "Item não encontrado")
    obj = await svc.update_catalog_item(db, item, body.model_dump(exclude_unset=True))
    return CatalogItemRead.model_validate(obj)


@router.delete("/catalog/{item_id}", status_code=204, response_model=None)
async def delete_catalog_item(
    item_id: UUID,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    item = await svc.get_catalog_item(db, ctx.tenant.id, item_id)
    if not item:
        raise HTTPException(404, "Item não encontrado")
    await db.delete(item)
    await db.commit()


# ── Access Requests ───────────────────────────────────────────────────────────

@router.get("/access-requests", response_model=list[AccessRequestRead])
async def list_access_requests(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AccessRequestRead]:
    items = await svc.list_access_requests(db, ctx.tenant.id, status=status, limit=limit)
    return [AccessRequestRead.model_validate(r) for r in items]


@router.post("/access-requests", response_model=AccessRequestRead, status_code=201)
async def submit_access_request(
    body: AccessRequestCreate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccessRequestRead:
    try:
        obj = await svc.submit_access_request(
            db,
            tenant_id=ctx.tenant.id,
            catalog_item_id=body.catalog_item_id,
            requester_email=body.requester_email,
            requester_name=body.requester_name,
            justification=body.business_justification,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return AccessRequestRead.model_validate(obj)


@router.post("/access-requests/{request_id}/approve", response_model=AccessRequestRead)
async def approve_request(
    request_id: UUID,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccessRequestRead:
    req = await svc.get_access_request(db, ctx.tenant.id, request_id)
    if not req:
        raise HTTPException(404, "Solicitação não encontrada")
    obj = await svc.approve_access_request(db, req, ctx.user.id)
    return AccessRequestRead.model_validate(obj)


@router.post("/access-requests/{request_id}/reject", response_model=AccessRequestRead)
async def reject_request(
    request_id: UUID,
    body: RejectBody,
    ctx: Annotated[TenantContext, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccessRequestRead:
    req = await svc.get_access_request(db, ctx.tenant.id, request_id)
    if not req:
        raise HTTPException(404, "Solicitação não encontrada")
    obj = await svc.reject_access_request(db, req, ctx.user.id, body.reason)
    return AccessRequestRead.model_validate(obj)


# ── AD Reports ────────────────────────────────────────────────────────────────

@router.get("/reports/expired-passwords")
async def report_expired_passwords(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    max_age_days: int = Query(default=90, ge=1, le=365),
) -> list[dict]:
    return await svc.report_expired_passwords(db, ctx.tenant.id, max_age_days)


@router.get("/reports/inactive-accounts")
async def report_inactive_accounts(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    inactive_days: int = Query(default=60, ge=1, le=365),
) -> list[dict]:
    return await svc.report_inactive_accounts(db, ctx.tenant.id, inactive_days)


@router.get("/reports/admins-without-mfa")
async def report_admins_without_mfa(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    return await svc.report_admins_without_mfa(db, ctx.tenant.id)


@router.get("/reports/group-members")
async def report_group_members(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    group_name: str = Query(...),
) -> list[dict]:
    return await svc.report_group_members(db, ctx.tenant.id, group_name)
