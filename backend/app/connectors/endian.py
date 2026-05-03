"""Endian Firewall connector — SSH-based automation via paramiko."""
import asyncio
import logging
import re
import time

import paramiko

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

logger = logging.getLogger(__name__)

_SNAPSHOT_COMMANDS: dict[str, str] = {
    "version":     "cat /etc/endian-release 2>/dev/null || cat /etc/issue 2>/dev/null | head -3",
    "iptables":    "iptables-save 2>/dev/null",
    "routes":      "ip route show",
    "interfaces":  "ip addr show",
    "nat":         "iptables -t nat -L -n -v 2>/dev/null",
    "system_info": "uname -a && uptime",
    "dns":         "cat /etc/resolv.conf 2>/dev/null",
}

_FORWARD_CMD = "iptables -L FORWARD -n -v --line-numbers 2>/dev/null"
_NAT_CMD     = "iptables -t nat -L PREROUTING -n -v --line-numbers 2>/dev/null"
_ROUTE_CMD   = "ip route show"


def _ssh_exec(
    host: str,
    port: int,
    username: str,
    password: str,
    commands: dict[str, str],
    timeout: int = 20,
) -> dict[str, str]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    results: dict[str, str] = {}
    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=timeout,
            allow_agent=False,
            look_for_keys=False,
        )
        for key, cmd in commands.items():
            try:
                _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
                out = stdout.read().decode(errors="replace").strip()
                err = stderr.read().decode(errors="replace").strip()
                results[key] = out or err or "(sem saída)"
            except Exception as exc:
                results[key] = f"ERRO: {exc}"
    finally:
        client.close()
    return results


class EndianConnector(BaseConnector):
    """Endian Firewall — SSH-based automation.

    Endian does not expose a public REST API; all operations use paramiko SSH.
    Credentials: auth_type=user_pass, optional ssh_port (default 22).
    Rules created via iptables are runtime-only; for persistence the caller
    should also trigger an iptables-save or Endian config rebuild.
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        ssh_port: int = 22,
        verify_ssl: bool = False,
    ) -> None:
        m = re.match(r"^https?://([^:/]+)", host)
        self.ssh_host = m.group(1) if m else host.split(":")[0]
        self.ssh_port = ssh_port
        self.username = username
        self.password = password

    async def _run(self, commands: dict[str, str]) -> dict[str, str]:
        return await asyncio.to_thread(
            _ssh_exec,
            self.ssh_host,
            self.ssh_port,
            self.username,
            self.password,
            commands,
        )

    # ── connectivity ──────────────────────────────────────────────────────────

    async def test_connection(self) -> ConnectionResult:
        start = time.monotonic()
        try:
            result = await self._run({
                "ver": "cat /etc/endian-release 2>/dev/null || echo 'Endian Firewall'",
            })
            latency = (time.monotonic() - start) * 1000
            ver = result.get("ver", "unknown").splitlines()[0][:80]
            return ConnectionResult(success=True, latency_ms=latency, firmware_version=ver)
        except Exception as exc:
            return ConnectionResult(success=False, error=str(exc))

    # ── rules (iptables FORWARD chain) ────────────────────────────────────────

    async def list_rules(self) -> list[FirewallRule]:
        result = await self._run({"rules": _FORWARD_CMD})
        rules: list[FirewallRule] = []
        for line in result.get("rules", "").splitlines():
            parts = line.split()
            # iptables -v --line-numbers: num pkts bytes target prot opt in out src dst
            if len(parts) >= 10 and parts[0].isdigit():
                rules.append(FirewallRule(
                    rule_id=parts[0],
                    name=f"FORWARD #{parts[0]}",
                    src=parts[8],
                    dst=parts[9],
                    service=parts[4],
                    action=parts[3].lower(),
                    enabled=True,
                    raw={"line": line},
                ))
        return rules

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        action = "ACCEPT" if spec.action in ("accept", "allow", "pass") else "DROP"
        comment = (spec.name or "").replace("'", "")
        cmd = (
            f"iptables -A FORWARD "
            f"-s {spec.src_address} -d {spec.dst_address} "
            f"-j {action} -m comment --comment '{comment}'"
        )
        result = await self._run({"cmd": cmd})
        output = result.get("cmd", "")
        ok = "ERRO:" not in output
        return ExecutionResult(success=ok, error=output if not ok else None)

    async def delete_rule(self, rule_id: str) -> ExecutionResult:
        result = await self._run({"cmd": f"iptables -D FORWARD {rule_id}"})
        output = result.get("cmd", "")
        ok = "ERRO:" not in output
        return ExecutionResult(success=ok, error=output if not ok else None)

    async def edit_rule(self, rule_id: str, spec: RuleSpec) -> ExecutionResult:
        del_result = await self.delete_rule(rule_id)
        if not del_result.success:
            return del_result
        return await self.create_rule(spec)

    async def create_group(self, spec: GroupSpec) -> ExecutionResult:
        cmds: dict[str, str] = {
            "create": f"ipset create {spec.name} hash:net 2>/dev/null || ipset flush {spec.name}",
        }
        for i, member in enumerate(spec.members):
            cmds[f"add_{i}"] = f"ipset add {spec.name} {member}"
        result = await self._run(cmds)
        errors = [v for v in result.values() if "ERRO:" in v]
        return ExecutionResult(
            success=not errors,
            error="; ".join(errors) if errors else None,
        )

    # ── config snapshot ───────────────────────────────────────────────────────

    async def get_config_snapshot(self) -> str:
        result = await self._run(_SNAPSHOT_COMMANDS)
        lines: list[str] = []
        for section, output in result.items():
            lines.append(f"=== {section.upper()} ===")
            lines.append(output)
            lines.append("")
        return "\n".join(lines)

    # ── NAT (iptables PREROUTING) ─────────────────────────────────────────────

    async def list_nat_policies(self) -> list[NatPolicy]:
        result = await self._run({"nat": _NAT_CMD})
        policies: list[NatPolicy] = []
        for line in result.get("nat", "").splitlines():
            parts = line.split()
            if len(parts) >= 10 and parts[0].isdigit():
                policies.append(NatPolicy(
                    rule_id=parts[0],
                    name=f"DNAT #{parts[0]}",
                    inbound="",
                    outbound="",
                    source=parts[8],
                    translated_source="original",
                    destination=parts[9],
                    translated_destination="",
                    service=parts[4],
                    translated_service="original",
                    enabled=True,
                    comment=line.strip(),
                    raw={"line": line},
                ))
        return policies

    async def create_nat_policy(self, spec: NatSpec) -> ExecutionResult:
        cmd = (
            f"iptables -t nat -A PREROUTING "
            f"-d {spec.destination} -j DNAT "
            f"--to-destination {spec.translated_destination}"
        )
        result = await self._run({"cmd": cmd})
        output = result.get("cmd", "")
        ok = "ERRO:" not in output
        return ExecutionResult(success=ok, error=output if not ok else None)

    async def delete_nat_policy(self, rule_id: str) -> ExecutionResult:
        result = await self._run({"cmd": f"iptables -t nat -D PREROUTING {rule_id}"})
        output = result.get("cmd", "")
        ok = "ERRO:" not in output
        return ExecutionResult(success=ok, error=output if not ok else None)

    # ── routes (ip route) ────────────────────────────────────────────────────

    async def list_route_policies(self) -> list[RoutePolicy]:
        result = await self._run({"routes": _ROUTE_CMD})
        routes: list[RoutePolicy] = []
        for i, line in enumerate(result.get("routes", "").splitlines()):
            if not line.strip():
                continue
            parts = line.split()
            dest = parts[0]
            gw = iface = ""
            for j, p in enumerate(parts):
                if p == "via" and j + 1 < len(parts):
                    gw = parts[j + 1]
                if p == "dev" and j + 1 < len(parts):
                    iface = parts[j + 1]
            routes.append(RoutePolicy(
                rule_id=str(i),
                name=dest,
                interface=iface,
                source="any",
                destination=dest,
                service="any",
                gateway=gw or "direct",
                metric=1,
                distance=1,
                route_type="static" if "proto static" in line else "connected",
                comment=line.strip(),
                enabled=True,
                raw={"line": line},
            ))
        return routes

    async def create_route_policy(self, spec: RouteSpec) -> ExecutionResult:
        cmd = f"ip route add {spec.destination} via {spec.gateway}"
        if spec.interface:
            cmd += f" dev {spec.interface}"
        result = await self._run({"cmd": cmd})
        output = result.get("cmd", "")
        ok = "ERRO:" not in output
        return ExecutionResult(success=ok, error=output if not ok else None)

    async def delete_route_policy(self, rule_id: str) -> ExecutionResult:
        routes_result = await self._run({"routes": _ROUTE_CMD})
        lines = [l for l in routes_result.get("routes", "").splitlines() if l.strip()]
        try:
            dest = lines[int(rule_id)].split()[0]
        except (ValueError, IndexError) as exc:
            return ExecutionResult(success=False, error=f"Rota não encontrada: {exc}")
        result = await self._run({"cmd": f"ip route del {dest}"})
        output = result.get("cmd", "")
        ok = "ERRO:" not in output
        return ExecutionResult(success=ok, error=output if not ok else None)

    # ── raw SSH access (bonus — não é parte do BaseConnector) ─────────────────

    async def execute_commands(self, commands: list[str]) -> dict[str, str]:
        """Execute raw SSH commands on Endian Firewall."""
        return await self._run({f"__cmd_{i}__": cmd for i, cmd in enumerate(commands)})

    async def execute_show_commands(self, commands: list[str]) -> dict[str, str]:
        """Run read-only commands on Endian Firewall."""
        return await self.execute_commands(commands)
