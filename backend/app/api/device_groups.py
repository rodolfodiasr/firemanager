from collections import defaultdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.bulk_job import BulkJob, BulkJobStatus
from app.models.device import Device
from app.models.device_group import DeviceGroup, DeviceGroupMember
from app.models.operation import Operation, OperationStatus
from app.models.user_tenant_role import TenantRole
from app.schemas.bulk_job import BulkJobDetail, BulkJobRead, CategoryPlanSummary
from app.schemas.device_group import (
    DeviceGroupCreate, DeviceGroupDetail, DeviceGroupRead,
    DeviceGroupUpdate, DeviceInGroup, GroupBulkJobCreate,
)
from app.schemas.operation import OperationRead
from app.services.device_service import get_device, DeviceNotFoundError
from app.services.operation_service import execute_operation, start_or_continue_operation

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_group(db: AsyncSession, group_id: UUID, tenant_id: UUID) -> DeviceGroup:
    result = await db.execute(
        select(DeviceGroup).where(
            DeviceGroup.id == group_id,
            DeviceGroup.tenant_id == tenant_id,
        )
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    return group


async def _get_group_devices(db: AsyncSession, group_id: UUID) -> list[Device]:
    result = await db.execute(
        select(Device)
        .join(DeviceGroupMember, Device.id == DeviceGroupMember.device_id)
        .where(DeviceGroupMember.group_id == group_id)
        .order_by(Device.name)
    )
    return list(result.scalars().all())


async def _category_counts_for_groups(
    db: AsyncSession, group_ids: list[UUID]
) -> dict[UUID, dict[str, int]]:
    """Return {group_id: {category: count}} for a set of groups."""
    if not group_ids:
        return {}
    result = await db.execute(
        select(
            DeviceGroupMember.group_id,
            Device.category,
            func.count().label("cnt"),
        )
        .join(Device, Device.id == DeviceGroupMember.device_id)
        .where(DeviceGroupMember.group_id.in_(group_ids))
        .group_by(DeviceGroupMember.group_id, Device.category)
    )
    counts: dict[UUID, dict[str, int]] = defaultdict(dict)
    for row in result:
        counts[row.group_id][row.category.value] = row.cnt
    return counts


def _build_group_read(group: DeviceGroup, device_count: int, cat_counts: dict[str, int]) -> DeviceGroupRead:
    return DeviceGroupRead(
        id=group.id,
        tenant_id=group.tenant_id,
        created_by=group.created_by,
        name=group.name,
        description=group.description,
        device_count=device_count,
        category_counts=cat_counts,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


async def _member_count(db: AsyncSession, group_id: UUID) -> int:
    result = await db.execute(
        select(func.count()).where(DeviceGroupMember.group_id == group_id)
    )
    return result.scalar_one() or 0


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[DeviceGroupRead])
async def list_groups(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[DeviceGroupRead]:
    result = await db.execute(
        select(DeviceGroup)
        .where(DeviceGroup.tenant_id == ctx.tenant.id)
        .order_by(DeviceGroup.name)
    )
    groups = list(result.scalars().all())
    if not groups:
        return []

    group_ids = [g.id for g in groups]

    # Counts per group
    count_result = await db.execute(
        select(DeviceGroupMember.group_id, func.count().label("cnt"))
        .where(DeviceGroupMember.group_id.in_(group_ids))
        .group_by(DeviceGroupMember.group_id)
    )
    counts = {row.group_id: row.cnt for row in count_result}
    cat_counts = await _category_counts_for_groups(db, group_ids)

    return [
        _build_group_read(g, counts.get(g.id, 0), cat_counts.get(g.id, {}))
        for g in groups
    ]


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=DeviceGroupDetail, status_code=201)
async def create_group(
    data: DeviceGroupCreate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> DeviceGroupDetail:
    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão.")

    # Validate all devices belong to this tenant
    for device_id in data.device_ids:
        try:
            await get_device(db, device_id, tenant_id=ctx.tenant.id)
        except DeviceNotFoundError:
            raise HTTPException(status_code=404, detail=f"Dispositivo {device_id} não encontrado")

    group = DeviceGroup(
        tenant_id=ctx.tenant.id,
        created_by=ctx.user.id,
        name=data.name,
        description=data.description,
    )
    db.add(group)
    await db.flush()
    await db.refresh(group)

    for device_id in data.device_ids:
        db.add(DeviceGroupMember(group_id=group.id, device_id=device_id))
    await db.flush()

    devices = await _get_group_devices(db, group.id)
    cat_counts = await _category_counts_for_groups(db, [group.id])
    base = _build_group_read(group, len(devices), cat_counts.get(group.id, {}))
    return DeviceGroupDetail(
        **base.model_dump(),
        devices=[DeviceInGroup.model_validate(d) for d in devices],
    )


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{group_id}", response_model=DeviceGroupDetail)
async def get_group(
    group_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> DeviceGroupDetail:
    group = await _get_group(db, group_id, ctx.tenant.id)
    devices = await _get_group_devices(db, group.id)
    cat_counts = await _category_counts_for_groups(db, [group.id])
    base = _build_group_read(group, len(devices), cat_counts.get(group.id, {}))
    return DeviceGroupDetail(
        **base.model_dump(),
        devices=[DeviceInGroup.model_validate(d) for d in devices],
    )


# ── Update ────────────────────────────────────────────────────────────────────

@router.put("/{group_id}", response_model=DeviceGroupDetail)
async def update_group(
    group_id: UUID,
    data: DeviceGroupUpdate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> DeviceGroupDetail:
    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão.")

    group = await _get_group(db, group_id, ctx.tenant.id)

    if data.name is not None:
        group.name = data.name
    if data.description is not None:
        group.description = data.description

    if data.device_ids is not None:
        for device_id in data.device_ids:
            try:
                await get_device(db, device_id, tenant_id=ctx.tenant.id)
            except DeviceNotFoundError:
                raise HTTPException(status_code=404, detail=f"Dispositivo {device_id} não encontrado")
        # Replace all members
        await db.execute(delete(DeviceGroupMember).where(DeviceGroupMember.group_id == group.id))
        for device_id in data.device_ids:
            db.add(DeviceGroupMember(group_id=group.id, device_id=device_id))

    await db.flush()
    await db.refresh(group)

    devices = await _get_group_devices(db, group.id)
    cat_counts = await _category_counts_for_groups(db, [group.id])
    base = _build_group_read(group, len(devices), cat_counts.get(group.id, {}))
    return DeviceGroupDetail(
        **base.model_dump(),
        devices=[DeviceInGroup.model_validate(d) for d in devices],
    )


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão.")
    group = await _get_group(db, group_id, ctx.tenant.id)
    await db.delete(group)


# ── Apply — create BulkJob for this group ─────────────────────────────────────

@router.post("/{group_id}/bulk-job", response_model=BulkJobDetail, status_code=201)
async def group_bulk_job(
    group_id: UUID,
    data: GroupBulkJobCreate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> BulkJobDetail:
    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão.")

    group = await _get_group(db, group_id, ctx.tenant.id)
    devices = await _get_group_devices(db, group.id)

    if len(devices) < 1:
        raise HTTPException(status_code=400, detail="O grupo não possui dispositivos.")
    if len(devices) < 2:
        raise HTTPException(status_code=400, detail="O grupo precisa ter pelo menos 2 dispositivos para operação em lote.")

    # Group devices by category (Phase 9 logic)
    category_groups: dict[str, list[UUID]] = defaultdict(list)
    for dev in devices:
        category_groups[dev.category.value].append(dev.id)

    is_cross_device = len(category_groups) > 1

    bulk_job = BulkJob(
        tenant_id=ctx.tenant.id,
        created_by=ctx.user.id,
        description=f"[{group.name}] {data.natural_language_input}",
        device_count=len(devices),
        status=BulkJobStatus.pending,
    )
    db.add(bulk_job)
    await db.flush()
    await db.refresh(bulk_job)

    intents_by_category: dict[str, str | None] = {}

    for category, cat_device_ids in category_groups.items():
        first_op, _ = await start_or_continue_operation(
            db=db,
            user_id=ctx.user.id,
            operation_id=None,
            device_id=cat_device_ids[0],
            user_message=data.natural_language_input,
        )
        first_op.bulk_job_id = bulk_job.id
        await db.flush()
        intents_by_category[category] = first_op.intent

        for device_id in cat_device_ids[1:]:
            op = Operation(
                user_id=ctx.user.id,
                device_id=device_id,
                natural_language_input=data.natural_language_input,
                intent=first_op.intent,
                action_plan=first_op.action_plan,
                status=first_op.status,
                bulk_job_id=bulk_job.id,
            )
            db.add(op)

    await db.flush()

    bulk_job.intent = "cross_device" if is_cross_device else intents_by_category.get(next(iter(category_groups)))

    ops_result = await db.execute(
        select(Operation).where(Operation.bulk_job_id == bulk_job.id).order_by(Operation.created_at)
    )
    ops = list(ops_result.scalars().all())
    all_approved = all(o.status == OperationStatus.approved for o in ops)
    bulk_job.status = BulkJobStatus.ready if all_approved else BulkJobStatus.pending
    await db.flush()
    await db.refresh(bulk_job)

    # Build detail response with device info
    devices_map = {dev.id: dev for dev in devices}

    def _op_read(op: Operation) -> OperationRead:
        r = OperationRead.model_validate(op)
        dev = devices_map.get(op.device_id)
        if dev:
            r.device_name = dev.name
            r.device_category = dev.category.value
        return r

    from app.api.bulk_jobs import _build_category_plans
    cat_plans_raw = _build_category_plans(ops, {op.device_id: devices_map[op.device_id] for op in ops if op.device_id in devices_map})

    return BulkJobDetail(
        **BulkJobRead.model_validate(bulk_job).model_dump(),
        operations=[_op_read(o) for o in ops],
        category_plans=cat_plans_raw,
    )
