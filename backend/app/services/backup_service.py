"""Backup & Restore service — platform (pg_dump) and tenant (JSON export)."""
from __future__ import annotations

import gzip
import io
import json
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Tuple

import paramiko
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.backup import BackupConfig


def _fernet() -> Fernet:
    return Fernet(settings.fernet_key.encode())


def _pg_dsn() -> str:
    """Convert asyncpg URL to standard postgresql:// for pg_dump/psql."""
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


def _pack(raw: bytes) -> bytes:
    return _fernet().encrypt(gzip.compress(raw))


def _unpack(blob: bytes) -> bytes:
    return gzip.decompress(_fernet().decrypt(blob))


# ── Tenant JSON export ────────────────────────────────────────────────────────

async def _export_tenant_json(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    from app.models.device import Device
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.user_tenant_role import UserTenantRole

    r = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = r.scalar_one_or_none()
    if not tenant:
        raise ValueError(f"Tenant {tenant_id} not found")

    dev_r = await db.execute(select(Device).where(Device.tenant_id == tenant_id))
    devices = dev_r.scalars().all()

    utr_r = await db.execute(select(UserTenantRole).where(UserTenantRole.tenant_id == tenant_id))
    roles = utr_r.scalars().all()

    user_ids = {r.user_id for r in roles}
    users = []
    for uid in user_ids:
        u_r = await db.execute(select(User).where(User.id == uid))
        u = u_r.scalar_one_or_none()
        if u:
            users.append({
                "id": str(u.id), "email": u.email, "name": u.name,
                "role": str(u.role.value if hasattr(u.role, "value") else u.role),
                "is_active": u.is_active, "is_super_admin": u.is_super_admin,
            })

    return {
        "export_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "tenant": {
            "id": str(tenant.id), "name": tenant.name,
            "slug": tenant.slug, "is_active": tenant.is_active,
        },
        "devices": [
            {
                "id": str(d.id), "name": d.name,
                "vendor": str(d.vendor.value if hasattr(d.vendor, "value") else d.vendor),
                "category": str(d.category.value if hasattr(d.category, "value") else d.category),
                "host": d.host, "port": d.port,
                "use_ssl": d.use_ssl, "verify_ssl": d.verify_ssl,
                "read_only_agent": d.read_only_agent, "notes": d.notes,
                "encrypted_credentials": d.encrypted_credentials,
            }
            for d in devices
        ],
        "user_roles": [
            {
                "user_id": str(r.user_id),
                "role": str(r.role.value if hasattr(r.role, "value") else r.role),
            }
            for r in roles
        ],
        "users": users,
    }


# ── Produce backups ───────────────────────────────────────────────────────────

async def produce_platform_backup(db: AsyncSession) -> Tuple[bytes, str]:
    """pg_dump → gzip → Fernet encrypt. Returns (blob, filename)."""
    dsn = _pg_dsn()
    with tempfile.TemporaryDirectory() as tmp:
        dump_file = os.path.join(tmp, "dump.sql")
        res = subprocess.run(
            ["pg_dump", "--format=plain", dsn, "-f", dump_file],
            capture_output=True, text=True, timeout=600,
        )
        if res.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {res.stderr[:500]}")
        with open(dump_file, "rb") as f:
            raw = f.read()

    filename = f"platform_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.sql.gz.enc"
    return _pack(raw), filename


async def produce_tenant_backup(db: AsyncSession, tenant_id: uuid.UUID) -> Tuple[bytes, str]:
    """JSON export → gzip → Fernet encrypt. Returns (blob, filename)."""
    data = await _export_tenant_json(db, tenant_id)
    raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    filename = f"tenant_{tenant_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json.gz.enc"
    return _pack(raw), filename


# ── Storage drivers ───────────────────────────────────────────────────────────

def store_local(data: bytes, config: BackupConfig, filename: str) -> str:
    path = config.local_path or "/tmp/firemanager_backups"
    os.makedirs(path, exist_ok=True)
    dest = os.path.join(path, filename)
    with open(dest, "wb") as f:
        f.write(data)
    return dest


def store_s3(data: bytes, config: BackupConfig, filename: str) -> str:
    import boto3  # type: ignore
    creds = json.loads(_fernet().decrypt(config.s3_credentials_encrypted.encode()).decode())
    s3 = boto3.client(
        "s3",
        aws_access_key_id=creds["access_key"],
        aws_secret_access_key=creds["secret_key"],
        region_name=config.s3_region or "us-east-1",
    )
    prefix = (config.s3_prefix or "").strip("/")
    key = f"{prefix}/{filename}" if prefix else filename
    s3.put_object(Bucket=config.s3_bucket, Key=key, Body=data)
    return f"s3://{config.s3_bucket}/{key}"


def store_sftp(data: bytes, config: BackupConfig, filename: str) -> str:
    creds = json.loads(_fernet().decrypt(config.sftp_credentials_encrypted.encode()).decode())
    transport = paramiko.Transport((config.sftp_host, config.sftp_port or 22))
    if "private_key" in creds:
        pkey = paramiko.RSAKey.from_private_key(io.StringIO(creds["private_key"]))
        transport.connect(username=config.sftp_user, pkey=pkey)
    else:
        transport.connect(username=config.sftp_user, password=creds.get("password", ""))
    sftp = paramiko.SFTPClient.from_transport(transport)
    remote_dir = (config.sftp_path or "/backups").rstrip("/")
    try:
        sftp.mkdir(remote_dir)
    except OSError:
        pass
    remote_path = f"{remote_dir}/{filename}"
    sftp.putfo(io.BytesIO(data), remote_path)
    sftp.close()
    transport.close()
    return remote_path


def upload(data: bytes, config: BackupConfig, filename: str) -> str:
    if config.destination == "local":
        return store_local(data, config, filename)
    if config.destination == "s3":
        return store_s3(data, config, filename)
    if config.destination == "sftp":
        return store_sftp(data, config, filename)
    raise ValueError(f"Unknown destination: {config.destination}")


# ── Fetch for restore ─────────────────────────────────────────────────────────

def fetch_backup(config: BackupConfig, file_path: str) -> bytes:
    if config.destination == "local":
        with open(file_path, "rb") as f:
            return f.read()
    if config.destination == "s3":
        import boto3  # type: ignore
        creds = json.loads(_fernet().decrypt(config.s3_credentials_encrypted.encode()).decode())
        s3 = boto3.client(
            "s3",
            aws_access_key_id=creds["access_key"],
            aws_secret_access_key=creds["secret_key"],
            region_name=config.s3_region or "us-east-1",
        )
        # file_path is s3://bucket/key — extract key
        key = "/".join(file_path.split("/")[3:])
        resp = s3.get_object(Bucket=config.s3_bucket, Key=key)
        return resp["Body"].read()
    if config.destination == "sftp":
        creds = json.loads(_fernet().decrypt(config.sftp_credentials_encrypted.encode()).decode())
        transport = paramiko.Transport((config.sftp_host, config.sftp_port or 22))
        if "private_key" in creds:
            pkey = paramiko.RSAKey.from_private_key(io.StringIO(creds["private_key"]))
            transport.connect(username=config.sftp_user, pkey=pkey)
        else:
            transport.connect(username=config.sftp_user, password=creds.get("password", ""))
        sftp = paramiko.SFTPClient.from_transport(transport)
        buf = io.BytesIO()
        sftp.getfo(file_path, buf)
        sftp.close()
        transport.close()
        return buf.getvalue()
    raise ValueError(f"Unknown destination: {config.destination}")


# ── Restore ───────────────────────────────────────────────────────────────────

async def restore_platform(blob: bytes) -> None:
    """Decrypt → gunzip → psql to replay SQL dump."""
    raw_sql = _unpack(blob)
    with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as f:
        f.write(raw_sql)
        sql_path = f.name
    try:
        dsn = _pg_dsn()
        res = subprocess.run(
            ["psql", dsn, "-f", sql_path],
            capture_output=True, text=True, timeout=600,
        )
        if res.returncode != 0:
            raise RuntimeError(f"psql restore failed: {res.stderr[:500]}")
    finally:
        os.unlink(sql_path)


async def restore_tenant(blob: bytes, db: AsyncSession) -> dict:
    """Decrypt → gunzip → JSON upsert (idempotent)."""
    from app.models.device import Device
    from app.models.tenant import Tenant

    raw = _unpack(blob)
    export = json.loads(raw.decode("utf-8"))
    t_data = export["tenant"]

    r = await db.execute(select(Tenant).where(Tenant.slug == t_data["slug"]))
    tenant = r.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(
            name=t_data["name"], slug=t_data["slug"],
            is_active=t_data.get("is_active", True),
        )
        db.add(tenant)
        await db.flush()
        await db.refresh(tenant)

    restored_devices = 0
    for d in export.get("devices", []):
        r2 = await db.execute(
            select(Device).where(Device.tenant_id == tenant.id, Device.name == d["name"])
        )
        if not r2.scalar_one_or_none():
            device = Device(
                tenant_id=tenant.id, name=d["name"],
                vendor=d["vendor"], category=d["category"],
                host=d["host"], port=d.get("port", 443),
                use_ssl=d.get("use_ssl", True), verify_ssl=d.get("verify_ssl", False),
                read_only_agent=d.get("read_only_agent", True),
                encrypted_credentials=d.get("encrypted_credentials") or "{}",
                notes=d.get("notes"),
            )
            db.add(device)
            restored_devices += 1

    await db.commit()
    return {"tenant_slug": tenant.slug, "devices_restored": restored_devices}


# ── Retention cleanup ─────────────────────────────────────────────────────────

async def apply_retention(db: AsyncSession, config: BackupConfig) -> None:
    """Delete oldest jobs beyond retention_count (local files are also removed)."""
    from sqlalchemy import delete
    from app.models.backup import BackupJob

    r = await db.execute(
        select(BackupJob)
        .where(BackupJob.config_id == config.id, BackupJob.status == "success")
        .order_by(BackupJob.created_at.desc())
    )
    jobs = r.scalars().all()
    to_delete = jobs[config.retention_count:]
    for job in to_delete:
        if job.file_path and config.destination == "local":
            try:
                os.unlink(job.file_path)
            except OSError:
                pass
        await db.delete(job)
    if to_delete:
        await db.commit()
