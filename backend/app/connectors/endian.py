"""Endian Firewall connector (basic HTTP connectivity check)."""
import time

import httpx

from app.connectors.base import (
    BaseConnector,
    ConnectionResult,
    ExecutionResult,
    FirewallRule,
    GroupSpec,
    NatPolicy,
    NatSpec,
    RoutePolicy,
    RouteSpec,
    RuleSpec,
)


class EndianConnector(BaseConnector):
    """Endian Firewall — connectivity test via web interface.

    Endian does not expose a public REST API; this connector verifies
    reachability and provides a placeholder for future SSH-based automation.
    Credentials: auth_type=user_pass.
    """

    def __init__(self, host: str, username: str, password: str, verify_ssl: bool = False) -> None:
        self.base_url = host.rstrip("/")
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl

    async def test_connection(self) -> ConnectionResult:
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(verify=self.verify_ssl, timeout=10.0) as client:
                resp = await client.get(self.base_url, follow_redirects=True)
                latency = (time.monotonic() - start) * 1000
                reachable = resp.status_code < 500
                return ConnectionResult(
                    success=reachable,
                    latency_ms=latency,
                    firmware_version="unknown",
                    error=None if reachable else f"HTTP {resp.status_code}",
                )
        except Exception as exc:
            return ConnectionResult(success=False, error=str(exc))

    async def list_rules(self) -> list[FirewallRule]:
        return []

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        return ExecutionResult(success=False, error="Endian REST API not available — use SSH automation")

    async def delete_rule(self, rule_id: str) -> ExecutionResult:
        return ExecutionResult(success=False, error="Endian REST API not available")

    async def edit_rule(self, rule_id: str, spec: RuleSpec) -> ExecutionResult:
        return ExecutionResult(success=False, error="Endian REST API not available")

    async def create_group(self, spec: GroupSpec) -> ExecutionResult:
        return ExecutionResult(success=False, error="Endian REST API not available")

    async def get_config_snapshot(self) -> str:
        return ""

    async def list_nat_policies(self) -> list[NatPolicy]:
        return []

    async def create_nat_policy(self, spec: NatSpec) -> ExecutionResult:
        return ExecutionResult(success=False, error="Endian REST API not available")

    async def delete_nat_policy(self, rule_id: str) -> ExecutionResult:
        return ExecutionResult(success=False, error="Endian REST API not available")

    async def list_route_policies(self) -> list[RoutePolicy]:
        return []

    async def create_route_policy(self, spec: RouteSpec) -> ExecutionResult:
        return ExecutionResult(success=False, error="Endian REST API not available")

    async def delete_route_policy(self, rule_id: str) -> ExecutionResult:
        return ExecutionResult(success=False, error="Endian REST API not available")
