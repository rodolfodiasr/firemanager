"""Celery tasks for backup and restore operations."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(name="backup.run_backup_job", bind=True, max_retries=0)
def run_backup_job(self, job_id: str) -> None:
    asyncio.run(_run_backup(job_id))


@celery_app.task(name="backup.run_restore_job", bind=True, max_retries=0)
def run_restore_job(self, job_id: str) -> None:
    asyncio.run(_run_restore(job_id))


@celery_app.task(name="backup.run_scheduled_backups")
def run_scheduled_backups() -> None:
    asyncio.run(_run_scheduled())


async def _run_backup(job_id: str) -> None:
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.backup import BackupConfig, BackupJob
    from app.services import backup_service

    async with AsyncSessionLocal() as db:
        r = await db.execute(select(BackupJob).where(BackupJob.id == uuid.UUID(job_id)))
        job = r.scalar_one_or_none()
        if not job:
            log.error("backup.run: job not found", job_id=job_id)
            return

        r2 = await db.execute(select(BackupConfig).where(BackupConfig.id == job.config_id))
        config = r2.scalar_one_or_none()
        if not config:
            job.status = "failed"
            job.error_message = "Config not found"
            await db.commit()
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        await db.commit()

        try:
            if job.backup_type == "platform":
                data, filename = await backup_service.produce_platform_backup(db)
            else:
                data, filename = await backup_service.produce_tenant_backup(db, job.tenant_id)

            file_path = backup_service.upload(data, config, filename)

            job.status = "success"
            job.file_path = file_path
            job.file_size_bytes = len(data)
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Enforce retention policy
            await backup_service.apply_retention(db, config)

            log.info("backup.run: success", job_id=job_id, path=file_path, size=len(data))

        except Exception as exc:
            log.error("backup.run: failed", job_id=job_id, error=str(exc))
            await db.rollback()
            # Re-fetch to update status after rollback
            async with AsyncSessionLocal() as db2:
                r3 = await db2.execute(select(BackupJob).where(BackupJob.id == uuid.UUID(job_id)))
                j2 = r3.scalar_one_or_none()
                if j2:
                    j2.status = "failed"
                    j2.error_message = str(exc)[:490]
                    j2.completed_at = datetime.now(timezone.utc)
                    await db2.commit()


async def _run_restore(job_id: str) -> None:
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.backup import BackupConfig, BackupJob
    from app.services import backup_service

    async with AsyncSessionLocal() as db:
        r = await db.execute(select(BackupJob).where(BackupJob.id == uuid.UUID(job_id)))
        job = r.scalar_one_or_none()
        if not job or not job.file_path:
            log.error("backup.restore: job not found or no file_path", job_id=job_id)
            return

        r2 = await db.execute(select(BackupConfig).where(BackupConfig.id == job.config_id))
        config = r2.scalar_one_or_none()
        if not config:
            log.error("backup.restore: config not found", job_id=job_id)
            return

        try:
            blob = backup_service.fetch_backup(config, job.file_path)
            if job.backup_type == "platform":
                await backup_service.restore_platform(blob)
            else:
                result = await backup_service.restore_tenant(blob, db)
                log.info("backup.restore: tenant restore done", **result)

            log.info("backup.restore: success", job_id=job_id)

        except Exception as exc:
            log.error("backup.restore: failed", job_id=job_id, error=str(exc))


async def _run_scheduled() -> None:
    """Evaluate cron schedules and fire backup jobs for due configs."""
    from sqlalchemy import select
    from croniter import croniter  # type: ignore
    from app.database import AsyncSessionLocal
    from app.models.backup import BackupConfig, BackupJob

    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(BackupConfig).where(
                BackupConfig.is_active.is_(True),
                BackupConfig.schedule_cron.isnot(None),
            )
        )
        configs = r.scalars().all()

        for config in configs:
            try:
                cron = croniter(config.schedule_cron, now)
                prev = cron.get_prev(datetime)

                # Check if any successful job already ran in this cron window
                r2 = await db.execute(
                    select(BackupJob)
                    .where(
                        BackupJob.config_id == config.id,
                        BackupJob.status == "success",
                        BackupJob.created_at >= prev,
                    )
                    .limit(1)
                )
                if r2.scalar_one_or_none():
                    continue  # Already ran this window

                job = BackupJob(
                    config_id=config.id,
                    tenant_id=config.tenant_id,
                    status="pending",
                    backup_type=config.backup_type,
                    destination=config.destination,
                )
                db.add(job)
                await db.flush()
                job_id = str(job.id)
                await db.commit()

                run_backup_job.delay(job_id)
                log.info("backup.scheduled: triggered", config_id=str(config.id), job_id=job_id)

            except Exception as exc:
                log.error("backup.scheduled: error", config_id=str(config.id), error=str(exc))
