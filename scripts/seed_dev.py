"""Seed development database with admin user and fake devices."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from passlib.context import CryptContext
from sqlalchemy import text

from app.database import AsyncSessionLocal, engine, Base
from app.models.user import User, UserRole
from app.models.device import Device, VendorEnum
from app.utils.crypto import encrypt_credentials

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Admin user
        admin = User(
            email="admin@firemanager.local",
            name="Admin",
            hashed_password=pwd_context.hash("FireManager@dev1"),
            role=UserRole.admin,
        )
        db.add(admin)

        # Fake Fortinet device
        fortinet = Device(
            name="FW-Fortinet-Dev",
            vendor=VendorEnum.fortinet,
            firmware_version="7.4.3",
            host="192.168.1.1",
            port=443,
            encrypted_credentials=encrypt_credentials({"auth_type": "token", "token": "dev_token_123", "vdom": "root"}),
            use_ssl=True,
            verify_ssl=False,
            notes="Dispositivo de desenvolvimento (fake)",
        )
        db.add(fortinet)

        # Fake SonicWall device
        sonicwall = Device(
            name="FW-SonicWall-Dev",
            vendor=VendorEnum.sonicwall,
            firmware_version="7.1.1",
            host="192.168.1.2",
            port=443,
            encrypted_credentials=encrypt_credentials({"auth_type": "user_pass", "username": "admin", "password": "dev_pass", "os_version": 7}),
            use_ssl=True,
            verify_ssl=False,
            notes="Dispositivo de desenvolvimento (fake)",
        )
        db.add(sonicwall)

        await db.commit()
        print("Seed completed successfully!")
        print("Login: admin@firemanager.local / FireManager@dev1")


if __name__ == "__main__":
    asyncio.run(seed())
