import ipaddress
import re as _re

from netmiko import NetmikoAuthenticationException, NetmikoTimeoutException

from app.connectors.base import ExecutionResult, FirewallRule, RoutePolicy, RuleSpec, RouteSpec
from app.connectors.ssh.base import BaseSSHConnector, SSHResult


class JuniperConnector(BaseSSHConnector):
    """
    Juniper JunOS — 'set ...' commands inside configure mode; explicit commit required.

    _show_sync and _test_sync use the base implementation (operational mode, no enable).
    _config_sync overrides to handle configure mode, per-command send, and commit/rollback.
    """

    netmiko_device_type = "juniper_junos"
    needs_enable = False
    auto_save = False  # commit is included in commands or added automatically below

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _safe_filter_name(name: str) -> str:
        return "FM-" + _re.sub(r"[^A-Za-z0-9\-]", "-", name).upper()[:60]

    @staticmethod
    def _format_prefix(cidr: str) -> str:
        """Normalise CIDR for JunOS (strict host bits)."""
        try:
            net = ipaddress.ip_network(cidr, strict=False)
            return str(net)
        except ValueError:
            return cidr

    # ── config mode override ──────────────────────────────────────────────────

    def _config_sync(self, commands: list[str]) -> SSHResult:
        try:
            with self._connect_handler() as conn:
                conn.config_mode()
                parts: list[str] = []
                for cmd in commands:
                    out = conn.send_command(
                        cmd, expect_string=r"[>#%\$]", read_timeout=30
                    )
                    parts.append(out)

                if not any("commit" in c.lower() for c in commands):
                    commit_out = conn.send_command(
                        "commit",
                        expect_string=r"commit complete|error",
                        read_timeout=30,
                    )
                    parts.append(commit_out)
                    if "error" in commit_out.lower():
                        conn.send_command("rollback 0", expect_string=r"[>#%]")
                        combined = self._clean("\n".join(parts))
                        return SSHResult(
                            success=False, output=combined,
                            error="Juniper commit failed — rollback applied",
                            commands_executed=commands,
                        )

                conn.exit_config_mode()
                combined = self._clean("\n".join(parts))

            err = self._first_error(combined)
            if err:
                return SSHResult(
                    success=False, output=combined,
                    error=f"CLI error: {err}",
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

    async def list_rules(self) -> list[FirewallRule]:
        """Parse 'show firewall filter' into FirewallRule objects."""
        result = await self.execute_show_commands(["show firewall filter"])
        rules: list[FirewallRule] = []
        current_filter = ""
        current_term = ""
        src = "any"
        dst = "any"
        action = "accept"
        service = "any"

        for line in result.output.splitlines():
            line = line.rstrip()

            m_filter = _re.match(r"^Filter:\s+(\S+)", line)
            if m_filter:
                current_filter = m_filter.group(1)
                current_term = ""
                continue

            m_term = _re.match(r"^\s+Term:\s+(\S+)", line)
            if m_term:
                if current_term and current_filter:
                    rules.append(FirewallRule(
                        rule_id=f"{current_filter}:{current_term}",
                        name=current_filter,
                        src=src,
                        dst=dst,
                        service=service,
                        action=action,
                        enabled=True,
                        raw={"filter": current_filter, "term": current_term},
                    ))
                current_term = m_term.group(1)
                src = dst = service = "any"
                action = "accept"
                continue

            m_src = _re.match(r"^\s+Source addresses:\s+(\S+)", line)
            if m_src:
                src = m_src.group(1)
                continue

            m_dst = _re.match(r"^\s+Destination addresses:\s+(\S+)", line)
            if m_dst:
                dst = m_dst.group(1)
                continue

            m_port = _re.match(r"^\s+Destination ports:\s+(\S+)", line)
            if m_port:
                service = m_port.group(1)
                continue

            m_action = _re.match(r"^\s+Action:\s+(\S+)", line)
            if m_action:
                action = m_action.group(1)

        if current_term and current_filter:
            rules.append(FirewallRule(
                rule_id=f"{current_filter}:{current_term}",
                name=current_filter,
                src=src,
                dst=dst,
                service=service,
                action=action,
                enabled=True,
                raw={"filter": current_filter, "term": current_term},
            ))

        return rules

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        """Create JunOS firewall filter with a match term."""
        fname = self._safe_filter_name(spec.name)
        action = "discard" if spec.action in ("deny", "drop", "block", "reject") else "accept"
        base = f"set firewall family inet filter {fname} term t1"

        commands: list[str] = []

        src = spec.src_address
        if src and src.lower() not in ("any", "0.0.0.0/0", ""):
            commands.append(f"{base} from source-address {self._format_prefix(src)}")

        dst = spec.dst_address
        if dst and dst.lower() not in ("any", "0.0.0.0/0", ""):
            commands.append(f"{base} from destination-address {self._format_prefix(dst)}")

        svc = spec.service
        if svc and svc not in ("any", "Any", "ALL", ""):
            parts = svc.upper().split("/")
            if len(parts) == 2 and parts[0] in ("TCP", "UDP"):
                commands.append(f"{base} from protocol {parts[0].lower()}")
                commands.append(f"{base} from destination-port {parts[1]}")

        commands.append(f"{base} then {action}")
        # default term to avoid implicit deny dropping everything else
        commands.append(f"set firewall family inet filter {fname} term default then accept")

        if spec.comment:
            commands.append(f"set firewall family inet filter {fname} term t1 from comment \"{spec.comment[:100]}\"")

        result = await self.execute_commands(commands)
        return ExecutionResult(success=result.success, rule_id=fname, error=result.error)

    async def delete_rule(self, rule_id: str) -> ExecutionResult:
        """Delete entire filter or single term ('FILTER_NAME' or 'FILTER_NAME:term')."""
        if ":" in rule_id:
            fname, term = rule_id.split(":", 1)
            cmd = f"delete firewall family inet filter {fname} term {term}"
        else:
            cmd = f"delete firewall family inet filter {rule_id}"
        result = await self.execute_commands([cmd])
        return ExecutionResult(success=result.success, error=result.error)

    async def list_route_policies(self) -> list[RoutePolicy]:
        """Parse 'show route protocol static' into RoutePolicy objects."""
        result = await self.execute_show_commands(["show route protocol static"])
        routes: list[RoutePolicy] = []
        current_dest = ""

        for line in result.output.splitlines():
            m_dest = _re.match(r"^(\S+)\s+\(.*\)", line.strip())
            if m_dest:
                current_dest = m_dest.group(1)
                continue

            m_via = _re.match(r".*>\s*to\s+([\d.]+)\s+via\s+(\S+)", line)
            if m_via and current_dest:
                gw = m_via.group(1)
                iface = m_via.group(2)
                routes.append(RoutePolicy(
                    rule_id=current_dest,
                    name=current_dest,
                    interface=iface,
                    source="any",
                    destination=current_dest,
                    service="any",
                    gateway=gw,
                    metric=1,
                    distance=1,
                    route_type="static",
                    comment="",
                    enabled=True,
                    raw={"line": line.strip()},
                ))
                current_dest = ""

        return routes

    async def create_route_policy(self, spec: RouteSpec) -> ExecutionResult:
        """Add static route: 'set routing-options static route <dest> next-hop <gw>'."""
        dest = self._format_prefix(spec.destination)
        cmd = f"set routing-options static route {dest} next-hop {spec.gateway}"
        if spec.metric not in (1, 0):
            cmd += f" metric {spec.metric}"
        result = await self.execute_commands([cmd])
        return ExecutionResult(success=result.success, rule_id=dest, error=result.error)

    async def delete_route_policy(self, rule_id: str) -> ExecutionResult:
        """Remove static route by destination prefix."""
        dest = self._format_prefix(rule_id)
        result = await self.execute_commands([f"delete routing-options static route {dest}"])
        return ExecutionResult(success=result.success, error=result.error)

    async def get_config_snapshot(self) -> str:
        """Return full running configuration."""
        result = await self.execute_show_commands(["show configuration"])
        return result.output
