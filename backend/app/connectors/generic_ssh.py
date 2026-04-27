"""
Generic SSH/CLI connector using Netmiko.
Supports: Cisco IOS/IOS-XE, Cisco NX-OS, Juniper JunOS, Aruba OS-CX,
          DELL OS10/PowerConnect, DELL DNOS6 (N-Series),
          HP/H3C Comware (V1910, V3600, V5800).
"""
import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException

from app.models.device import Device


@dataclass
class SSHResult:
    success: bool
    output: str = ""
    error: str | None = None
    commands_executed: list[str] = field(default_factory=list)


# Netmiko device_type per vendor value
_DEVICE_TYPE: dict[str, str] = {
    "cisco_ios":  "cisco_ios",
    "cisco_nxos": "cisco_nxos",
    "juniper":    "juniper_junos",
    "aruba":      "aruba_osswitch",
    "dell":       "dell_os10",
    "dell_n":     "dell_dnos6",   # N-Series (N1524P/N1548P/N2000/N3000) running DNOS6
    "hp_comware": "hp_comware",   # HP V1910 / H3C Comware 5.x — system-view, quit
    "ubiquiti":   "ubiquiti_edge",
}

# Vendors that require 'enable' before config mode
_NEEDS_ENABLE = {"cisco_ios", "aruba", "dell_n"}

# Vendors where netmiko.save_config() should run after send_config_set()
# hp_comware: save_config() sends "save force" — no prompt needed
_AUTO_SAVE = {"cisco_ios", "cisco_nxos", "aruba", "dell", "dell_n", "hp_comware"}

# Vendors that use 'quit' instead of 'exit' to leave submode (Comware-based)
_USES_QUIT = {"hp_comware"}

# CLI error patterns
_ERROR_RE = re.compile(
    r"(% (Invalid|Ambiguous|Incomplete|Error)|"
    r"syntax error|Command rejected|Error:.*|"
    r"invalid input|command not found)",
    re.IGNORECASE,
)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


class GenericSSHConnector:
    """SSH/CLI connector for network devices managed via Netmiko."""

    def __init__(self, device: Device, credentials: dict):
        self.device = device
        self.credentials = credentials
        self.vendor = device.vendor.value

    def _device_type(self) -> str:
        base = _DEVICE_TYPE.get(self.vendor, "cisco_ios")
        if self.vendor == "dell":
            os_ver = str(self.credentials.get("os_version", "")).lower()
            if "powerconnect" in os_ver:
                return "dell_powerconnect"
        return base

    def _connect_params(self) -> dict:
        port = int(self.credentials.get("ssh_port", 22))
        params: dict = {
            "device_type": self._device_type(),
            "host":        self.device.host,
            "port":        port,
            "username":    self.credentials.get("username", ""),
            "password":    self.credentials.get("password", ""),
            "timeout":     30,
            "session_timeout": 60,
            "global_delay_factor": 2,
            "fast_cli":    False,
        }
        if self.vendor in _NEEDS_ENABLE:
            params["secret"] = (
                self.credentials.get("enable_password")
                or self.credentials.get("password", "")
            )
        return params

    @staticmethod
    def _clean(text: str) -> str:
        return _ANSI_RE.sub("", text).replace("\r", "")

    def _first_error(self, output: str) -> str | None:
        for line in output.splitlines():
            if _ERROR_RE.search(line):
                return line.strip()
        return None

    # ── sync helpers (run inside ThreadPoolExecutor) ─────────────────────────

    def _config_sync(self, commands: list[str]) -> SSHResult:
        try:
            with ConnectHandler(**self._connect_params()) as conn:
                if self.vendor in _NEEDS_ENABLE:
                    conn.enable()

                if self.vendor == "juniper":
                    # JunOS: set commands run in configure mode; commit must be in list
                    conn.config_mode()
                    parts: list[str] = []
                    for cmd in commands:
                        out = conn.send_command(
                            cmd, expect_string=r"[>#%\$]", read_timeout=30
                        )
                        parts.append(out)
                    if not any("commit" in c.lower() for c in commands):
                        commit_out = conn.send_command(
                            "commit", expect_string=r"commit complete|error",
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
                elif self.vendor in _USES_QUIT:
                    # Comware: send_config_set enters system-view, but AI commands
                    # already include 'quit' at the end of each block. We send raw.
                    raw = conn.send_config_set(
                        commands, exit_config_mode=False, read_timeout=60
                    )
                    combined = self._clean(raw)
                    conn.exit_config_mode()  # sends 'quit' back to user view
                    if self.vendor in _AUTO_SAVE:
                        try:
                            save_out = conn.save_config()
                            combined += "\n" + self._clean(save_out)
                        except Exception:
                            pass
                else:
                    raw = conn.send_config_set(commands, read_timeout=60)
                    combined = self._clean(raw)
                    if self.vendor in _AUTO_SAVE:
                        try:
                            save_out = conn.save_config()
                            combined += "\n" + self._clean(save_out)
                        except Exception:
                            pass

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

    def _show_sync(self, commands: list[str]) -> SSHResult:
        try:
            parts: list[str] = []
            with ConnectHandler(**self._connect_params()) as conn:
                if self.vendor in _NEEDS_ENABLE:
                    conn.enable()
                for cmd in commands:
                    out = conn.send_command(cmd, read_timeout=30)
                    parts.append(out)
            combined = self._clean("\n".join(parts))
            return SSHResult(success=True, output=combined, commands_executed=commands)
        except NetmikoAuthenticationException as exc:
            return SSHResult(success=False, error=f"Autenticação falhou: {exc}")
        except NetmikoTimeoutException as exc:
            return SSHResult(success=False, error=f"Timeout: {exc}")
        except Exception as exc:
            return SSHResult(success=False, error=str(exc))

    def _test_sync(self) -> SSHResult:
        cmd = "show version" if self.vendor != "juniper" else "show version"
        try:
            with ConnectHandler(**self._connect_params()) as conn:
                if self.vendor in _NEEDS_ENABLE:
                    conn.enable()
                out = conn.send_command(cmd, read_timeout=20)
            clean = self._clean(out)
            return SSHResult(success=True, output=clean[:400])
        except NetmikoAuthenticationException as exc:
            return SSHResult(success=False, error=f"Autenticação falhou: {exc}")
        except NetmikoTimeoutException as exc:
            return SSHResult(success=False, error=f"Timeout: {exc}")
        except Exception as exc:
            return SSHResult(success=False, error=str(exc))

    # ── async public interface ───────────────────────────────────────────────

    async def execute_commands(self, commands: list[str]) -> SSHResult:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            return await loop.run_in_executor(pool, self._config_sync, commands)

    async def execute_show_commands(self, commands: list[str]) -> SSHResult:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            return await loop.run_in_executor(pool, self._show_sync, commands)

    async def test_connection(self) -> SSHResult:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            return await loop.run_in_executor(pool, self._test_sync)
