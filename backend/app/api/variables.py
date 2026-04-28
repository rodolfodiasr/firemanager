from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.user_tenant_role import TenantRole
from app.schemas.variable import (
    DeviceVariableCreate, DeviceVariableRead, DeviceVariableUpdate,
    TenantVariableCreate, TenantVariableRead, TenantVariableUpdate,
)
from app.services.device_service import DeviceNotFoundError, get_device
from app.services.variable_service import (
    create_device_variable, create_tenant_variable,
    delete_device_variable, delete_tenant_variable,
    get_device_variable, get_tenant_variable,
    list_device_variables, list_tenant_variables,
    update_device_variable, update_tenant_variable,
    resolve_variables,
)

router = APIRouter()


def _require_write(ctx: TenantContext) -> None:
    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão para modificar variáveis.")


# ── Tenant Variables ──────────────────────────────────────────────────────────

@router.get("/tenant", response_model=list[TenantVariableRead])
async def list_tenant_vars(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[TenantVariableRead]:
    vars_ = await list_tenant_variables(db, ctx.tenant.id)
    return [TenantVariableRead.model_validate(v) for v in vars_]


@router.post("/tenant", response_model=TenantVariableRead, status_code=201)
async def create_tenant_var(
    data: TenantVariableCreate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> TenantVariableRead:
    _require_write(ctx)
    try:
        var = await create_tenant_variable(
            db, ctx.tenant.id, data.name, data.value, data.variable_type, data.description
        )
    except Exception:
        raise HTTPException(status_code=409, detail=f"Variável '{data.name}' já existe neste tenant.")
    return TenantVariableRead.model_validate(var)


@router.put("/tenant/{var_id}", response_model=TenantVariableRead)
async def update_tenant_var(
    var_id: UUID,
    data: TenantVariableUpdate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> TenantVariableRead:
    _require_write(ctx)
    var = await update_tenant_variable(
        db, var_id, ctx.tenant.id, data.value, data.variable_type, data.description
    )
    if not var:
        raise HTTPException(status_code=404, detail="Variável não encontrada.")
    return TenantVariableRead.model_validate(var)


@router.delete("/tenant/{var_id}", status_code=204)
async def delete_tenant_var(
    var_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    _require_write(ctx)
    if not await delete_tenant_variable(db, var_id, ctx.tenant.id):
        raise HTTPException(status_code=404, detail="Variável não encontrada.")


# ── Device Variables ──────────────────────────────────────────────────────────

@router.get("/device/{device_id}", response_model=list[DeviceVariableRead])
async def list_device_vars(
    device_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[DeviceVariableRead]:
    try:
        await get_device(db, device_id, tenant_id=ctx.tenant.id)
    except DeviceNotFoundError:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado.")

    device_vars = await list_device_variables(db, device_id)
    tenant_vars  = await list_tenant_variables(db, ctx.tenant.id)
    tenant_names = {v.name for v in tenant_vars}

    reads: list[DeviceVariableRead] = []
    for dv in device_vars:
        r = DeviceVariableRead.model_validate(dv)
        r.overrides_tenant = dv.name in tenant_names
        reads.append(r)
    return reads


@router.post("/device/{device_id}", response_model=DeviceVariableRead, status_code=201)
async def create_device_var(
    device_id: UUID,
    data: DeviceVariableCreate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> DeviceVariableRead:
    _require_write(ctx)
    try:
        await get_device(db, device_id, tenant_id=ctx.tenant.id)
    except DeviceNotFoundError:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado.")
    try:
        var = await create_device_variable(
            db, device_id, ctx.tenant.id, data.name, data.value, data.variable_type, data.description
        )
    except Exception:
        raise HTTPException(status_code=409, detail=f"Variável '{data.name}' já existe neste dispositivo.")
    return DeviceVariableRead.model_validate(var)


@router.put("/device/{device_id}/{var_id}", response_model=DeviceVariableRead)
async def update_device_var(
    device_id: UUID,
    var_id: UUID,
    data: DeviceVariableUpdate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> DeviceVariableRead:
    _require_write(ctx)
    var = await update_device_variable(
        db, var_id, device_id, data.value, data.variable_type, data.description
    )
    if not var:
        raise HTTPException(status_code=404, detail="Variável não encontrada.")
    return DeviceVariableRead.model_validate(var)


@router.delete("/device/{device_id}/{var_id}", status_code=204)
async def delete_device_var(
    device_id: UUID,
    var_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    _require_write(ctx)
    if not await delete_device_variable(db, var_id, device_id):
        raise HTTPException(status_code=404, detail="Variável não encontrada.")


# ── Effective variables (merged tenant + device) ──────────────────────────────

@router.get("/device/{device_id}/effective", response_model=list[dict])
async def get_effective_vars(
    device_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    """Retorna as variáveis resolvidas após herança Tenant → Device."""
    try:
        await get_device(db, device_id, tenant_id=ctx.tenant.id)
    except DeviceNotFoundError:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado.")

    _, resolved = await resolve_variables(db, device_id, ctx.tenant.id)
    return [r.model_dump() for r in resolved]
