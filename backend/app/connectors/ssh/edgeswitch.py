"""
Ubiquiti EdgeSwitch (EdgeMax 1.x / 2.x) SSH connector.

Quirks vs. the standard base:
  - Uses 'ubiquiti_edgeswitch' Netmiko driver (handles enable + --More-- paging)
  - Some models allow only 1 concurrent SSH session — retried once on socket reset
    in BOTH _show_sync() and _test_sync() (health check)
  - 'terminal length 0' must be sent before show commands to suppress paging
    on models where the Netmiko driver pagination handling is unreliable
  - save_config() sends 'write memory'
"""
import time

from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException

from app.connectors.ssh.base import BaseSSHConnector, SSHResult


class EdgeSwitchConnector(BaseSSHConnector):
    """Ubiquiti EdgeSwitch (EdgeMax line) — firmware 1.x/2.x."""

    netmiko_device_type = "ubiquiti_edgeswitch"
    needs_enable = True
    auto_save = True

    def _connect_params(self) -> dict:
        params = super()._connect_params()
        # EdgeSwitch does not need the extra global_delay_factor=2; it slows
        # session setup enough to conflict with health checks on single-session models
        params["global_delay_factor"] = 1
        params["timeout"] = 45
        params["session_timeout"] = 120
        return params

    def _test_sync(self) -> SSHResult:
        """Health check — disable paging then run show version. Retries once on socket reset.

        Overrides base because EdgeSwitch allows only 1 concurrent SSH session.
        Without retry the health check fails whenever another session is open.
        """
        last_exc: Exception | None = None
        for attempt in range(2):
            if attempt:
                time.sleep(8)  # let the previous session close before retrying
            try:
                with ConnectHandler(**self._connect_params()) as conn:
                    conn.enable()
                    conn.send_command_timing("terminal length 0", last_read=2.0)
                    out = conn.send_command("show version", read_timeout=45)
                return SSHResult(success=True, output=self._clean(out)[:400])
            except NetmikoAuthenticationException as exc:
                return SSHResult(success=False, error=f"Autenticação falhou: {exc}")
            except NetmikoTimeoutException as exc:
                return SSHResult(success=False, error=f"Timeout: {exc}")
            except Exception as exc:
                last_exc = exc
                if "reset by peer" not in str(exc).lower() and "socket" not in str(exc).lower():
                    break  # non-transient — no point retrying
        return SSHResult(success=False, error=str(last_exc))

    def _show_sync(self, commands: list[str]) -> SSHResult:
        """Disable paging then run show commands. Retries once on socket reset."""
        last_exc: Exception | None = None
        for attempt in range(2):
            if attempt:
                time.sleep(5)  # wait before retry — let health-check session close
            try:
                parts: list[str] = []
                with ConnectHandler(**self._connect_params()) as conn:
                    conn.enable()
                    # Disable paging so show running-config returns in one shot
                    conn.send_command_timing("terminal length 0", last_read=2.0)
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
                last_exc = exc
                if "reset by peer" not in str(exc).lower() and "socket" not in str(exc).lower():
                    break  # non-transient error — don't retry
        return SSHResult(success=False, error=str(last_exc))
