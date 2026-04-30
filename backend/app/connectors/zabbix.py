"""Zabbix JSON-RPC connector — supports v6.x and v7.x auth models."""
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ZabbixConnector:
    """
    Zabbix 6.x: token goes in JSON-RPC body as {"auth": token}.
    Zabbix 7.x: token goes as HTTP header Authorization: Bearer {token}.
    """

    def __init__(
        self,
        url: str,
        token: str,
        version: str = "7",
        verify_ssl: bool = False,
    ) -> None:
        self.url = url.rstrip("/") + "/api_jsonrpc.php"
        self.token = token
        self.major_version = int(str(version)[0])
        self.verify_ssl = verify_ssl
        self._req_id = 0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _build_headers(self, method: str = "") -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        # apiinfo.version must be called without auth header in Zabbix 7.x
        if self.major_version >= 7 and method != "apiinfo.version":
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _build_payload(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._next_id(),
        }
        if self.major_version < 7:
            payload["auth"] = self.token
        return payload

    async def _call(self, method: str, params: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30.0) as client:
            resp = await client.post(
                self.url,
                json=self._build_payload(method, params),
                headers=self._build_headers(method),
            )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"Zabbix API error: {data['error'].get('data', data['error'])}")
            return data.get("result")

    async def ping(self) -> tuple[bool, str]:
        start = time.monotonic()
        try:
            result = await self._call("apiinfo.version", {})
            latency = (time.monotonic() - start) * 1000
            return True, f"Zabbix {result} — {latency:.0f}ms"
        except Exception as exc:
            return False, str(exc)

    async def get_hosts(self, limit: int = 100) -> list[dict[str, Any]]:
        return await self._call("host.get", {
            "output": ["hostid", "host", "name", "status", "description"],
            "selectInterfaces": ["ip", "port", "type", "main"],
            "limit": limit,
        })

    async def get_problems(self, limit: int = 50) -> list[dict[str, Any]]:
        return await self._call("problem.get", {
            "output": "extend",
            "selectAcknowledges": "count",
            "selectTags": "extend",
            "recent": True,
            "sortfield": ["eventid"],
            "sortorder": "DESC",
            "limit": limit,
        })

    async def get_host_items(self, host_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return await self._call("item.get", {
            "output": ["itemid", "name", "key_", "lastvalue", "units", "lastclock", "value_type"],
            "hostids": [host_id],
            "monitored": True,
            "sortfield": "name",
            "limit": limit,
        })

    async def get_triggers(self, host_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "output": ["triggerid", "description", "priority", "value", "lastchange"],
            "filter": {"value": 1},  # only active (PROBLEM state)
            "sortfield": "priority",
            "sortorder": "DESC",
            "limit": limit,
        }
        if host_id:
            params["hostids"] = [host_id]
        return await self._call("trigger.get", params)

    async def gather_diagnostics(self, host_filter: str | None = None) -> dict[str, Any]:
        """Aggregate hosts + active problems + critical triggers for AI analysis."""
        hosts = await self.get_hosts()
        if host_filter:
            hosts = [h for h in hosts if host_filter.lower() in (h.get("name", "") + h.get("host", "")).lower()]

        problems = await self.get_problems()
        triggers = await self.get_triggers()

        return {
            "hosts": hosts,
            "active_problems": problems,
            "active_triggers": triggers,
        }
