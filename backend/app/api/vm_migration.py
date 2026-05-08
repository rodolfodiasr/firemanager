"""Fase 27 — VM Migration Planner API."""
from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context
from app.database import AsyncSessionLocal, get_db
from app.models.vm_migration import MigrationRunbook, VmHypervisor, VmInventory
from app.utils.crypto import decrypt_credentials, encrypt_credentials

router = APIRouter()

CtxDep = Annotated[TenantContext, Depends(get_tenant_context)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


# ── Pydantic Schemas ───────────────────────────────────────────────────────────

class HypervisorCreate(BaseModel):
    name: str
    hypervisor_type: str  # vmware_vcenter | proxmox | hyper_v
    host: str
    credentials: dict  # {username, password} — will be encrypted
    verify_ssl: bool = False


class HypervisorRead(BaseModel):
    id: str
    name: str
    hypervisor_type: str
    host: str
    verify_ssl: bool
    is_active: bool
    last_sync_at: Optional[str]
    last_vm_count: Optional[int]
    created_at: str

    @classmethod
    def from_orm(cls, h: VmHypervisor) -> "HypervisorRead":
        return cls(
            id=str(h.id),
            name=h.name,
            hypervisor_type=h.hypervisor_type,
            host=h.host,
            verify_ssl=h.verify_ssl,
            is_active=h.is_active,
            last_sync_at=h.last_sync_at.isoformat() if h.last_sync_at else None,
            last_vm_count=h.last_vm_count,
            created_at=h.created_at.isoformat(),
        )


class VmInventoryRead(BaseModel):
    id: str
    hypervisor_id: str
    vm_id: str
    vm_name: str
    power_state: Optional[str]
    os_type: Optional[str]
    cpu_count: Optional[int]
    ram_mb: Optional[int]
    disk_gb: Optional[float]
    ip_addresses: Optional[list]
    tags: Optional[list]
    synced_at: str

    @classmethod
    def from_orm(cls, v: VmInventory) -> "VmInventoryRead":
        return cls(
            id=str(v.id),
            hypervisor_id=str(v.hypervisor_id),
            vm_id=v.vm_id,
            vm_name=v.vm_name,
            power_state=v.power_state,
            os_type=v.os_type,
            cpu_count=v.cpu_count,
            ram_mb=v.ram_mb,
            disk_gb=v.disk_gb,
            ip_addresses=v.ip_addresses,
            tags=v.tags,
            synced_at=v.synced_at.isoformat(),
        )


class RunbookCreate(BaseModel):
    title: str
    vm_ids: list[str]
    source_hypervisor_id: Optional[str] = None
    target_hypervisor_id: Optional[str] = None


class RunbookRead(BaseModel):
    id: str
    title: str
    vm_ids: list
    status: str
    ai_runbook: Optional[str]
    source_hypervisor_id: Optional[str]
    target_hypervisor_id: Optional[str]
    bookstack_page_url: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, r: MigrationRunbook) -> "RunbookRead":
        return cls(
            id=str(r.id),
            title=r.title,
            vm_ids=r.vm_ids or [],
            status=r.status,
            ai_runbook=r.ai_runbook,
            source_hypervisor_id=str(r.source_hypervisor_id) if r.source_hypervisor_id else None,
            target_hypervisor_id=str(r.target_hypervisor_id) if r.target_hypervisor_id else None,
            bookstack_page_url=r.bookstack_page_url,
            created_at=r.created_at.isoformat(),
            updated_at=r.updated_at.isoformat(),
        )


# ── Hypervisors ────────────────────────────────────────────────────────────────

@router.get("/hypervisors", response_model=list[HypervisorRead])
async def list_hypervisors(db: DbDep, ctx: CtxDep) -> list[HypervisorRead]:
    rows = (await db.execute(
        select(VmHypervisor)
        .where(VmHypervisor.tenant_id == ctx.tenant.id)
        .order_by(VmHypervisor.created_at)
    )).scalars().all()
    return [HypervisorRead.from_orm(h) for h in rows]


@router.post("/hypervisors", response_model=HypervisorRead, status_code=201)
async def create_hypervisor(body: HypervisorCreate, db: DbDep, ctx: CtxDep) -> HypervisorRead:
    valid_types = {"vmware_vcenter", "proxmox", "hyper_v"}
    if body.hypervisor_type not in valid_types:
        raise HTTPException(400, f"hypervisor_type deve ser um de: {', '.join(valid_types)}")

    h = VmHypervisor(
        tenant_id=ctx.tenant.id,
        name=body.name,
        hypervisor_type=body.hypervisor_type,
        host=body.host,
        encrypted_credentials=encrypt_credentials(body.credentials),
        verify_ssl=body.verify_ssl,
    )
    db.add(h)
    await db.flush()
    await db.refresh(h)
    return HypervisorRead.from_orm(h)


@router.delete("/hypervisors/{hypervisor_id}", status_code=204)
async def delete_hypervisor(hypervisor_id: UUID, db: DbDep, ctx: CtxDep) -> None:
    h = await db.get(VmHypervisor, hypervisor_id)
    if not h or h.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Hypervisor não encontrado")
    await db.delete(h)


@router.post("/hypervisors/{hypervisor_id}/test")
async def test_hypervisor(hypervisor_id: UUID, db: DbDep, ctx: CtxDep) -> dict:
    h = await db.get(VmHypervisor, hypervisor_id)
    if not h or h.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Hypervisor não encontrado")

    creds = decrypt_credentials(h.encrypted_credentials)

    if h.hypervisor_type == "vmware_vcenter":
        from app.services.vmware_service import VMwareService
        svc = VMwareService(
            host=h.host,
            username=creds.get("username", ""),
            password=creds.get("password", ""),
            verify_ssl=h.verify_ssl,
        )
        return await svc.test_connection()
    elif h.hypervisor_type == "proxmox":
        from app.services.proxmox_service import ProxmoxService
        svc = ProxmoxService(
            host=h.host,
            username=creds.get("username", ""),
            password=creds.get("password", ""),
            verify_ssl=h.verify_ssl,
        )
        return await svc.test_connection()
    else:
        raise HTTPException(400, "Teste de conexão não disponível para este tipo de hypervisor")


@router.post("/hypervisors/{hypervisor_id}/sync")
async def sync_hypervisor(hypervisor_id: UUID, db: DbDep, ctx: CtxDep) -> dict:
    h = await db.get(VmHypervisor, hypervisor_id)
    if not h or h.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Hypervisor não encontrado")

    from app.services.vm_sync_service import sync_hypervisor as _sync
    count = await _sync(db, h)
    return {"synced": count, "hypervisor_id": str(hypervisor_id)}


# ── VM Inventory ───────────────────────────────────────────────────────────────

@router.get("/inventory", response_model=list[VmInventoryRead])
async def list_inventory(
    db: DbDep,
    ctx: CtxDep,
    hypervisor_id: Optional[UUID] = None,
) -> list[VmInventoryRead]:
    query = select(VmInventory).where(VmInventory.tenant_id == ctx.tenant.id)
    if hypervisor_id is not None:
        query = query.where(VmInventory.hypervisor_id == hypervisor_id)
    query = query.order_by(VmInventory.vm_name)
    rows = (await db.execute(query)).scalars().all()
    return [VmInventoryRead.from_orm(v) for v in rows]


# ── Migration Runbooks ─────────────────────────────────────────────────────────

@router.get("/runbooks", response_model=list[RunbookRead])
async def list_runbooks(db: DbDep, ctx: CtxDep) -> list[RunbookRead]:
    rows = (await db.execute(
        select(MigrationRunbook)
        .where(MigrationRunbook.tenant_id == ctx.tenant.id)
        .order_by(MigrationRunbook.created_at.desc())
    )).scalars().all()
    return [RunbookRead.from_orm(r) for r in rows]


@router.post("/runbooks", response_model=RunbookRead, status_code=201)
async def create_runbook(
    body: RunbookCreate,
    background_tasks: BackgroundTasks,
    db: DbDep,
    ctx: CtxDep,
) -> RunbookRead:
    source_id = UUID(body.source_hypervisor_id) if body.source_hypervisor_id else None
    target_id = UUID(body.target_hypervisor_id) if body.target_hypervisor_id else None

    # Validate hypervisors belong to tenant
    if source_id:
        src = await db.get(VmHypervisor, source_id)
        if not src or src.tenant_id != ctx.tenant.id:
            raise HTTPException(404, "Hypervisor de origem não encontrado")
    if target_id:
        tgt = await db.get(VmHypervisor, target_id)
        if not tgt or tgt.tenant_id != ctx.tenant.id:
            raise HTTPException(404, "Hypervisor de destino não encontrado")

    runbook = MigrationRunbook(
        tenant_id=ctx.tenant.id,
        title=body.title,
        vm_ids=body.vm_ids,
        source_hypervisor_id=source_id,
        target_hypervisor_id=target_id,
        status="generating",
    )
    db.add(runbook)
    await db.flush()
    await db.refresh(runbook)

    runbook_id = str(runbook.id)
    tenant_name = ctx.tenant.name
    source_name = src.name if source_id else "Unknown"
    target_name = tgt.name if target_id else "Unknown"
    vm_ids_snapshot = list(body.vm_ids)

    background_tasks.add_task(
        _bg_generate_runbook,
        runbook_id,
        vm_ids_snapshot,
        source_name,
        target_name,
        tenant_name,
    )

    return RunbookRead.from_orm(runbook)


@router.get("/runbooks/{runbook_id}", response_model=RunbookRead)
async def get_runbook(runbook_id: UUID, db: DbDep, ctx: CtxDep) -> RunbookRead:
    r = await db.get(MigrationRunbook, runbook_id)
    if not r or r.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Runbook não encontrado")
    return RunbookRead.from_orm(r)


# ── Background task ────────────────────────────────────────────────────────────

async def _bg_generate_runbook(
    runbook_id: str,
    vm_ids: list[str],
    source_hypervisor: str,
    target_hypervisor: str,
    tenant_name: str,
) -> None:
    from app.services.vm_runbook_service import generate_migration_runbook

    async with AsyncSessionLocal() as db:
        runbook = await db.get(MigrationRunbook, UUID(runbook_id))
        if not runbook:
            return

        try:
            # Fetch VM details for the selected vm_ids
            vm_uuid_list = [UUID(vid) for vid in vm_ids if vid]
            vms: list[dict] = []
            for vm_uuid in vm_uuid_list:
                inv = await db.get(VmInventory, vm_uuid)
                if inv:
                    vms.append({
                        "vm_name": inv.vm_name,
                        "os_type": inv.os_type,
                        "cpu_count": inv.cpu_count,
                        "ram_mb": inv.ram_mb,
                        "disk_gb": inv.disk_gb,
                        "power_state": inv.power_state,
                        "ip_addresses": inv.ip_addresses or [],
                    })

            ai_text = await generate_migration_runbook(
                vms=vms,
                source_hypervisor=source_hypervisor,
                target_hypervisor=target_hypervisor,
                tenant_name=tenant_name,
            )

            runbook.ai_runbook = ai_text
            runbook.status = "ready"
            await db.commit()
        except Exception:
            runbook.status = "draft"
            await db.commit()
