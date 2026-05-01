"""
Generic SSH/CLI connector using Netmiko.
Supports: Cisco IOS/IOS-XE, Cisco NX-OS, Juniper JunOS, Aruba OS-CX,
          DELL OS10/PowerConnect, DELL DNOS6 (N-Series),
          HP/H3C Comware (V1910, V3600, V5800).
"""
import asyncio
import re
import time
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

    def _enter_cmdline_mode(self, conn) -> None:
        """Send _cmdline-mode on + Y/N confirms + password for HP Comware V1910/V1920.

        Uses raw write_channel/read_channel with timing to avoid Netmiko send_command
        pattern-matching failures. V1910 shows up to TWO [Y/N] prompts before password.
        """
        cmdline_pwd = self.credentials.get("cmdline_password", "")
        if not cmdline_pwd:
            raise ValueError(
                "HP Comware requer 'Senha cmdline-mode' nas credenciais do dispositivo. "
                "Edite o dispositivo e preencha o campo 'Senha cmdline-mode' (ex: 512900)."
            )
        conn.write_channel("_cmdline-mode on\n")
        time.sleep(1.5)
        output = conn.read_channel()

        # First Y/N: "Continue? [Y/N]:"
        if "[Y/N]" in output or "Y/N" in output:
            conn.write_channel("y\n")
            time.sleep(1.0)
            output = conn.read_channel()

        # Second Y/N: "Before pressing ENTER you must choose 'YES' or 'NO'[Y/N]:"
        if "[Y/N]" in output or "Y/N" in output:
            conn.write_channel("y\n")
            time.sleep(1.0)
            output = conn.read_channel()

        # Password prompt
        if "assword" in output or "password" in output.lower():
            conn.write_channel(cmdline_pwd + "\n")
            time.sleep(1.5)
            conn.read_channel()

        # Re-sync Netmiko's prompt detection after _cmdline-mode changes device state
        conn.set_base_prompt()

        # Disable paging for this session (Comware 5.x syntax — "screen-length disable"
        # used by Netmiko's session_preparation is Comware 7.x only and fails silently on V1910)
        conn.send_command_timing("screen-length 0 temporary", last_read=1.0)

    _COMWARE_SHOW_PREFIXES = ("display ", "ping ", "tracert ", "traceroute ")
    # display current-configuration interface X works from user-view after _cmdline-mode on
    # No system-view needed — _comware_show_sysview_sync is not used for this command
    _COMWARE_SYSVIEW_DISPLAY = ()

    def _is_comware_show(self, cmd: str) -> bool:
        stripped = cmd.strip().lower()
        if stripped.startswith(self._COMWARE_SYSVIEW_DISPLAY):
            return False
        return stripped.startswith(self._COMWARE_SHOW_PREFIXES)

    def _config_sync(self, commands: list[str]) -> SSHResult:
        # For hp_comware, display/ping commands are user-view only — redirect to show mode
        if self.vendor == "hp_comware" and all(self._is_comware_show(c) for c in commands):
            return self._show_sync(commands)

        try:
            with ConnectHandler(**self._connect_params()) as conn:
                if self.vendor in _NEEDS_ENABLE:
                    conn.enable()
                if self.vendor == "hp_comware":
                    self._enter_cmdline_mode(conn)

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
                    display_only = all(c.strip().lower().startswith("display ") for c in commands)
                    if self.vendor in _AUTO_SAVE and not display_only:
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

    def _comware_show_sysview_sync(self, commands: list[str]) -> SSHResult:
        """
        Run Comware display commands that require system-view (e.g. display current-configuration).
        Uses send_command_timing to enter/exit system-view, bypassing Netmiko's check_config_mode()
        which consistently fails on HP 1910 Comware Lite due to a race on the prompt buffer.
        After system-view, base_prompt ("HP V1910 Switch") is present inside "[HP V1910 Switch]"
        so regular send_command prompt detection still works for the display commands.
        """
        try:
            parts: list[str] = []
            with ConnectHandler(**self._connect_params()) as conn:
                self._enter_cmdline_mode(conn)
                # Enter system-view without check_config_mode()
                conn.send_command_timing("system-view", last_read=2)
                for cmd in commands:
                    out = conn.send_command(cmd, read_timeout=30)
                    parts.append(out)
                # Return to user-view
                conn.send_command_timing("quit", last_read=1)
            combined = self._clean("\n".join(parts))
            return SSHResult(success=True, output=combined, commands_executed=commands)
        except NetmikoAuthenticationException as exc:
            return SSHResult(success=False, error=f"Autenticação falhou: {exc}")
        except NetmikoTimeoutException as exc:
            return SSHResult(success=False, error=f"Timeout: {exc}")
        except Exception as exc:
            return SSHResult(success=False, error=str(exc))

    def _show_sync(self, commands: list[str]) -> SSHResult:
        try:
            parts: list[str] = []
            with ConnectHandler(**self._connect_params()) as conn:
                if self.vendor in _NEEDS_ENABLE:
                    conn.enable()
                if self.vendor == "hp_comware":
                    self._enter_cmdline_mode(conn)
                for cmd in commands:
                    effective_cmd = cmd
                    if self.vendor == "hp_comware" and cmd.strip().lower().startswith("display "):
                        # Comware 5.x pager bypass: | no-more prevents ---- More ---- pauses
                        effective_cmd = cmd.rstrip() + " | no-more"
                    out = conn.send_command(effective_cmd, read_timeout=60)
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
        cmd = "display version" if self.vendor == "hp_comware" else "show version"
        try:
            with ConnectHandler(**self._connect_params()) as conn:
                if self.vendor in _NEEDS_ENABLE:
                    conn.enable()
                if self.vendor == "hp_comware":
                    self._enter_cmdline_mode(conn)
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
            if self.vendor == "hp_comware" and any(
                c.strip().lower().startswith(self._COMWARE_SYSVIEW_DISPLAY) for c in commands
            ):
                return await loop.run_in_executor(pool, self._comware_show_sysview_sync, commands)
            return await loop.run_in_executor(pool, self._show_sync, commands)

    async def test_connection(self) -> SSHResult:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            return await loop.run_in_executor(pool, self._test_sync)
