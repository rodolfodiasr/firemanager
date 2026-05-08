"""Cisco ASA connector — SSH CLI via Netmiko."""
import ipaddress
import re as _re

from netmiko import NetmikoAuthenticationException, NetmikoTimeoutException

from app.connectors.base import ExecutionResult, FirewallRule, RoutePolicy, RuleSpec, RouteSpec
from app.connectors.ssh.base import BaseSSHConnector, SSHResult


class CiscoASAConnector(BaseSSHConnector):
    """Cisco ASA — enable required, configure via 'configure terminal' / 'end'."""

    netmiko_device_type = "cisco_asa"
    needs_enable = True
    auto_save = False

    # ── override config sync (ASA uses configure terminal / end explicitly) ───

    def _config_sync(self, commands: list[str]) -> SSHResult:
        """ASA: enable → configure terminal → commands → end."""
        try:
            with self._connect_handler() as conn:
                conn.enable()
                parts: list[str] = []
                for cmd in ["configure terminal"] + commands + ["end"]:
                    out = conn.send_command_timing(cmd, read_timeout=60)
                    parts.append(out)
                combined = self._clean("\n".join(parts))
            err = self._first_error(combined)
            if err:
                return SSHResult(
                    success=False, output=combined, error=f"CLI error: {err}",
                    commands_executed=commands,
                )
            return SSHResult(success=True, output=combined, commands_executed=commands)
        except NetmikoAuthenticationException as exc:
            return SSHResult(success=False, error=f"Autenticação falhou: {exc}",
                             commands_executed=commands)
        except NetmikoTimeoutException as exc:
            return SSHResult(success=False, error=f"Timeout de conexão: {exc}",
                             commands_executed=commands)
        except Exception as exc:
            return SSHResult(success=False, error=str(exc), commands_executed=commands)

    # ── structured methods ────────────────────────────────────────────────────

    async def get_config_snapshot(self) -> str:
        """Return full running configuration."""
        result = await self.execute_show_commands(["show running-config"])
        return result.output

    async def list_rules(self) -> list[FirewallRule]:
        """Parse 'show running-config access-list' into FirewallRule objects."""
        result = await self.execute_show_commands(["show running-config access-list"])
        rules: list[FirewallRule] = []
        for line in result.output.splitlines():
            m = _re.match(
                r"^access-list\s+(\S+)\s+extended\s+(permit|deny)\s+(\S+)\s+(.+)",
                line.strip(),
            )
            if m:
                acl_name, action = m.group(1), m.group(2)
                rules.append(FirewallRule(
                    rule_id=acl_name,
                    name=acl_name,
                    src="any",
                    dst="any",
                    service=m.group(4),
                    action=action,
                    enabled=True,
                    raw={"line": line.strip()},
                ))
        return rules

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        """Create ASA access-list extended entry."""
        action = "permit" if spec.action in ("accept", "allow", "permit", "pass") else "deny"
        acl_name = "FM-" + _re.sub(r"[^A-Za-z0-9\-]", "-", spec.name).upper()[:60]

        src = "any" if spec.src_address.lower() in ("any", "0.0.0.0/0", "") else spec.src_address
        dst = "any" if spec.dst_address.lower() in ("any", "0.0.0.0/0", "") else spec.dst_address

        if spec.service not in ("any", "Any", "ALL", ""):
            parts = spec.service.upper().split("/")
            if len(parts) == 2 and parts[0] in ("TCP", "UDP"):
                proto = parts[0].lower()
                port = parts[1]
                cmd = (
                    f"access-list {acl_name} extended {action} "
                    f"{proto} {src} {dst} eq {port}"
                )
                result = await self.execute_commands([cmd])
                return ExecutionResult(success=result.success, rule_id=acl_name, error=result.error)

        cmd = f"access-list {acl_name} extended {action} ip {src} {dst}"
        result = await self.execute_commands([cmd])
        return ExecutionResult(success=result.success, rule_id=acl_name, error=result.error)

    async def delete_rule(self, rule_id: str) -> ExecutionResult:
        """Remove entire access-list by name."""
        result = await self.execute_commands([f"no access-list {rule_id}"])
        return ExecutionResult(success=result.success, error=result.error)

    async def list_route_policies(self) -> list[RoutePolicy]:
        """Parse 'show route static' into RoutePolicy objects."""
        result = await self.execute_show_commands(["show route static"])
        routes: list[RoutePolicy] = []
        for line in result.output.splitlines():
            m = _re.match(r"^S\s+(\S+)\s+\[\d+/\d+\]\s+via\s+([\d.]+)", line.strip())
            if m:
                routes.append(RoutePolicy(
                    rule_id=m.group(1),
                    name=m.group(1),
                    interface="",
                    source="any",
                    destination=m.group(1),
                    service="any",
                    gateway=m.group(2),
                    metric=1,
                    distance=1,
                    route_type="static",
                    comment="",
                    enabled=True,
                    raw={"line": line.strip()},
                ))
        return routes

    async def create_route_policy(self, spec: RouteSpec) -> ExecutionResult:
        """Add static route on ASA: route <intf> <network> <mask> <gateway> [metric]."""
        try:
            net = ipaddress.ip_network(spec.destination, strict=False)
            dest = f"{net.network_address} {net.netmask}"
        except ValueError:
            dest = spec.destination
        intf = spec.interface or "outside"
        cmd = f"route {intf} {dest} {spec.gateway} {spec.metric}"
        result = await self.execute_commands([cmd])
        return ExecutionResult(success=result.success, rule_id=spec.destination, error=result.error)

    async def delete_route_policy(self, rule_id: str) -> ExecutionResult:
        """Remove static route by destination."""
        try:
            net = ipaddress.ip_network(rule_id, strict=False)
            dest = f"{net.network_address} {net.netmask}"
        except ValueError:
            dest = rule_id
        result = await self.execute_commands([f"no route {dest}"])
        return ExecutionResult(success=result.success, error=result.error)
