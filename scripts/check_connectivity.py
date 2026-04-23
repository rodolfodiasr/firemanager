"""Test connectivity to all registered devices."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import select

from app.connectors.factory import get_connector
from app.database import AsyncSessionLocal
from app.models.device import Device


async def check_all() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Device))
        devices = list(result.scalars().all())

    if not devices:
        print("No devices registered.")
        return

    for device in devices:
        try:
            connector = get_connector(device)
            result = await connector.test_connection()
            status = "OK" if result.success else "FAIL"
            latency = f"{result.latency_ms:.1f}ms" if result.latency_ms else "N/A"
            version = result.firmware_version or "unknown"
            print(f"[{status}] {device.name} ({device.vendor}) — {latency} — {version}")
            if result.error:
                print(f"       Error: {result.error}")
        except Exception as exc:
            print(f"[ERROR] {device.name}: {exc}")


if __name__ == "__main__":
    asyncio.run(check_all())
