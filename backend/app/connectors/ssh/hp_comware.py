"""
HP / H3C Comware 5.x connector (V1910, V3600, V5800, A-Series).

Comware quirks vs. the standard base:
  - Requires '_cmdline-mode on' + password before any config or display command
  - Uses 'quit' instead of 'exit' to leave submodes (_USES_QUIT)
  - 'display ...' commands run in user-view (after _cmdline-mode), not configure
  - Manual paging handling: V1910 ignores 'screen-length disable' (Comware 7 only)
    so we poll read_channel and send space to dismiss '---- More ----' prompts
  - save_config() sends 'save force' — no prompt needed
"""
import re
import time

from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException

from app.connectors.ssh.base import BaseSSHConnector, SSHResult

_MORE_RE = re.compile(r"\s*----\s*More\s*----\s*", re.IGNORECASE)

_COMWARE_SHOW_PREFIXES = ("display ", "ping ", "tracert ", "traceroute ")

# Commands that need system-view to run (currently none — display current-configuration
# interface X works from user-view after _cmdline-mode on)
_COMWARE_SYSVIEW_DISPLAY: tuple[()] = ()


class HPComwareConnector(BaseSSHConnector):
    """HP / H3C Comware 5.x — cmdline-mode, quit-based submodes, manual paging."""

    netmiko_device_type = "hp_comware"
    needs_enable = False
    auto_save = True  # save_config() sends 'save force'

    # ── Comware-specific helpers ──────────────────────────────────────────────

    def _enter_cmdline_mode(self, conn) -> None:
        """Send _cmdline-mode on and handle up to two Y/N prompts + password."""
        cmdline_pwd = self.credentials.get("cmdline_password", "")
        if not cmdline_pwd:
            raise ValueError(
                "HP Comware requer 'Senha cmdline-mode' nas credenciais do dispositivo. "
                "Edite o dispositivo e preencha o campo 'Senha cmdline-mode' (ex: 512900)."
            )
        conn.write_channel("_cmdline-mode on\n")
        time.sleep(1.5)
        output = conn.read_channel()

        if "[Y/N]" in output or "Y/N" in output:
            conn.write_channel("y\n")
            time.sleep(1.0)
            output = conn.read_channel()

        if "[Y/N]" in output or "Y/N" in output:
            conn.write_channel("y\n")
            time.sleep(1.0)
            output = conn.read_channel()

        if "assword" in output or "password" in output.lower():
            conn.write_channel(cmdline_pwd + "\n")
            time.sleep(1.5)
            conn.read_channel()

        conn.set_base_prompt()
        conn.send_command_timing("screen-length 0 temporary", last_read=1.0)

    def _is_comware_show(self, cmd: str) -> bool:
        stripped = cmd.strip().lower()
        if stripped.startswith(_COMWARE_SYSVIEW_DISPLAY):
            return False
        return stripped.startswith(_COMWARE_SHOW_PREFIXES)

    def _comware_send_display(self, conn, cmd: str, timeout: int = 90) -> str:
        """Send a display command and handle '---- More ----' paging manually."""
        conn.write_channel(cmd + "\n")
        parts: list[str] = []
        deadline = time.time() + timeout
        prompt = conn.base_prompt

        while time.time() < deadline:
            time.sleep(0.5)
            chunk = conn.read_channel()
            if chunk:
                parts.append(chunk)
                if "---- More ----" in chunk or "----More----" in chunk:
                    conn.write_channel(" ")
                elif f"<{prompt}>" in chunk or f"[{prompt}]" in chunk:
                    break

        raw = "".join(parts)
        return _MORE_RE.sub("", raw)

    def _comware_show_sysview_sync(self, commands: list[str]) -> SSHResult:
        """Run display commands that require system-view (e.g. display current-configuration)."""
        try:
            parts: list[str] = []
            with ConnectHandler(**self._connect_params()) as conn:
                self._enter_cmdline_mode(conn)
                conn.send_command_timing("system-view", last_read=2)
                for cmd in commands:
                    out = conn.send_command(cmd, read_timeout=30)
                    parts.append(out)
                conn.send_command_timing("quit", last_read=1)
            combined = self._clean("\n".join(parts))
            return SSHResult(success=True, output=combined, commands_executed=commands)
        except NetmikoAuthenticationException as exc:
            return SSHResult(success=False, error=f"Autenticação falhou: {exc}")
        except NetmikoTimeoutException as exc:
            return SSHResult(success=False, error=f"Timeout: {exc}")
        except Exception as exc:
            return SSHResult(success=False, error=str(exc))

    # ── Overridden sync methods ───────────────────────────────────────────────

    def _config_sync(self, commands: list[str]) -> SSHResult:
        # Redirect show-only batches to _show_sync (display/ping in config mode = error)
        if all(self._is_comware_show(c) for c in commands):
            return self._show_sync(commands)

        try:
            with self._connect_handler() as conn:
                self._enter_cmdline_mode(conn)
                # exit_config_mode=False because AI commands include 'quit' at end of each block
                raw = conn.send_config_set(commands, exit_config_mode=False, read_timeout=60)
                combined = self._clean(raw)
                conn.exit_config_mode()  # sends 'quit' back to user-view
                display_only = all(c.strip().lower().startswith("display ") for c in commands)
                if not display_only:
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
        if any(c.strip().lower().startswith(_COMWARE_SYSVIEW_DISPLAY) for c in commands):
            return self._comware_show_sysview_sync(commands)
        try:
            parts: list[str] = []
            with self._connect_handler() as conn:
                self._enter_cmdline_mode(conn)
                for cmd in commands:
                    if cmd.strip().lower().startswith("display "):
                        out = self._comware_send_display(conn, cmd)
                    else:
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
        try:
            with self._connect_handler() as conn:
                self._enter_cmdline_mode(conn)
                out = conn.send_command("display version", read_timeout=20)
            return SSHResult(success=True, output=self._clean(out)[:400])
        except NetmikoAuthenticationException as exc:
            return SSHResult(success=False, error=f"Autenticação falhou: {exc}")
        except NetmikoTimeoutException as exc:
            return SSHResult(success=False, error=f"Timeout: {exc}")
        except Exception as exc:
            return SSHResult(success=False, error=str(exc))
