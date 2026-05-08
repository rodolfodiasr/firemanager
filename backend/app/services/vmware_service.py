"""Fase 27 — VMware vCenter REST API service (read-only)."""
from __future__ import annotations

from typing import Optional

import httpx


class VMwareService:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        verify_ssl: bool = False,
    ) -> None:
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self._session_id: Optional[str] = None

    async def _auth(self) -> str:
        """POST /api/session with Basic auth → returns session_id string."""
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            r = await client.post(
                f"{self.host}/api/session",
                auth=(self.username, self.password),
            )
            r.raise_for_status()
            return r.json()  # session ID string

    async def test_connection(self) -> dict:
        """Test connectivity by authenticating and listing datacenters."""
        try:
            session_id = await self._auth()
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                r = await client.get(
                    f"{self.host}/api/vcenter/datacenter",
                    headers={"vmware-api-session-id": session_id},
                )
            if r.status_code == 200:
                return {"ok": True, "datacenters": r.json()}
            return {"ok": False, "error": r.text}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def list_vms(self) -> list[dict]:
        """GET /api/vcenter/vm → list of VMs with detailed info (up to 100)."""
        session_id = await self._auth()
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            r = await client.get(
                f"{self.host}/api/vcenter/vm",
                headers={"vmware-api-session-id": session_id},
            )
            r.raise_for_status()
            vms = r.json()  # list of {vm, name, power_state}

            detailed = []
            for vm_summary in vms[:100]:
                try:
                    detail_r = await client.get(
                        f"{self.host}/api/vcenter/vm/{vm_summary['vm']}",
                        headers={"vmware-api-session-id": session_id},
                    )
                    if detail_r.status_code == 200:
                        detail = detail_r.json()

                        # Guest IP requires VMware tools API — best effort only
                        ips: list[str] = []
                        for _nic_key, _nic_val in (detail.get("nics") or {}).items():
                            pass

                        cpu = detail.get("cpu") or {}
                        mem = detail.get("memory") or {}
                        disks = detail.get("disks") or {}
                        total_disk_gb = sum(
                            d.get("capacity", 0) / (1024 ** 3)
                            for d in disks.values()
                        )

                        detailed.append({
                            "vm_id": vm_summary["vm"],
                            "vm_name": vm_summary.get("name", ""),
                            "power_state": (
                                vm_summary.get("power_state", "UNKNOWN")
                                .lower()
                                .replace("powered_", "powered")
                            ),
                            "os_type": detail.get("guest_OS"),
                            "cpu_count": cpu.get("count"),
                            "ram_mb": mem.get("size_MiB"),
                            "disk_gb": round(total_disk_gb, 2) if total_disk_gb else None,
                            "ip_addresses": ips,
                            "extra": {"vcenter_vm_id": vm_summary["vm"]},
                        })
                    else:
                        detailed.append({
                            "vm_id": vm_summary["vm"],
                            "vm_name": vm_summary.get("name", ""),
                            "power_state": vm_summary.get("power_state", "").lower(),
                        })
                except Exception:
                    detailed.append({
                        "vm_id": vm_summary["vm"],
                        "vm_name": vm_summary.get("name", ""),
                        "power_state": vm_summary.get("power_state", "").lower(),
                    })

            return detailed
