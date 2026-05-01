"""
Dell N-Series DNOS6 connector (N1524P, N1548P, N2000, N3000).

Two quirks vs. the standard base:
  1. Keyboard-interactive auth is advertised but rejected → _force_password_connect
  2. 'terminal length 0' must be re-sent after enable() because session_preparation
     runs it in user-exec mode; privileged exec mode keeps paging active otherwise,
     causing send_command to timeout waiting for the prompt.
"""
from netmiko import NetmikoAuthenticationException, NetmikoTimeoutException

from app.connectors.ssh.base import BaseSSHConnector, SSHResult, _force_password_connect


def _dnos6_device_type() -> str:
    try:
        from netmiko.ssh_dispatcher import CLASS_MAPPER as _NM_MAP
        return "dell_dnos6" if "dell_dnos6" in _NM_MAP else "dell_powerconnect"
    except Exception:
        return "dell_powerconnect"


_DNOS6_TYPE = _dnos6_device_type()


class DellNConnector(BaseSSHConnector):
    """Dell DNOS6 N-Series — password-only auth, enable, paging disable after enable."""

    needs_enable = True
    auto_save = True

    def _device_type(self) -> str:
        return _DNOS6_TYPE

    def _connect_handler(self):
        return _force_password_connect(self._connect_params())

    def _show_sync(self, commands: list[str]) -> SSHResult:
        try:
            parts: list[str] = []
            with self._connect_handler() as conn:
                conn.enable()
                conn.send_command_timing("terminal length 0", last_read=1.0)
                for cmd in commands:
                    out = conn.send_command(cmd, read_timeout=90)
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
        try:
            with self._connect_handler() as conn:
                conn.enable()
                conn.send_command_timing("terminal length 0", last_read=1.0)
                out = conn.send_command("show version", read_timeout=30)
            return SSHResult(success=True, output=self._clean(out)[:400])
        except NetmikoAuthenticationException as exc:
            return SSHResult(success=False, error=f"Autenticação falhou: {exc}")
        except NetmikoTimeoutException as exc:
            return SSHResult(success=False, error=f"Timeout: {exc}")
        except Exception as exc:
            return SSHResult(success=False, error=str(exc))
