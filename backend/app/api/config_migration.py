"""Config Migration API — switch configuration migration planning and apply."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_tenant_context, require_reviewer
from app.database import get_db
from app.models.config_migration import ConfigMigration, MigrationStatus
from app.models.device import Device
from app.schemas.migration import (
    MigrationCreate,
    MigrationListItem,
    MigrationRead,
    PortMappingUpdate,
)

router = APIRouter()


@router.post("", response_model=MigrationRead, status_code=201)
async def create_migration(
    data: MigrationCreate,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> MigrationRead:
    src = await db.get(Device, UUID(data.source_device_id))
    tgt = await db.get(Device, UUID(data.target_device_id))

    if not src or src.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Dispositivo de origem não encontrado")
    if not tgt or tgt.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Dispositivo de destino não encontrado")
    if src.id == tgt.id:
        raise HTTPException(400, "Dispositivo de origem e destino não podem ser iguais")

    migration = ConfigMigration(
        tenant_id=ctx.tenant.id,
        source_device_id=src.id,
        target_device_id=tgt.id,
        source_vendor=src.vendor.value,
        target_vendor=tgt.vendor.value,
        status=MigrationStatus.analyzing,
    )
    db.add(migration)
    await db.flush()
    await db.refresh(migration)

    # Dispatch Celery task
    from app.workers.migration_worker import analyze_config_migration
    analyze_config_migration.delay(str(migration.id))

    await db.commit()
    await db.refresh(migration)
    return MigrationRead.model_validate(migration)


@router.get("", response_model=list[MigrationListItem])
async def list_migrations(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[MigrationListItem]:
    rows = await db.execute(
        select(ConfigMigration)
        .where(ConfigMigration.tenant_id == ctx.tenant.id)
        .order_by(ConfigMigration.created_at.desc())
    )
    return [MigrationListItem.model_validate(r) for r in rows.scalars().all()]


@router.get("/{migration_id}", response_model=MigrationRead)
async def get_migration(
    migration_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> MigrationRead:
    row = await db.get(ConfigMigration, migration_id)
    if not row or row.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Migração não encontrada")
    return MigrationRead.model_validate(row)


@router.patch("/{migration_id}/port-mapping", response_model=MigrationRead)
async def update_port_mapping(
    migration_id: UUID,
    data: PortMappingUpdate,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> MigrationRead:
    row = await db.get(ConfigMigration, migration_id)
    if not row or row.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Migração não encontrada")
    if row.status not in (MigrationStatus.ready, MigrationStatus.failed):
        raise HTTPException(400, "Mapeamento só pode ser atualizado quando status é 'ready' ou 'failed'")

    from app.services.config_renderer import render_config
    ir = row.migration_plan or {}
    rendered = render_config(ir, row.target_vendor, data.port_mapping)

    row.port_mapping = data.port_mapping
    row.commands_preview = "\n".join(rendered["commands"])
    # Keep non-mapping warnings, replace mapping warnings
    existing = [w for w in (row.warnings or []) if "sem mapeamento" not in w]
    row.warnings = existing + rendered["warnings"]
    row.status = MigrationStatus.ready

    await db.commit()
    await db.refresh(row)
    return MigrationRead.model_validate(row)


@router.post("/{migration_id}/apply", status_code=202)
async def apply_migration(
    migration_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    row = await db.get(ConfigMigration, migration_id)
    if not row or row.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Migração não encontrada")
    if row.status != MigrationStatus.ready:
        raise HTTPException(400, "Migração precisa ter status 'ready' para ser aplicada")

    from app.workers.migration_worker import apply_config_migration
    apply_config_migration.delay(str(migration_id))

    row.status = MigrationStatus.applying
    await db.commit()
    return {"queued": True, "migration_id": str(migration_id)}


@router.delete("/{migration_id}", status_code=204)
async def delete_migration(
    migration_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = await db.get(ConfigMigration, migration_id)
    if not row or row.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Migração não encontrada")
    if row.status == MigrationStatus.applying:
        raise HTTPException(400, "Não é possível excluir uma migração em execução")
    await db.delete(row)
    await db.commit()
