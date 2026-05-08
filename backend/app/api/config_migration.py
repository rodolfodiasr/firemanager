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
    CommandsUpdate,
    InterfaceAdd,
    MigrationCreate,
    MigrationListItem,
    MigrationRead,
    PortMappingUpdate,
    RegenerateRequest,
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

    ai_level = max(1, min(3, data.ai_level))  # clamp to valid range

    migration = ConfigMigration(
        tenant_id=ctx.tenant.id,
        source_device_id=src.id,
        target_device_id=tgt.id,
        source_vendor=src.vendor.value,
        target_vendor=tgt.vendor.value,
        status=MigrationStatus.analyzing,
        ai_level=ai_level,
    )
    db.add(migration)
    await db.flush()
    await db.refresh(migration)
    migration_id = str(migration.id)

    # Commit first so the worker can find the record in the DB
    await db.commit()

    # Dispatch Celery task only after commit
    from app.workers.migration_worker import analyze_config_migration
    analyze_config_migration.delay(migration_id)

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


@router.patch("/{migration_id}/commands", response_model=MigrationRead)
async def update_commands(
    migration_id: UUID,
    data: CommandsUpdate,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> MigrationRead:
    row = await db.get(ConfigMigration, migration_id)
    if not row or row.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Migração não encontrada")
    if row.status not in (MigrationStatus.ready, MigrationStatus.failed):
        raise HTTPException(400, "Comandos só podem ser editados quando status é 'ready' ou 'failed'")

    row.commands_preview = data.commands_preview
    row.status = MigrationStatus.ready
    await db.commit()
    await db.refresh(row)
    return MigrationRead.model_validate(row)


@router.post("/{migration_id}/regenerate", status_code=202)
async def regenerate_migration(
    migration_id: UUID,
    data: RegenerateRequest,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Re-render preview from stored IR (+ optional port_mapping override) respecting ai_level."""
    row = await db.get(ConfigMigration, migration_id)
    if not row or row.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Migração não encontrada")
    if row.status not in (MigrationStatus.ready, MigrationStatus.failed):
        raise HTTPException(400, "Regeneração disponível apenas em status 'ready' ou 'failed'")

    # Update port_mapping before dispatching if provided
    if data.port_mapping is not None:
        row.port_mapping = data.port_mapping

    row.status = MigrationStatus.analyzing
    row.error_message = None
    await db.commit()

    from app.workers.migration_worker import regenerate_config_migration
    regenerate_config_migration.delay(str(migration_id))

    return {"queued": True, "migration_id": str(migration_id)}


@router.post("/{migration_id}/add-interface", response_model=MigrationRead)
async def add_interface(
    migration_id: UUID,
    data: InterfaceAdd,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> MigrationRead:
    """Add a manual interface entry to migration_plan + port_mapping, then re-render."""
    from sqlalchemy.orm.attributes import flag_modified
    from app.services.config_renderer import render_config

    row = await db.get(ConfigMigration, migration_id)
    if not row or row.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Migração não encontrada")
    if row.status not in (MigrationStatus.ready, MigrationStatus.failed):
        raise HTTPException(400, "Interfaces só podem ser adicionadas quando status é 'ready' ou 'failed'")

    # Update migration_plan
    plan = dict(row.migration_plan or {})
    ifaces: list = list(plan.get("interfaces", []))

    # Replace existing entry with same name if present
    ifaces = [i for i in ifaces if i.get("name") != data.name]
    ifaces.append({
        "name": data.name,
        "mode": data.mode,
        "pvid": data.pvid,
        "tagged_vlans": data.tagged_vlans,
        "description": data.description,
        "port_type": data.port_type,
        "lag_member_of": None,
        "members": [],
    })
    plan["interfaces"] = ifaces
    row.migration_plan = plan
    flag_modified(row, "migration_plan")

    # Update port_mapping
    pm = dict(row.port_mapping or {})
    pm[data.name] = data.target_name
    row.port_mapping = pm
    flag_modified(row, "port_mapping")

    # Synchronous re-render (Level 1 only — no Claude for manual add)
    rendered = render_config(plan, row.target_vendor, pm)
    row.commands_preview = "\n".join(rendered["commands"])
    existing_warns = [w for w in (row.warnings or []) if "sem mapeamento" not in w]
    row.warnings = existing_warns + rendered["warnings"]
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


@router.post("/{migration_id}/retry", status_code=202)
async def retry_migration(
    migration_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_reviewer)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    row = await db.get(ConfigMigration, migration_id)
    if not row or row.tenant_id != ctx.tenant.id:
        raise HTTPException(404, "Migração não encontrada")
    if row.status != MigrationStatus.failed:
        raise HTTPException(400, "Retry só é possível quando status é 'failed'")

    from app.workers.migration_worker import apply_config_migration
    apply_config_migration.delay(str(migration_id))

    row.status = MigrationStatus.applying
    row.error_message = None
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
