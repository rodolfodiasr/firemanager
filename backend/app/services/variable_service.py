"""Variable resolution service — Tenant → Device inheritance."""
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.variable import DeviceVariable, TenantVariable, VariableType
from app.schemas.variable import ResolvedVariable

_VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")


# ── CRUD — Tenant Variables ───────────────────────────────────────────────────

async def list_tenant_variables(db: AsyncSession, tenant_id: UUID) -> list[TenantVariable]:
    result = await db.execute(
        select(TenantVariable).where(TenantVariable.tenant_id == tenant_id)
        .order_by(TenantVariable.name)
    )
    return list(result.scalars().all())


async def get_tenant_variable(db: AsyncSession, var_id: UUID, tenant_id: UUID) -> TenantVariable | None:
    result = await db.execute(
        select(TenantVariable).where(TenantVariable.id == var_id, TenantVariable.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def create_tenant_variable(
    db: AsyncSession, tenant_id: UUID, name: str, value: str,
    variable_type: VariableType = VariableType.string, description: str | None = None,
) -> TenantVariable:
    var = TenantVariable(
        tenant_id=tenant_id, name=name, value=value,
        variable_type=variable_type, description=description,
    )
    db.add(var)
    await db.flush()
    await db.refresh(var)
    return var


async def update_tenant_variable(
    db: AsyncSession, var_id: UUID, tenant_id: UUID,
    value: str | None = None, variable_type: VariableType | None = None,
    description: str | None = None,
) -> TenantVariable | None:
    var = await get_tenant_variable(db, var_id, tenant_id)
    if not var:
        return None
    if value is not None:
        var.value = value
    if variable_type is not None:
        var.variable_type = variable_type
    if description is not None:
        var.description = description
    await db.flush()
    await db.refresh(var)
    return var


async def delete_tenant_variable(db: AsyncSession, var_id: UUID, tenant_id: UUID) -> bool:
    var = await get_tenant_variable(db, var_id, tenant_id)
    if not var:
        return False
    await db.delete(var)
    return True


# ── CRUD — Device Variables ───────────────────────────────────────────────────

async def list_device_variables(db: AsyncSession, device_id: UUID) -> list[DeviceVariable]:
    result = await db.execute(
        select(DeviceVariable).where(DeviceVariable.device_id == device_id)
        .order_by(DeviceVariable.name)
    )
    return list(result.scalars().all())


async def get_device_variable(db: AsyncSession, var_id: UUID, device_id: UUID) -> DeviceVariable | None:
    result = await db.execute(
        select(DeviceVariable).where(DeviceVariable.id == var_id, DeviceVariable.device_id == device_id)
    )
    return result.scalar_one_or_none()


async def create_device_variable(
    db: AsyncSession, device_id: UUID, tenant_id: UUID, name: str, value: str,
    variable_type: VariableType = VariableType.string, description: str | None = None,
) -> DeviceVariable:
    var = DeviceVariable(
        device_id=device_id, tenant_id=tenant_id, name=name, value=value,
        variable_type=variable_type, description=description,
    )
    db.add(var)
    await db.flush()
    await db.refresh(var)
    return var


async def update_device_variable(
    db: AsyncSession, var_id: UUID, device_id: UUID,
    value: str | None = None, variable_type: VariableType | None = None,
    description: str | None = None,
) -> DeviceVariable | None:
    var = await get_device_variable(db, var_id, device_id)
    if not var:
        return None
    if value is not None:
        var.value = value
    if variable_type is not None:
        var.variable_type = variable_type
    if description is not None:
        var.description = description
    await db.flush()
    await db.refresh(var)
    return var


async def delete_device_variable(db: AsyncSession, var_id: UUID, device_id: UUID) -> bool:
    var = await get_device_variable(db, var_id, device_id)
    if not var:
        return False
    await db.delete(var)
    return True


# ── Resolution (Tenant → Device inheritance) ─────────────────────────────────

async def resolve_variables(
    db: AsyncSession, device_id: UUID, tenant_id: UUID
) -> tuple[dict[str, str], list[ResolvedVariable]]:
    """
    Returns (merged_dict, resolved_list).
    Device variables override tenant variables with the same name.
    resolved_list carries source info for the preview UI.
    """
    tenant_vars = await list_tenant_variables(db, tenant_id)
    device_vars = await list_device_variables(db, device_id)

    device_names = {v.name for v in device_vars}

    resolved: list[ResolvedVariable] = []
    merged: dict[str, str] = {}

    for tv in tenant_vars:
        merged[tv.name] = tv.value
        resolved.append(ResolvedVariable(
            name=tv.name, value=tv.value,
            variable_type=tv.variable_type, source="tenant",
        ))

    for dv in device_vars:
        merged[dv.name] = dv.value
        # Replace the tenant entry if it existed, else append
        for i, r in enumerate(resolved):
            if r.name == dv.name:
                resolved[i] = ResolvedVariable(
                    name=dv.name, value=dv.value,
                    variable_type=dv.variable_type, source="device",
                )
                break
        else:
            resolved.append(ResolvedVariable(
                name=dv.name, value=dv.value,
                variable_type=dv.variable_type, source="device",
            ))

    _ = device_names  # used implicitly via device_vars loop above
    return merged, resolved


def substitute(text: str, variables: dict[str, str]) -> tuple[str, list[str]]:
    """
    Replace {{var_name}} with values from the dict.
    Returns (resolved_text, list_of_unresolved_names).
    """
    result = text
    for name, value in variables.items():
        result = result.replace(f"{{{{{name}}}}}", value)

    unresolved = _VAR_PATTERN.findall(result)
    return result, unresolved


async def resolve_and_substitute(
    db: AsyncSession, device_id: UUID, tenant_id: UUID, text: str
) -> tuple[str, list[ResolvedVariable], list[str]]:
    """
    Convenience: resolve variables for a device then substitute in text.
    Returns (resolved_text, resolved_vars, unresolved_names).
    Only returns variables that were actually referenced in the text.
    """
    merged, all_resolved = await resolve_variables(db, device_id, tenant_id)

    referenced_names = set(_VAR_PATTERN.findall(text))
    used_resolved = [r for r in all_resolved if r.name in referenced_names]

    resolved_text, unresolved = substitute(text, merged)
    return resolved_text, used_resolved, unresolved
