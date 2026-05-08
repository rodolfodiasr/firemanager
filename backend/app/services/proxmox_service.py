"""Fase 27 — Proxmox VE API service (read-only)."""
from __future__ import annotations

import httpx


class ProxmoxService:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        verify_ssl: bool = False,
    ) -> None:
        self.host = host.rstrip("/")
        self.username = username  # e.g., root@pam
        self.password = password
        self.verify_ssl = verify_ssl

    async def _auth(self) -> tuple[str, str]:
        """POST /api2/json/access/ticket → (ticket, CSRFPreventionToken)."""
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            r = await client.post(
                f"{self.host}/api2/json/access/ticket",
                data={"username": self.username, "password": self.password},
            )
            r.raise_for_status()
            data = r.json()["data"]
            return data["ticket"], data["CSRFPreventionToken"]

    async def test_connection(self) -> dict:
        """Test connectivity by authenticating and listing nodes."""
        try:
            ticket, _ = await self._auth()
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                r = await client.get(
                    f"{self.host}/api2/json/nodes",
                    cookies={"PVEAuthCookie": ticket},
                )
            if r.status_code == 200:
                return {"ok": True, "nodes": [n["node"] for n in r.json()["data"]]}
            return {"ok": False, "error": r.text}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def list_vms(self) -> list[dict]:
        """GET /api2/json/nodes/{node}/qemu + lxc for all nodes."""
        ticket, _ = await self._auth()
        vms: list[dict] = []

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            nodes_r = await client.get(
                f"{self.host}/api2/json/nodes",
                cookies={"PVEAuthCookie": ticket},
            )
            nodes_r.raise_for_status()

            for node_info in nodes_r.json()["data"]:
                node = node_info["node"]
                for endpoint in ["qemu", "lxc"]:
                    vm_r = await client.get(
                        f"{self.host}/api2/json/nodes/{node}/{endpoint}",
                        cookies={"PVEAuthCookie": ticket},
                    )
                    if vm_r.status_code != 200:
                        continue
                    for vm in vm_r.json()["data"]:
                        vms.append({
                            "vm_id": f"{node}/{endpoint}/{vm['vmid']}",
                            "vm_name": vm.get("name", f"vm{vm['vmid']}"),
                            "power_state": (
                                "running" if vm.get("status") == "running" else "stopped"
                            ),
                            "os_type": None,
                            "cpu_count": vm.get("cpus"),
                            "ram_mb": (
                                int(vm["maxmem"] / (1024 ** 2))
                                if vm.get("maxmem")
                                else None
                            ),
                            "disk_gb": (
                                round(vm["maxdisk"] / (1024 ** 3), 2)
                                if vm.get("maxdisk")
                                else None
                            ),
                            "ip_addresses": [],
                            "extra": {
                                "node": node,
                                "vmid": vm["vmid"],
                                "type": endpoint,
                            },
                        })

        return vms
