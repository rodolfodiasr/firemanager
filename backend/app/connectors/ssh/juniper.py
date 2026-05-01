from netmiko import NetmikoAuthenticationException, NetmikoTimeoutException

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
