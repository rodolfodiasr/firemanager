"""API — Segmentos de Rede (agrupamento de dispositivos para análise de conectividade)."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import get_db
from app.models.connectivity import ConnectivityAnalysis, ConnectivityStatus
from app.models.device import Device
from app.models.network_segments import NetworkSegment, NetworkSegmentMember
from app.models.user_tenant_role import TenantRole

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class NetworkSegmentCreate(BaseModel):
    name: str
    description: str | None = None
    cidr: str | None = None
    device_ids: list[UUID] = []


class NetworkSegmentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    cidr: str | None = None
    device_ids: list[UUID] | None = None


class DeviceInSegment(BaseModel):
    id: UUID
    name: str
    vendor: str
    category: str
    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_device(cls, d: Device) -> "DeviceInSegment":
        return cls(
            id=d.id,
            name=d.name,
            vendor=d.vendor,
            category=d.category.value if hasattr(d.category, "value") else str(d.category),
        )


class NetworkSegmentRead(BaseModel):
    id: UUID
    tenant_id: UUID
    created_by: UUID | None
    name: str
    description: str | None
    cidr: str | None
    device_count: int
    created_at: str
    updated_at: str


class NetworkSegmentDetail(NetworkSegmentRead):
    devices: list[DeviceInSegment]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_segment(db: AsyncSession, segment_id: UUID, tenant_id: UUID) -> NetworkSegment:
    result = await db.execute(
        select(NetworkSegment).where(
            NetworkSegment.id == segment_id,
            NetworkSegment.tenant_id == tenant_id,
        )
    )
    seg = result.scalar_one_or_none()
    if not seg:
        raise HTTPException(status_code=404, detail="Segmento não encontrado")
    return seg


async def _get_segment_devices(db: AsyncSession, segment_id: UUID) -> list[Device]:
    result = await db.execute(
        select(Device)
        .join(NetworkSegmentMember, Device.id == NetworkSegmentMember.device_id)
        .where(NetworkSegmentMember.segment_id == segment_id)
        .order_by(Device.name)
    )
    return list(result.scalars().all())


def _to_read(seg: NetworkSegment, device_count: int) -> NetworkSegmentRead:
    return NetworkSegmentRead(
        id=seg.id,
        tenant_id=seg.tenant_id,
        created_by=seg.created_by,
        name=seg.name,
        description=seg.description,
        cidr=seg.cidr,
        device_count=device_count,
        created_at=seg.created_at.isoformat(),
        updated_at=seg.updated_at.isoformat(),
    )


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[NetworkSegmentRead])
async def list_segments(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[NetworkSegmentRead]:
    result = await db.execute(
        select(NetworkSegment)
        .where(NetworkSegment.tenant_id == ctx.tenant.id)
        .order_by(NetworkSegment.name)
    )
    segs = list(result.scalars().all())
    if not segs:
        return []
    seg_ids = [s.id for s in segs]
    count_result = await db.execute(
        select(NetworkSegmentMember.segment_id, func.count().label("cnt"))
        .where(NetworkSegmentMember.segment_id.in_(seg_ids))
        .group_by(NetworkSegmentMember.segment_id)
    )
    counts = {row.segment_id: row.cnt for row in count_result}
    return [_to_read(s, counts.get(s.id, 0)) for s in segs]


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=NetworkSegmentDetail, status_code=201)
async def create_segment(
    data: NetworkSegmentCreate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> NetworkSegmentDetail:
    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão.")
    for device_id in data.device_ids:
        r = await db.execute(
            select(Device).where(Device.id == device_id, Device.tenant_id == ctx.tenant.id)
        )
        if not r.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Dispositivo {device_id} não encontrado")
    seg = NetworkSegment(
        tenant_id=ctx.tenant.id,
        created_by=ctx.user.id,
        name=data.name,
        description=data.description,
        cidr=data.cidr,
    )
    db.add(seg)
    await db.flush()
    await db.refresh(seg)
    for device_id in data.device_ids:
        db.add(NetworkSegmentMember(segment_id=seg.id, device_id=device_id))
    await db.flush()
    devices = await _get_segment_devices(db, seg.id)
    base = _to_read(seg, len(devices))
    return NetworkSegmentDetail(
        **base.model_dump(),
        devices=[DeviceInSegment.from_orm_device(d) for d in devices],
    )


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{segment_id}", response_model=NetworkSegmentDetail)
async def get_segment(
    segment_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> NetworkSegmentDetail:
    seg = await _get_segment(db, segment_id, ctx.tenant.id)
    devices = await _get_segment_devices(db, seg.id)
    base = _to_read(seg, len(devices))
    return NetworkSegmentDetail(
        **base.model_dump(),
        devices=[DeviceInSegment.from_orm_device(d) for d in devices],
    )


# ── Update ────────────────────────────────────────────────────────────────────

@router.put("/{segment_id}", response_model=NetworkSegmentDetail)
async def update_segment(
    segment_id: UUID,
    data: NetworkSegmentUpdate,
    ctx:  Annotated[TenantContext, Depends(get_tenant_context)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> NetworkSegmentDetail:
    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão.")
    seg = await _get_segment(db, segment_id, ctx.tenant.id)
    if data.name is not None:
        seg.name = data.name
    if data.description is not None:
        seg.description = data.description
    if data.cidr is not None:
        seg.cidr = data.cidr
    if data.device_ids is not None:
        for device_id in data.device_ids:
            r = await db.execute(
                select(Device).where(Device.id == device_id, Device.tenant_id == ctx.tenant.id)
            )
            if not r.scalar_one_or_none():
                raise HTTPException(status_code=404, detail=f"Dispositivo {device_id} não encontrado")
        await db.execute(delete(NetworkSegmentMember).where(NetworkSegmentMember.segment_id == seg.id))
        for device_id in data.device_ids:
            db.add(NetworkSegmentMember(segment_id=seg.id, device_id=device_id))
    await db.flush()
    await db.refresh(seg)
    devices = await _get_segment_devices(db, seg.id)
    base = _to_read(seg, len(devices))
    return NetworkSegmentDetail(
        **base.model_dump(),
        devices=[DeviceInSegment.from_orm_device(d) for d in devices],
    )


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{segment_id}", status_code=204)
async def delete_segment(
    segment_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    if ctx.role == TenantRole.readonly:
        raise HTTPException(status_code=403, detail="Sem permissão.")
    seg = await _get_segment(db, segment_id, ctx.tenant.id)
    await db.delete(seg)


# ── Bulk Connectivity Analysis ────────────────────────────────────────────────

@router.post("/{segment_id}/analyze", status_code=201)
async def analyze_segment(
    segment_id: UUID,
    background_tasks: BackgroundTasks,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Dispara análise individual de conectividade para cada device do segmento."""
    seg = await _get_segment(db, segment_id, ctx.tenant.id)
    devices = await _get_segment_devices(db, seg.id)
    if not devices:
        raise HTTPException(status_code=400, detail="O segmento não possui dispositivos.")

    from app.services.connectivity_service import run_analysis

    analysis_ids = []
    for device in devices:
        record = ConnectivityAnalysis(
            tenant_id=device.tenant_id,
            device_id=device.id,
            mode="single",
            status=ConnectivityStatus.pending,
        )
        db.add(record)
        await db.flush()
        await db.refresh(record)
        analysis_id = str(record.id)
        await db.commit()
        background_tasks.add_task(run_analysis, analysis_id)
        analysis_ids.append({"device_id": str(device.id), "device_name": device.name, "analysis_id": analysis_id})

    return {
        "segment_name": seg.name,
        "device_count": len(devices),
        "analyses": analysis_ids,
    }
