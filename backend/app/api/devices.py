from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.schemas.device import DeviceCreate, DeviceRead, DeviceUpdate
from app.services.device_service import (
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
    devices, _ = await list_devices(db, tenant_id=ctx.tenant.id, skip=skip, limit=limit)
    return [DeviceRead.model_validate(d) for d in devices]


@router.post("", response_model=DeviceRead, status_code=201)
async def add_device(
    data: DeviceCreate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)] = None,
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
    device = await get_device(db, device_id, tenant_id=ctx.tenant.id)
    return DeviceRead.model_validate(device)


@router.put("/{device_id}", response_model=DeviceRead)
async def update_device_by_id(
    device_id: UUID,
    data: DeviceUpdate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)] = None,
    db:   Annotated[AsyncSession, Depends(get_db)] = None,
) -> DeviceRead:
    device = await update_device(db, device_id, data, tenant_id=ctx.tenant.id)
    return DeviceRead.model_validate(device)


@router.delete("/{device_id}", status_code=204)
async def delete_device_by_id(
    device_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = None,
    db:  Annotated[AsyncSession, Depends(get_db)] = None,
) -> None:
    await delete_device(db, device_id, tenant_id=ctx.tenant.id)


@router.post("/{device_id}/health-check", response_model=DeviceRead)
async def run_health_check(
    device_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)] = None,
    db:  Annotated[AsyncSession, Depends(get_db)] = None,
) -> DeviceRead:
    device = await health_check_device(db, device_id, tenant_id=ctx.tenant.id)
    return DeviceRead.model_validate(device)
