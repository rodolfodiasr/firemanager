"""Wazuh platform connector — supports v4.x and v5.x."""
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class WazuhConnector:
    """
    Both v4 and v5 use JWT auth via POST /security/user/authenticate (HTTP Basic).
    The main difference in v5 is some renamed endpoints and new agent fields.
    """

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        version: str = "4",
        verify_ssl: bool = False,
    ) -> None:
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self.v = int(str(version)[0])  # 4 or 5
        self.verify_ssl = verify_ssl
        self._token: str | None = None

    async def _authenticate(self) -> str:
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=15.0) as client:
            resp = await client.post(
                f"{self.url}/security/user/authenticate",
                auth=(self.username, self.password),
            )
            if resp.status_code == 401:
                try:
                    detail = resp.json().get("title", resp.text[:200])
                except Exception:
                    detail = resp.text[:200]
                raise RuntimeError(f"Wazuh autenticação falhou (401): {detail}")
            resp.raise_for_status()
            body = resp.json()
            token = body.get("data", {}).get("token") if isinstance(body.get("data"), dict) else body.get("token")
            if not token:
                raise RuntimeError(f"Wazuh: token não encontrado na resposta — {str(body)[:200]}")
            return token

    async def _get_token(self) -> str:
        if not self._token:
            self._token = await self._authenticate()
        return self._token

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        token = await self._get_token()
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30.0) as client:
            resp = await client.get(
                self.url + path,
                headers={"Authorization": f"Bearer {token}"},
                params=params or {},
            )
            if resp.status_code == 401:
                # Token expired — re-authenticate once
                self._token = None
                token = await self._get_token()
                resp = await client.get(
                    self.url + path,
                    headers={"Authorization": f"Bearer {token}"},
                    params=params or {},
                )
            resp.raise_for_status()
            return resp.json()

    async def ping(self) -> tuple[bool, str]:
        start = time.monotonic()
        try:
            data = await self._get("/")
            latency = (time.monotonic() - start) * 1000
            title = data.get("data", {}).get("title", "Wazuh")
            return True, f"{title} — {latency:.0f}ms"
        except Exception as exc:
            return False, str(exc)

    async def get_agents(self, limit: int = 100) -> list[dict[str, Any]]:
        data = await self._get("/agents", {
            "limit": limit,
            "select": "id,name,ip,status,os,version,lastKeepAlive",
            "sort": "-lastKeepAlive",
        })
        return data.get("data", {}).get("affected_items", [])

    async def get_agent_vulnerabilities(self, agent_id: str, limit: int = 30) -> list[dict[str, Any]]:
        try:
            data = await self._get(f"/vulnerability/{agent_id}", {
                "limit": limit,
                "sort": "-severity",
                "q": "severity=Critical,severity=High",
            })
            return data.get("data", {}).get("affected_items", [])
        except Exception:
            return []

    async def get_security_events_summary(self) -> dict[str, Any]:
        try:
            data = await self._get("/overview/agents")
            return data.get("data", {})
        except Exception:
            return {}

    async def get_sca_summary(self, agent_id: str) -> dict[str, Any]:
        """Security Configuration Assessment summary for an agent."""
        try:
            data = await self._get(f"/sca/{agent_id}")
            return data.get("data", {})
        except Exception:
            return {}

    async def get_sca_policies(self, agent_id: str) -> list[dict[str, Any]]:
        """List SCA policies available for an agent (e.g. CIS Ubuntu 22.04 L1)."""
        try:
            data = await self._get(f"/sca/{agent_id}", {"limit": 50})
            return data.get("data", {}).get("affected_items", [])
        except Exception:
            return []

    async def get_sca_checks(
        self, agent_id: str, policy_id: str, limit: int = 500
    ) -> list[dict[str, Any]]:
        """List individual SCA checks for a policy with pass/fail results."""
        try:
            data = await self._get(
                f"/sca/{agent_id}/checks/{policy_id}",
                {"limit": limit, "offset": 0},
            )
            return data.get("data", {}).get("affected_items", [])
        except Exception:
            return []

    async def find_agent_by_host(self, host: str) -> dict[str, Any] | None:
        """Search for an agent matching the given IP or hostname."""
        try:
            agents = await self.get_agents(limit=500)
            host_lower = host.lower()
            for agent in agents:
                if (
                    agent.get("ip", "").lower() == host_lower
                    or agent.get("name", "").lower() == host_lower
                    or host_lower in agent.get("name", "").lower()
                ):
                    return agent
        except Exception:
            pass
        return None

    async def get_alerts(self, limit: int = 30) -> list[dict[str, Any]]:
        """Recent alerts from all agents."""
        try:
            data = await self._get("/alerts", {
                "limit": limit,
                "sort": "-timestamp",
                "q": "rule.level>=10",  # medium+ severity
            })
            return data.get("data", {}).get("affected_items", [])
        except Exception:
            return []

    async def gather_diagnostics(self, agent_filter: str | None = None) -> dict[str, Any]:
        """Aggregate agents + vulnerabilities + alerts for AI analysis."""
        agents = await self.get_agents()
        if agent_filter:
            agents = [
                a for a in agents
                if agent_filter.lower() in (a.get("name", "") + a.get("ip", "")).lower()
            ]

        # Collect critical/high vulns for each agent (up to 5 agents to avoid timeout)
        vulns: dict[str, list] = {}
        for agent in agents[:5]:
            aid = agent.get("id")
            if aid:
                vulns[agent.get("name", aid)] = await self.get_agent_vulnerabilities(aid)

        alerts = await self.get_alerts()
        summary = await self.get_security_events_summary()

        return {
            "agents": agents,
            "agent_vulnerabilities": vulns,
            "recent_high_alerts": alerts,
            "agents_summary": summary,
        }
