from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.factory import get_connector
from app.models.device import Device, DeviceStatus
from app.schemas.device import DeviceCreate, DeviceUpdate
from app.utils.crypto import encrypt_credentials


class DeviceNotFoundError(Exception):
    status_code = 404
    default_message = "Device não encontrado"


async def create_device(db: AsyncSession, data: DeviceCreate) -> Device:
    encrypted = encrypt_credentials(data.credentials.model_dump())
    device = Device(
        name=data.name,
        vendor=data.vendor,
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


async def get_device(db: AsyncSession, device_id: UUID) -> Device:
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise DeviceNotFoundError()
    return device


async def list_devices(db: AsyncSession, skip: int = 0, limit: int = 100) -> tuple[list[Device], int]:
    count_result = await db.execute(select(Device))
    all_devices = list(count_result.scalars().all())
    total = len(all_devices)
    return all_devices[skip : skip + limit], total


async def update_device(db: AsyncSession, device_id: UUID, data: DeviceUpdate) -> Device:
    device = await get_device(db, device_id)
    if data.name is not None:
        device.name = data.name
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


async def delete_device(db: AsyncSession, device_id: UUID) -> None:
    device = await get_device(db, device_id)
    await db.delete(device)


async def health_check_device(db: AsyncSession, device_id: UUID) -> Device:
    device = await get_device(db, device_id)
    try:
        connector = get_connector(device)
        result = await connector.test_connection()
        if result.success:
            device.status = DeviceStatus.online
            if result.firmware_version:
                device.firmware_version = result.firmware_version
        else:
            device.status = DeviceStatus.offline
        from datetime import datetime, timezone
        device.last_seen = datetime.now(timezone.utc)
    except Exception:
        device.status = DeviceStatus.error
    await db.flush()
    await db.refresh(device)
    return device
