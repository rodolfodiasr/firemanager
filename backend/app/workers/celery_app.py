from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "firemanager",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.health_check",
        "app.workers.execute_operation",
        "app.workers.generate_documents",
        "app.workers.bookstack_snapshot",
        "app.workers.bookstack_index",
        "app.workers.compliance_scan",
        "app.workers.glpi_sync",
        "app.workers.migration_worker",
        "app.workers.bundle_apply",
        "app.workers.firmware_tasks",
        "app.workers.identity_sync",
        "app.workers.expiry_reminders",
        "app.workers.playbook_evaluator",
        "app.workers.backup_worker",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "health-check-all-devices": {
            "task": "app.workers.health_check.run_health_checks",
            "schedule": crontab(minute="*/5"),
        },
        "bookstack-daily-snapshot": {
            "task": "app.workers.bookstack_snapshot.run_bookstack_snapshots",
            "schedule": crontab(minute=0),                # every hour — config per integration
        },
        "bookstack-reindex": {
            "task": "app.workers.bookstack_index.run_bookstack_indexing",
            "schedule": crontab(minute=0, hour="*/6"),     # every 6 hours
        },
        "compliance-daily-scan": {
            "task": "app.workers.compliance_scan.run_compliance_scan",
            "schedule": crontab(minute=0, hour=2),         # 02:00 UTC daily
        },
        "glpi-ticket-sync": {
            "task": "app.workers.glpi_sync.run_glpi_sync",
            "schedule": crontab(minute="*/5"),              # every 5 min
        },
        "glpi-cleanup-stale": {
            "task": "app.workers.glpi_sync.clean_stale_glpi_analyses",
            "schedule": crontab(minute=0),                  # every hour
        },
        "firmware-nvd-sync": {
            "task": "app.workers.firmware_tasks.sync_nvd_all_vendors",
            "schedule": crontab(minute=0, hour=3),          # 03:00 UTC daily
        },
        "firmware-correlate": {
            "task": "app.workers.firmware_tasks.correlate_all",
            "schedule": crontab(minute=0, hour=4),          # 04:00 UTC daily
        },
        "soar-scheduled-triggers": {
            "task": "soar.evaluate_scheduled_triggers",
            "schedule": crontab(minute="*"),                # every minute
        },
        "identity-expire-jit": {
            "task": "identity_sync.expire_jit",
            "schedule": crontab(minute="*"),                # every minute
        },
        "identity-sod-scan": {
            "task": "identity_sync.check_sod_all",
            "schedule": crontab(minute=0, hour=1),          # 01:00 UTC daily
        },
        "identity-password-expiry": {
            "task": "expiry_reminders.check_password_expiry",
            "schedule": crontab(minute=0, hour=8),          # 08:00 UTC daily
        },
        "backup-scheduled": {
            "task": "backup.run_scheduled_backups",
            "schedule": crontab(minute="*/5"),               # every 5 min — cron evaluation
        },
    },
)
