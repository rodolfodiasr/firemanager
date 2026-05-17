from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_tenant_admin, require_reviewer
from app.models.user_tenant_role import TenantRole
from app.database import get_db
from app.schemas.device import BookstackPageInfo, DeviceBookstackLink, DeviceCreate, DeviceRead, DeviceUpdate, DocDraftResult
from app.services.device_service import (
    DeviceNotFoundError,
    create_device,
    delete_device,
    get_device,
    health_check_device,
    list_devices,
    update_device,
)

router = APIRouter()


@router.get("", response_model=list[DeviceRead])
async def get_devices(
    skip:  int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    ctx:   Annotated[TenantContext, Depends(get_tenant_context)] = None,
    db:    Annotated[AsyncSession, Depends(get_db)] = None,
) -> list[DeviceRead]:
    is_admin = ctx.role == TenantRole.admin or ctx.user.is_super_admin
    devices, _ = await list_devices(
        db, tenant_id=ctx.tenant.id, skip=skip, limit=limit,
        user_id=ctx.user.id, user_is_admin=is_admin,
    )
    return [DeviceRead.model_validate(d) for d in devices]


@router.post("", response_model=DeviceRead, status_code=201)
async def add_device(
    data: DeviceCreate,
    ctx:  Annotated[TenantContext, Depends(require_reviewer)] = None,
    db:   Annotated[AsyncSession, Depends(get_db)] = None,
) -> DeviceRead:
    device = await create_device(db, data, tenant_id=ctx.tenant.id)
    return DeviceRead.model_validate(device)


@router.get("/{device_id}", response_model=DeviceRead)
async def get_device_by_id(
    device_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = None,
    db:  Annotated[AsyncSession, Depends(get_db)] = None,
) -> DeviceRead:
    try:
        device = await get_device(db, device_id, tenant_id=ctx.tenant.id)
    except DeviceNotFoundError:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    return DeviceRead.model_validate(device)


@router.put("/{device_id}", response_model=DeviceRead)
async def update_device_by_id(
    device_id: UUID,
    data: DeviceUpdate,
    ctx:  Annotated[TenantContext, Depends(require_reviewer)] = None,
    db:   Annotated[AsyncSession, Depends(get_db)] = None,
) -> DeviceRead:
    device = await update_device(db, device_id, data, tenant_id=ctx.tenant.id)
    return DeviceRead.model_validate(device)


@router.delete("/{device_id}", status_code=204)
async def delete_device_by_id(
    device_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_reviewer)] = None,
    db:  Annotated[AsyncSession, Depends(get_db)] = None,
) -> None:
    await delete_device(db, device_id, tenant_id=ctx.tenant.id)


@router.post("/{device_id}/health-check", response_model=DeviceRead)
async def run_health_check(
    device_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_reviewer)] = None,
    db:  Annotated[AsyncSession, Depends(get_db)] = None,
) -> DeviceRead:
    try:
        device = await health_check_device(db, device_id, tenant_id=ctx.tenant.id)
    except DeviceNotFoundError:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    return DeviceRead.model_validate(device)


@router.get("/{device_id}/bookstack/validate-page", response_model=BookstackPageInfo)
async def validate_bookstack_page(
    device_id: UUID,
    page_id: int = Query(...),
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)] = None,
    db:  Annotated[AsyncSession, Depends(get_db)] = None,
) -> BookstackPageInfo:
    """Validate that a BookStack page_id exists and return its title/preview (admin only)."""
    from app.services.bookstack_service import _fetch_page_info
    await get_device(db, device_id, tenant_id=ctx.tenant.id)
    return await _fetch_page_info(db, ctx.tenant.id, page_id)


@router.patch("/{device_id}/bookstack", response_model=DeviceRead)
async def link_device_bookstack(
    device_id: UUID,
    data: DeviceBookstackLink,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> DeviceRead:
    """Set BookStack page IDs for a device. Validates bookstack_page_id existence before saving (admin only)."""
    from app.services.bookstack_service import _fetch_page_info
    device = await get_device(db, device_id, tenant_id=ctx.tenant.id)

    if data.bookstack_page_id is not None:
        info = await _fetch_page_info(db, ctx.tenant.id, data.bookstack_page_id)
        if not info.valid:
            raise HTTPException(
                status_code=422,
                detail=f"Página BookStack #{data.bookstack_page_id} não encontrada: {info.error}",
            )
        device.bookstack_page_id = data.bookstack_page_id

    if data.bookstack_fm_page_id is not None:
        device.bookstack_fm_page_id = data.bookstack_fm_page_id
    if data.bookstack_doc_page_id is not None:
        device.bookstack_doc_page_id = data.bookstack_doc_page_id
    if data.bookstack_snapshot_page_id is not None:
        device.bookstack_snapshot_page_id = data.bookstack_snapshot_page_id
    await db.flush()
    await db.refresh(device)
    return DeviceRead.model_validate(device)


@router.post("/{device_id}/bookstack/snapshot", response_model=DocDraftResult)
async def trigger_device_snapshot(
    device_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> DocDraftResult:
    """Manually trigger a BookStack snapshot for a device (admin only).

    Runs the same logic as the daily Celery task but for a single device.
    Useful for testing the integration and for generating snapshots on demand.
    """
    from app.services.bookstack_service import publish_device_snapshot

    device = await get_device(db, device_id, tenant_id=ctx.tenant.id)
    try:
        await publish_device_snapshot(db, device)
        await db.flush()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return DocDraftResult(
        page_url="",  # snapshot writes in place; no single URL returned
        message="Snapshot publicado no BookStack com sucesso.",
    )


@router.post("/{device_id}/bookstack/generate-doc", response_model=DocDraftResult)
async def generate_doc_draft(
    device_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> DocDraftResult:
    """Generate an AI documentation draft and publish it to BookStack (admin only).

    On first call: creates a new '[FIREMANAGER DRAFT] {device} — Documentação' page.
    On subsequent calls: updates the same page with refreshed content.
    The human reviewer edits and approves directly in BookStack.
    """
    from app.services.bookstack_service import publish_doc_draft

    device = await get_device(db, device_id, tenant_id=ctx.tenant.id)
    try:
        page_url = await publish_doc_draft(db, device)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return DocDraftResult(
        page_url=page_url,
        message="Documentação gerada e publicada no BookStack com sucesso.",
    )
