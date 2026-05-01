"""
Base SSH connector — shared infrastructure for all CLI-managed network vendors.

Each vendor subclasses BaseSSHConnector and overrides only what differs:
  - Class attributes:  netmiko_device_type, needs_enable, auto_save
  - Methods:           _device_type(), _connect_handler(), _config_sync(),
                       _show_sync(), _test_sync()

The async public interface (execute_commands, execute_show_commands,
test_connection) is identical for all vendors and lives here.
"""
import asyncio
import re
import types
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field

import paramiko
from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException

from app.models.device import Device

# ── Shared regex ─────────────────────────────────────────────────────────────

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_ERROR_RE = re.compile(
    r"(% (Invalid|Ambiguous|Incomplete|Error)|"
    r"syntax error|Command rejected|Error:.*|"
    r"invalid input|command not found)",
    re.IGNORECASE,
)

# ── Password-only SSH client (used by Dell N-Series) ─────────────────────────


class _PasswordOnlySSHClient(paramiko.SSHClient):
    """Force password auth, skipping keyboard-interactive.

    Some switches (Dell N-Series) advertise keyboard-interactive but reject it
    with BadAuthenticationType before password auth is attempted.
    """

    def _auth(self, username, password, *args, **kwargs):  # noqa: ANN001
        self._transport.auth_password(username, password, fallback=False)


@contextmanager
def _force_password_connect(params: dict):
    """ConnectHandler context manager that injects _PasswordOnlySSHClient."""
    conn_params = {**params, "auto_connect": False}
    conn = ConnectHandler(**conn_params)

    def _pw_only_client(self):  # noqa: ANN001
        client = _PasswordOnlySSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        return client

    conn._build_ssh_client = types.MethodType(_pw_only_client, conn)
    conn._open()
    try:
        yield conn
    finally:
        try:
            conn.disconnect()
        except Exception:
            pass


# ── Result dataclass ──────────────────────────────────────────────────────────


@dataclass
class SSHResult:
    success: bool
    output: str = ""
    error: str | None = None
    commands_executed: list[str] = field(default_factory=list)


# ── Base connector ────────────────────────────────────────────────────────────


class BaseSSHConnector:
    """
    Common SSH/CLI connector. Subclass per vendor and override only what differs.

    Class attributes (set in each subclass):
        netmiko_device_type  Netmiko device_type string
        needs_enable         True if vendor requires 'enable' before config/show
        auto_save            True if save_config() should run after send_config_set
    """

    netmiko_device_type: str = "cisco_ios"
    needs_enable: bool = False
    auto_save: bool = False

    def __init__(self, device: Device, credentials: dict):
        self.device = device
        self.credentials = credentials
        self.vendor = device.vendor.value

    # ── Connection helpers ────────────────────────────────────────────────────

    def _device_type(self) -> str:
        return self.netmiko_device_type

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
        if self.needs_enable:
            params["secret"] = (
                self.credentials.get("enable_password")
                or self.credentials.get("password", "")
            )
        return params

    def _connect_handler(self):
        """Return a context manager that yields a connected Netmiko session."""
        return ConnectHandler(**self._connect_params())

    # ── Output helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _clean(text: str) -> str:
        return _ANSI_RE.sub("", text).replace("\r", "")

    def _first_error(self, output: str) -> str | None:
        for line in output.splitlines():
            if _ERROR_RE.search(line):
                return line.strip()
        return None

    # ── Sync execution (run inside ThreadPoolExecutor) ────────────────────────

    def _config_sync(self, commands: list[str]) -> SSHResult:
        """Enter configure mode, send commands, optionally save. Default: IOS-style."""
        try:
            with self._connect_handler() as conn:
                if self.needs_enable:
                    conn.enable()
                raw = conn.send_config_set(commands, read_timeout=60)
                combined = self._clean(raw)
                if self.auto_save:
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
        """Run read-only commands in exec mode. Default: IOS-style send_command."""
        try:
            parts: list[str] = []
            with self._connect_handler() as conn:
                if self.needs_enable:
                    conn.enable()
                for cmd in commands:
                    out = conn.send_command(cmd, read_timeout=60)
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
        """Quick connectivity check via 'show version'."""
        try:
            with self._connect_handler() as conn:
                if self.needs_enable:
                    conn.enable()
                out = conn.send_command("show version", read_timeout=30)
            return SSHResult(success=True, output=self._clean(out)[:400])
        except NetmikoAuthenticationException as exc:
            return SSHResult(success=False, error=f"Autenticação falhou: {exc}")
        except NetmikoTimeoutException as exc:
            return SSHResult(success=False, error=f"Timeout: {exc}")
        except Exception as exc:
            return SSHResult(success=False, error=str(exc))

    # ── Async public interface (identical for all vendors) ────────────────────

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
