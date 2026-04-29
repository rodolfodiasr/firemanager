import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.factory import CLI_VENDORS, get_connector, get_ssh_connector
from app.models.device import Device, DeviceStatus
from app.schemas.device import DeviceCreate, DeviceUpdate
from app.utils.crypto import encrypt_credentials

logger = logging.getLogger(__name__)


class DeviceNotFoundError(Exception):
    status_code = 404
    default_message = "Device não encontrado"


async def create_device(db: AsyncSession, data: DeviceCreate, tenant_id: UUID) -> Device:
    encrypted = encrypt_credentials(data.credentials.model_dump())
    device = Device(
        tenant_id=tenant_id,
        name=data.name,
        vendor=data.vendor,
        category=data.category,
        firmware_version=data.firmware_version,
        host=data.host,
        port=data.port,
        encrypted_credentials=encrypted,
        use_ssl=data.use_ssl,
        verify_ssl=data.verify_ssl,
        notes=data.notes,
    )
    db.add(device)
    await db.flush()
    await db.refresh(device)
    return device


async def get_device(db: AsyncSession, device_id: UUID, tenant_id: UUID | None = None) -> Device:
    query = select(Device).where(Device.id == device_id)
    if tenant_id is not None:
        query = query.where(Device.tenant_id == tenant_id)
    result = await db.execute(query)
    device = result.scalar_one_or_none()
    if not device:
        raise DeviceNotFoundError()
    return device


async def list_devices(
    db: AsyncSession, tenant_id: UUID, skip: int = 0, limit: int = 100
) -> tuple[list[Device], int]:
    result = await db.execute(select(Device).where(Device.tenant_id == tenant_id))
    all_devices = list(result.scalars().all())
    total = len(all_devices)
    return all_devices[skip : skip + limit], total


async def update_device(
    db: AsyncSession, device_id: UUID, data: DeviceUpdate, tenant_id: UUID | None = None
) -> Device:
    device = await get_device(db, device_id, tenant_id)
    if data.name is not None:
        device.name = data.name
    if data.category is not None:
        device.category = data.category
    if data.firmware_version is not None:
        device.firmware_version = data.firmware_version
    if data.host is not None:
        device.host = data.host
    if data.port is not None:
        device.port = data.port
    if data.credentials is not None:
        device.encrypted_credentials = encrypt_credentials(data.credentials.model_dump())
    if data.use_ssl is not None:
        device.use_ssl = data.use_ssl
    if data.verify_ssl is not None:
        device.verify_ssl = data.verify_ssl
    if data.notes is not None:
        device.notes = data.notes
    await db.flush()
    await db.refresh(device)
    return device


async def delete_device(db: AsyncSession, device_id: UUID, tenant_id: UUID | None = None) -> None:
    device = await get_device(db, device_id, tenant_id)
    await db.delete(device)


async def health_check_device(
    db: AsyncSession, device_id: UUID, tenant_id: UUID | None = None
) -> Device:
    device = await get_device(db, device_id, tenant_id)
    try:
        if device.vendor in CLI_VENDORS:
            connector = get_ssh_connector(device)
        else:
            connector = get_connector(device)
        result = await connector.test_connection()
        if result.success:
            device.status = DeviceStatus.online
            device.last_error = None
            fw = getattr(result, "firmware_version", None)
            if fw:
                device.firmware_version = fw
        else:
            logger.warning("Health check failed for device %s: %s", device_id, result.error)
            device.status = DeviceStatus.offline
            device.last_error = result.error
        from datetime import datetime, timezone
        device.last_seen = datetime.now(timezone.utc)
    except Exception as exc:
        logger.exception("Health check exception for device %s: %s", device_id, exc)
        device.status = DeviceStatus.error
        device.last_error = str(exc)
    await db.flush()
    await db.refresh(device)
    return device
