import asyncio
from collections import defaultdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.bulk_job import BulkJob, BulkJobStatus
from app.models.device import Device
from app.models.operation import Operation, OperationStatus
from app.models.user_tenant_role import TenantRole
from app.schemas.bulk_job import BulkJobCreate, BulkJobDetail, BulkJobRead, CategoryPlanSummary
from app.schemas.operation import OperationRead
from app.services.device_service import DeviceNotFoundError, get_device
from app.services.operation_service import execute_operation, start_or_continue_operation

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_bulk_job(db: AsyncSession, bulk_job_id: UUID, tenant_id: UUID) -> BulkJob:
    result = await db.execute(
        select(BulkJob).where(BulkJob.id == bulk_job_id, BulkJob.tenant_id == tenant_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return job


async def _get_job_operations(db: AsyncSession, bulk_job_id: UUID) -> list[Operation]:
    result = await db.execute(
        select(Operation)
        .where(Operation.bulk_job_id == bulk_job_id)
        .order_by(Operation.created_at)
    )
    return list(result.scalars().all())


async def _fetch_devices_map(db: AsyncSession, ops: list[Operation]) -> dict[UUID, Device]:
    """Load devices for a list of operations (for enriching OperationRead)."""
    device_ids = list({o.device_id for o in ops})
    if not device_ids:
        return {}
    result = await db.execute(select(Device).where(Device.id.in_(device_ids)))
    return {d.id: d for d in result.scalars().all()}


def _compute_status(ops: list[Operation]) -> BulkJobStatus:
    statuses = {o.status for o in ops}
    if all(s == OperationStatus.completed for s in (o.status for o in ops)):
        return BulkJobStatus.completed
    if all(s == OperationStatus.failed for s in (o.status for o in ops)):
        return BulkJobStatus.failed
    if OperationStatus.executing in statuses:
        return BulkJobStatus.executing
    if {OperationStatus.completed, OperationStatus.failed} & statuses:
        return BulkJobStatus.partial
    if all(s == OperationStatus.approved for s in (o.status for o in ops)):
        return BulkJobStatus.ready
    return BulkJobStatus.pending


def _build_op_reads(ops: list[Operation], devices: dict[UUID, Device]) -> list[OperationRead]:
    reads: list[OperationRead] = []
    for op in ops:
        r = OperationRead.model_validate(op)
        dev = devices.get(op.device_id)
        if dev:
            r.device_name = dev.name
            r.device_category = dev.category.value
        reads.append(r)
    return reads


def _build_category_plans(ops: list[Operation], devices: dict[UUID, Device]) -> list[CategoryPlanSummary] | None:
    """Group ops by device category and return per-category plan summary."""
    by_cat: dict[str, list[Operation]] = defaultdict(list)
    for op in ops:
        dev = devices.get(op.device_id)
        cat = dev.category.value if dev else "unknown"
        by_cat[cat].append(op)

    if len(by_cat) <= 1:
        return None

    summaries: list[CategoryPlanSummary] = []
    for cat, cat_ops in by_cat.items():
        # Use the intent from the first operation in this category group
        representative_intent = next((o.intent for o in cat_ops if o.intent), None)
        summaries.append(CategoryPlanSummary(
            category=cat,
            device_count=len(cat_ops),
            intent=representative_intent,
        ))
    return summaries


async def _build_detail(db: AsyncSession, job: BulkJob, ops: list[Operation]) -> BulkJobDetail:
    devices = await _fetch_devices_map(db, ops)
    op_reads = _build_op_reads(ops, devices)
    category_plans = _build_category_plans(ops, devices)
    return BulkJobDetail(
        **BulkJobRead.model_validate(job).model_dump(),
        operations=op_reads,
        category_plans=category_plans,
    )


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=BulkJobDetail, status_code=201)
async def create_bulk_job(
    data: BulkJobCreate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> BulkJobDetail:
    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão para criar operações.")

    # Validate and load all devices
    devices_map: dict[UUID, Device] = {}
    for device_id in data.device_ids:
        try:
            dev = await get_device(db, device_id, tenant_id=ctx.tenant.id)
            devices_map[device_id] = dev
        except DeviceNotFoundError:
            raise HTTPException(status_code=404, detail=f"Dispositivo {device_id} não encontrado")

    # ── Phase 9: group by category ─────────────────────────────────────────────
    # Preserve the original ordering within each group
    category_groups: dict[str, list[UUID]] = defaultdict(list)
    for device_id in data.device_ids:
        cat = devices_map[device_id].category.value
        category_groups[cat].append(device_id)

    is_cross_device = len(category_groups) > 1

    # Create the BulkJob record
    bulk_job = BulkJob(
        tenant_id=ctx.tenant.id,
        created_by=ctx.user.id,
        description=data.natural_language_input,
        device_count=len(data.device_ids),
        status=BulkJobStatus.pending,
    )
    db.add(bulk_job)
    await db.flush()
    await db.refresh(bulk_job)

    # ── One AI call per category group ─────────────────────────────────────────
    intents_by_category: dict[str, str | None] = {}

    for category, cat_device_ids in category_groups.items():
        first_id = cat_device_ids[0]

        # Generate plan via AI for the first device in this category
        first_op, _ = await start_or_continue_operation(
            db=db,
            user_id=ctx.user.id,
            operation_id=None,
            device_id=first_id,
            user_message=data.natural_language_input,
        )
        first_op.bulk_job_id = bulk_job.id
        await db.flush()

        intents_by_category[category] = first_op.intent

        # Copy plan to all remaining devices in this category
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

    # Update BulkJob metadata
    if is_cross_device:
        bulk_job.intent = "cross_device"
    else:
        first_cat = next(iter(category_groups))
        bulk_job.intent = intents_by_category.get(first_cat)

    ops = await _get_job_operations(db, bulk_job.id)
    all_approved = all(o.status == OperationStatus.approved for o in ops)
    bulk_job.status = BulkJobStatus.ready if all_approved else BulkJobStatus.pending
    await db.flush()
    await db.refresh(bulk_job)

    return await _build_detail(db, bulk_job, ops)


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[BulkJobRead])
async def list_bulk_jobs(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[BulkJobRead]:
    result = await db.execute(
        select(BulkJob)
        .where(BulkJob.tenant_id == ctx.tenant.id)
        .order_by(BulkJob.created_at.desc())
        .limit(50)
    )
    jobs = list(result.scalars().all())
    return [BulkJobRead.model_validate(j) for j in jobs]


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{bulk_job_id}", response_model=BulkJobDetail)
async def get_bulk_job(
    bulk_job_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> BulkJobDetail:
    job = await _get_bulk_job(db, bulk_job_id, ctx.tenant.id)
    ops = await _get_job_operations(db, bulk_job_id)

    # Recompute counts
    job.completed_count = sum(1 for o in ops if o.status == OperationStatus.completed)
    job.failed_count    = sum(1 for o in ops if o.status == OperationStatus.failed)
    job.status          = _compute_status(ops)
    await db.flush()

    return await _build_detail(db, job, ops)


# ── Execute ───────────────────────────────────────────────────────────────────

@router.post("/{bulk_job_id}/execute", response_model=BulkJobDetail)
async def execute_bulk_job(
    bulk_job_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> BulkJobDetail:
    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão para executar operações.")

    job = await _get_bulk_job(db, bulk_job_id, ctx.tenant.id)

    if job.status not in (BulkJobStatus.ready, BulkJobStatus.partial):
        raise HTTPException(
            status_code=400,
            detail=f"Job não pode ser executado no estado '{job.status.value}'",
        )

    job.status = BulkJobStatus.executing
    await db.flush()

    ops = await _get_job_operations(db, bulk_job_id)
    executable = [
        o for o in ops
        if o.status in (OperationStatus.approved, OperationStatus.pending)
    ]

    errors: list[str] = []
    for op in executable:
        try:
            await execute_operation(db, op.id)
        except Exception as exc:
            errors.append(f"{op.device_id}: {exc}")

    await db.flush()
    ops = await _get_job_operations(db, bulk_job_id)
    job.completed_count = sum(1 for o in ops if o.status == OperationStatus.completed)
    job.failed_count    = sum(1 for o in ops if o.status == OperationStatus.failed)
    job.status          = _compute_status(ops)
    if errors:
        job.error_summary = "\n".join(errors)
    await db.flush()
    await db.refresh(job)

    return await _build_detail(db, job, ops)


# ── Cancel ────────────────────────────────────────────────────────────────────

@router.delete("/{bulk_job_id}", status_code=204)
async def cancel_bulk_job(
    bulk_job_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    job = await _get_bulk_job(db, bulk_job_id, ctx.tenant.id)
    if job.status in (BulkJobStatus.executing, BulkJobStatus.completed):
        raise HTTPException(status_code=400, detail="Job não pode ser cancelado neste estado.")
    await db.delete(job)
