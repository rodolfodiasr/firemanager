"""Backup & Restore API — platform (super admin) and tenant (admin)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_current_user, get_tenant_context
from app.database import get_db
from app.models.backup import BackupConfig, BackupJob
from app.models.user import User
from app.models.user_tenant_role import TenantRole

router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class BackupConfigCreate(BaseModel):
    name: str
    destination: str = "local"
    schedule_cron: str | None = None
    retention_count: int = 7
    local_path: str | None = None
    s3_bucket: str | None = None
    s3_prefix: str | None = None
    s3_region: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    sftp_host: str | None = None
    sftp_port: int | None = 22
    sftp_user: str | None = None
    sftp_password: str | None = None
    sftp_private_key: str | None = None
    sftp_path: str | None = None


class BackupConfigRead(BaseModel):
    id: uuid.UUID
    name: str
    backup_type: str
    destination: str
    schedule_cron: str | None
    retention_count: int
    local_path: str | None
    s3_bucket: str | None
    s3_prefix: str | None
    sftp_host: str | None
    sftp_path: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BackupJobRead(BaseModel):
    id: uuid.UUID
    config_id: uuid.UUID
    tenant_id: uuid.UUID | None
    status: str
    backup_type: str
    destination: str
    file_path: str | None
    file_size_bytes: int | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_super_admin(user: User) -> None:
    if not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin only")


def _require_admin(ctx: TenantContext) -> None:
    if not ctx.user.is_super_admin and ctx.role not in (TenantRole.admin,):
        raise HTTPException(status_code=403, detail="Admin only")


def _encrypt_s3_creds(body: BackupConfigCreate) -> str | None:
    if not body.s3_access_key:
        return None
    import json
    from cryptography.fernet import Fernet
    from app.config import settings
    f = Fernet(settings.fernet_key.encode())
    return f.encrypt(json.dumps({
        "access_key": body.s3_access_key,
        "secret_key": body.s3_secret_key or "",
    }).encode()).decode()


def _encrypt_sftp_creds(body: BackupConfigCreate) -> str | None:
    if not body.sftp_host:
        return None
    import json
    from cryptography.fernet import Fernet
    from app.config import settings
    f = Fernet(settings.fernet_key.encode())
    creds: dict = {}
    if body.sftp_private_key:
        creds["private_key"] = body.sftp_private_key
    elif body.sftp_password:
        creds["password"] = body.sftp_password
    return f.encrypt(json.dumps(creds).encode()).decode()


def _validate_cron(cron: str | None) -> None:
    if cron:
        from croniter import croniter  # type: ignore
        if not croniter.is_valid(cron):
            raise HTTPException(status_code=422, detail="Invalid cron expression")


# ── Platform backup (super admin only) ───────────────────────────────────────

@router.get("/admin/backup/configs", response_model=list[BackupConfigRead])
async def list_platform_configs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[BackupConfig]:
    _require_super_admin(user)
    r = await db.execute(
        select(BackupConfig)
        .where(BackupConfig.backup_type == "platform")
        .order_by(BackupConfig.created_at.desc())
    )
    return list(r.scalars().all())


@router.post("/admin/backup/configs", response_model=BackupConfigRead)
async def create_platform_config(
    body: BackupConfigCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> BackupConfig:
    _require_super_admin(user)
    _validate_cron(body.schedule_cron)

    cfg = BackupConfig(
        name=body.name, backup_type="platform", destination=body.destination,
        schedule_cron=body.schedule_cron, retention_count=body.retention_count,
        local_path=body.local_path,
        s3_bucket=body.s3_bucket, s3_prefix=body.s3_prefix, s3_region=body.s3_region,
        s3_credentials_encrypted=_encrypt_s3_creds(body),
        sftp_host=body.sftp_host, sftp_port=body.sftp_port, sftp_user=body.sftp_user,
        sftp_credentials_encrypted=_encrypt_sftp_creds(body),
        sftp_path=body.sftp_path,
    )
    db.add(cfg)
    await db.flush()
    await db.refresh(cfg)
    await db.commit()
    return cfg


@router.delete("/admin/backup/configs/{config_id}")
async def delete_platform_config(
    config_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    _require_super_admin(user)
    r = await db.execute(select(BackupConfig).where(BackupConfig.id == config_id, BackupConfig.backup_type == "platform"))
    cfg = r.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    await db.delete(cfg)
    await db.commit()
    return {"ok": True}


@router.post("/admin/backup/configs/{config_id}/run")
async def trigger_platform_backup(
    config_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    _require_super_admin(user)
    r = await db.execute(select(BackupConfig).where(BackupConfig.id == config_id, BackupConfig.backup_type == "platform"))
    cfg = r.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")

    job = BackupJob(
        config_id=cfg.id, triggered_by=user.id,
        status="pending", backup_type="platform", destination=cfg.destination,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    await db.commit()

    from app.workers.backup_worker import run_backup_job
    run_backup_job.delay(str(job.id))
    return {"job_id": str(job.id), "status": "pending"}


@router.get("/admin/backup/jobs", response_model=list[BackupJobRead])
async def list_platform_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[BackupJob]:
    _require_super_admin(user)
    r = await db.execute(
        select(BackupJob)
        .where(BackupJob.backup_type == "platform")
        .order_by(BackupJob.created_at.desc())
        .limit(50)
    )
    return list(r.scalars().all())


@router.post("/admin/backup/jobs/{job_id}/restore")
async def trigger_platform_restore(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    _require_super_admin(user)
    r = await db.execute(
        select(BackupJob).where(BackupJob.id == job_id, BackupJob.status == "success", BackupJob.backup_type == "platform")
    )
    job = r.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Successful platform backup job not found")

    from app.workers.backup_worker import run_restore_job
    run_restore_job.delay(str(job.id))
    return {"status": "restore_triggered", "job_id": str(job.id)}


# ── Tenant backup (tenant admin) ──────────────────────────────────────────────

@router.get("/backup/configs", response_model=list[BackupConfigRead])
async def list_tenant_configs(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[BackupConfig]:
    _require_admin(ctx)
    r = await db.execute(
        select(BackupConfig)
        .where(BackupConfig.backup_type == "tenant", BackupConfig.tenant_id == ctx.tenant.id)
        .order_by(BackupConfig.created_at.desc())
    )
    return list(r.scalars().all())


@router.post("/backup/configs", response_model=BackupConfigRead)
async def create_tenant_config(
    body: BackupConfigCreate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BackupConfig:
    _require_admin(ctx)
    _validate_cron(body.schedule_cron)

    cfg = BackupConfig(
        tenant_id=ctx.tenant.id, name=body.name, backup_type="tenant",
        destination=body.destination, schedule_cron=body.schedule_cron,
        retention_count=body.retention_count,
        local_path=body.local_path,
        s3_bucket=body.s3_bucket, s3_prefix=body.s3_prefix, s3_region=body.s3_region,
        s3_credentials_encrypted=_encrypt_s3_creds(body),
        sftp_host=body.sftp_host, sftp_port=body.sftp_port, sftp_user=body.sftp_user,
        sftp_credentials_encrypted=_encrypt_sftp_creds(body),
        sftp_path=body.sftp_path,
    )
    db.add(cfg)
    await db.flush()
    await db.refresh(cfg)
    await db.commit()
    return cfg


@router.delete("/backup/configs/{config_id}")
async def delete_tenant_config(
    config_id: uuid.UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    _require_admin(ctx)
    r = await db.execute(
        select(BackupConfig).where(
            BackupConfig.id == config_id,
            BackupConfig.tenant_id == ctx.tenant.id,
            BackupConfig.backup_type == "tenant",
        )
    )
    cfg = r.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    await db.delete(cfg)
    await db.commit()
    return {"ok": True}


@router.post("/backup/configs/{config_id}/run")
async def trigger_tenant_backup(
    config_id: uuid.UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    _require_admin(ctx)
    r = await db.execute(
        select(BackupConfig).where(
            BackupConfig.id == config_id,
            BackupConfig.tenant_id == ctx.tenant.id,
            BackupConfig.backup_type == "tenant",
        )
    )
    cfg = r.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")

    job = BackupJob(
        config_id=cfg.id, tenant_id=ctx.tenant.id, triggered_by=ctx.user.id,
        status="pending", backup_type="tenant", destination=cfg.destination,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    await db.commit()

    from app.workers.backup_worker import run_backup_job
    run_backup_job.delay(str(job.id))
    return {"job_id": str(job.id), "status": "pending"}


@router.get("/backup/jobs", response_model=list[BackupJobRead])
async def list_tenant_jobs(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[BackupJob]:
    _require_admin(ctx)
    r = await db.execute(
        select(BackupJob)
        .where(BackupJob.backup_type == "tenant", BackupJob.tenant_id == ctx.tenant.id)
        .order_by(BackupJob.created_at.desc())
        .limit(50)
    )
    return list(r.scalars().all())


@router.post("/backup/jobs/{job_id}/restore")
async def trigger_tenant_restore(
    job_id: uuid.UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    _require_admin(ctx)
    r = await db.execute(
        select(BackupJob).where(
            BackupJob.id == job_id,
            BackupJob.tenant_id == ctx.tenant.id,
            BackupJob.status == "success",
            BackupJob.backup_type == "tenant",
        )
    )
    job = r.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Successful tenant backup job not found")

    from app.workers.backup_worker import run_restore_job
    run_restore_job.delay(str(job.id))
    return {"status": "restore_triggered", "job_id": str(job.id)}
