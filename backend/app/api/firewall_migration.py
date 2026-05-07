"""Firewall Migration API — Fase 16 firewall rule migration planning and apply."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_reviewer
from app.database import get_db
from app.models.firewall_migration import FirewallMigration, FirewallMigrationStatus
from app.models.device import Device
from app.schemas.firewall_migration import (
    FirewallCommandsUpdate,
    FirewallMigrationCreate,
    FirewallMigrationListItem,
    FirewallMigrationRead,
)

router = APIRouter()


@router.post("", response_model=FirewallMigrationRead, status_code=201)
async def create_firewall_migration(
    data: FirewallMigrationCreate,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> FirewallMigrationRead:
    src = await db.get(Device, UUID(data.source_device_id))
    tgt = await db.get(Device, UUID(data.target_device_id))

    if not src or src.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Dispositivo de origem não encontrado")
    if not tgt or tgt.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Dispositivo de destino não encontrado")
    if src.id == tgt.id:
        raise HTTPException(400, "Dispositivo de origem e destino não podem ser iguais")

    migration = FirewallMigration(
        tenant_id=ctx.tenant.id,
        source_device_id=src.id,
        target_device_id=tgt.id,
        source_vendor=src.vendor.value,
        target_vendor=tgt.vendor.value,
        status=FirewallMigrationStatus.analyzing,
    )
    db.add(migration)
    await db.flush()
    await db.refresh(migration)
    migration_id = str(migration.id)

    await db.commit()

    from app.workers.firewall_migration_worker import analyze_firewall_migration
    analyze_firewall_migration.delay(migration_id)

    await db.refresh(migration)
    return FirewallMigrationRead.model_validate(migration)


@router.get("", response_model=list[FirewallMigrationListItem])
async def list_firewall_migrations(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[FirewallMigrationListItem]:
    rows = await db.execute(
        select(FirewallMigration)
        .where(FirewallMigration.tenant_id == ctx.tenant.id)
        .order_by(FirewallMigration.created_at.desc())
    )
    return [FirewallMigrationListItem.model_validate(r) for r in rows.scalars().all()]


@router.get("/{migration_id}", response_model=FirewallMigrationRead)
async def get_firewall_migration(
    migration_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> FirewallMigrationRead:
    row = await db.get(FirewallMigration, migration_id)
    if not row or row.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Migração não encontrada")
    return FirewallMigrationRead.model_validate(row)


@router.patch("/{migration_id}/commands", response_model=FirewallMigrationRead)
async def update_firewall_commands(
    migration_id: UUID,
    data: FirewallCommandsUpdate,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> FirewallMigrationRead:
    row = await db.get(FirewallMigration, migration_id)
    if not row or row.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Migração não encontrada")
    if row.status not in (FirewallMigrationStatus.ready, FirewallMigrationStatus.failed):
        raise HTTPException(400, "Comandos só podem ser editados quando status é 'ready' ou 'failed'")

    row.commands_preview = data.commands_preview
    row.status = FirewallMigrationStatus.ready
    await db.commit()
    await db.refresh(row)
    return FirewallMigrationRead.model_validate(row)


@router.post("/{migration_id}/apply", status_code=202)
async def apply_firewall_migration(
    migration_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    row = await db.get(FirewallMigration, migration_id)
    if not row or row.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Migração não encontrada")
    if row.status != FirewallMigrationStatus.ready:
        raise HTTPException(400, "Migração precisa ter status 'ready' para ser aplicada")

    from app.workers.firewall_migration_worker import apply_firewall_migration as _apply_task
    _apply_task.delay(str(migration_id))

    row.status = FirewallMigrationStatus.applying
    await db.commit()
    return {"queued": True, "migration_id": str(migration_id)}


@router.delete("/{migration_id}", status_code=204)
async def delete_firewall_migration(
    migration_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = await db.get(FirewallMigration, migration_id)
    if not row or row.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Migração não encontrada")
    if row.status == FirewallMigrationStatus.applying:
        raise HTTPException(400, "Não é possível excluir uma migração em execução")
    await db.delete(row)
    await db.commit()
