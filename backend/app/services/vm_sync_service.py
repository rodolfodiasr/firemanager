"""Fase 27 — VM inventory sync service."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vm_migration import VmHypervisor, VmInventory
from app.utils.crypto import decrypt_credentials


async def sync_hypervisor(db: AsyncSession, hypervisor: VmHypervisor) -> int:
    """Sync VM inventory from hypervisor. Returns count of VMs synced."""
    creds = decrypt_credentials(hypervisor.encrypted_credentials)

    if hypervisor.hypervisor_type == "vmware_vcenter":
        from app.services.vmware_service import VMwareService
        svc = VMwareService(
            host=hypervisor.host,
            username=creds.get("username", ""),
            password=creds.get("password", ""),
            verify_ssl=hypervisor.verify_ssl,
        )
        vms = await svc.list_vms()
    elif hypervisor.hypervisor_type == "proxmox":
        from app.services.proxmox_service import ProxmoxService
        svc = ProxmoxService(
            host=hypervisor.host,
            username=creds.get("username", ""),
            password=creds.get("password", ""),
            verify_ssl=hypervisor.verify_ssl,
        )
        vms = await svc.list_vms()
    else:
        return 0

    # Delete old inventory for this hypervisor
    await db.execute(
        delete(VmInventory).where(VmInventory.hypervisor_id == hypervisor.id)
    )

    # Insert new inventory
    for vm_data in vms:
        inv = VmInventory(
            hypervisor_id=hypervisor.id,
            tenant_id=hypervisor.tenant_id,
            vm_id=vm_data.get("vm_id", ""),
            vm_name=vm_data.get("vm_name", ""),
            power_state=vm_data.get("power_state"),
            os_type=vm_data.get("os_type"),
            cpu_count=vm_data.get("cpu_count"),
            ram_mb=vm_data.get("ram_mb"),
            disk_gb=vm_data.get("disk_gb"),
            ip_addresses=vm_data.get("ip_addresses", []),
            extra=vm_data.get("extra"),
        )
        db.add(inv)

    hypervisor.last_sync_at = datetime.now(timezone.utc)
    hypervisor.last_vm_count = len(vms)
    await db.commit()
    return len(vms)
