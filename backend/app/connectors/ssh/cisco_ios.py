import ipaddress
import re as _re

from app.connectors.base import ExecutionResult, FirewallRule, RoutePolicy, RuleSpec, RouteSpec
from app.connectors.ssh.base import BaseSSHConnector


class CiscoIOSConnector(BaseSSHConnector):
    """Cisco IOS / IOS-XE — enable required, write mem via save_config."""

    netmiko_device_type = "cisco_ios"
    needs_enable = True
    auto_save = True

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _cidr_to_wildcard(cidr: str) -> tuple[str, str]:
        """Convert CIDR to (network, wildcard) for IOS ACL syntax."""
        try:
            net = ipaddress.ip_network(cidr, strict=False)
            return str(net.network_address), str(net.hostmask)
        except ValueError:
            return cidr, "0.0.0.0"

    @staticmethod
    def _safe_acl_name(name: str) -> str:
        return "FM-" + _re.sub(r"[^A-Za-z0-9\-]", "-", name).upper()[:60]

    # ── structured methods ────────────────────────────────────────────────────

    async def list_rules(self) -> list[FirewallRule]:
        """Parse 'show ip access-lists' into FirewallRule objects."""
        result = await self.execute_show_commands(["show ip access-lists"])
        rules: list[FirewallRule] = []
        current_acl = ""
        for line in result.output.splitlines():
            m_hdr = _re.match(r"^(Extended|Standard) IP access list (.+)", line.strip())
            if m_hdr:
                current_acl = m_hdr.group(2).strip()
                continue
            m_entry = _re.match(r"^\s+(\d+)\s+(permit|deny)\s+(.+)", line)
            if m_entry and current_acl:
                seq, action, rest = m_entry.group(1), m_entry.group(2), m_entry.group(3)
                rest = _re.sub(r"\s*\(\d+ match(es)?\)", "", rest).strip()
                rules.append(FirewallRule(
                    rule_id=f"{current_acl}:{seq}",
                    name=current_acl,
                    src="any",
                    dst="any",
                    service=rest,
                    action=action,
                    enabled=True,
                    raw={"acl": current_acl, "seq": seq, "line": rest},
                ))
        return rules

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        """Create named extended ACL entry. rule_id = ACL name (FM-...)."""
        acl = self._safe_acl_name(spec.name)
        action = "permit" if spec.action in ("accept", "allow", "permit", "pass") else "deny"

        src_net, src_wc = self._cidr_to_wildcard(spec.src_address)
        dst_net, dst_wc = self._cidr_to_wildcard(spec.dst_address)
        src_part = "any" if spec.src_address.lower() in ("any", "0.0.0.0/0", "") else f"{src_net} {src_wc}"
        dst_part = "any" if spec.dst_address.lower() in ("any", "0.0.0.0/0", "") else f"{dst_net} {dst_wc}"

        svc_part = ""
        if spec.service not in ("any", "Any", "ALL", ""):
            parts = spec.service.upper().split("/")
            if len(parts) == 2 and parts[0] in ("TCP", "UDP"):
                svc_part = f" eq {parts[1]}"

        commands = [
            f"ip access-list extended {acl}",
            f" {action} ip {src_part} {dst_part}{svc_part}",
        ]
        if spec.comment:
            commands.append(f" remark {spec.comment[:100]}")

        result = await self.execute_commands(commands)
        return ExecutionResult(success=result.success, rule_id=acl, error=result.error)

    async def delete_rule(self, rule_id: str) -> ExecutionResult:
        """Delete entire ACL (rule_id='ACL_NAME') or single entry ('ACL_NAME:seq')."""
        acl_name = rule_id.split(":")[0]
        seq = rule_id.split(":")[1] if ":" in rule_id else None
        if seq:
            commands = [f"ip access-list extended {acl_name}", f" no {seq}"]
        else:
            commands = [f"no ip access-list extended {acl_name}"]
        result = await self.execute_commands(commands)
        return ExecutionResult(success=result.success, error=result.error)

    async def list_route_policies(self) -> list[RoutePolicy]:
        """Parse 'show ip route static' into RoutePolicy objects."""
        result = await self.execute_show_commands(["show ip route static"])
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
        """Add static route: 'ip route <network> <mask> <gateway>'."""
        try:
            net = ipaddress.ip_network(spec.destination, strict=False)
            dest = f"{net.network_address} {net.netmask}"
        except ValueError:
            dest = spec.destination
        cmd = f"ip route {dest} {spec.gateway}"
        if spec.metric not in (1, 20):
            cmd += f" {spec.metric}"
        result = await self.execute_commands([cmd])
        return ExecutionResult(success=result.success, rule_id=spec.destination, error=result.error)

    async def delete_route_policy(self, rule_id: str) -> ExecutionResult:
        """Remove static route by destination CIDR or network/mask."""
        try:
            net = ipaddress.ip_network(rule_id, strict=False)
            dest = f"{net.network_address} {net.netmask}"
        except ValueError:
            dest = rule_id
        result = await self.execute_commands([f"no ip route {dest}"])
        return ExecutionResult(success=result.success, error=result.error)

    async def get_config_snapshot(self) -> str:
        """Return full running configuration."""
        result = await self.execute_show_commands(["show running-config"])
        return result.output
