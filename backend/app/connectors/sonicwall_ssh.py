"""SonicWall SSH connector — executes CLI commands via paramiko interactive shell.

Flow handled automatically:
  connect → wait for '>' → 'configure' → handle preempt → run commands
  → handle 'commit' password prompt → 'end'
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import asyncio

logger = logging.getLogger(__name__)

_RECV_SIZE = 65535
_CMD_DELAY = 0.6    # seconds to wait after each command
_POLL_SLEEP = 0.1   # polling interval while waiting for prompt


@dataclass
class SSHResult:
    success: bool
    output: str = ""
    commands_executed: list[str] = field(default_factory=list)
    error: str | None = None


class SonicWallSSHConnector:
    def __init__(self, host: str, username: str, password: str, ssh_port: int = 22):
        self.host = host
        self.username = username
        self.password = password
        self.ssh_port = ssh_port

    # ------------------------------------------------------------------
    # Low-level shell helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _recv_all(shell) -> str:
        buf = b""
        while shell.recv_ready():
            buf += shell.recv(_RECV_SIZE)
        return buf.decode("utf-8", errors="replace")

    @staticmethod
    def _wait_for(shell, patterns: list[str], timeout: float = 15.0) -> str:
        """Read output until one of the patterns appears or timeout."""
        buf = b""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if shell.recv_ready():
                buf += shell.recv(_RECV_SIZE)
                decoded = buf.decode("utf-8", errors="replace")
                if any(p in decoded for p in patterns):
                    return decoded
            time.sleep(_POLL_SLEEP)
        return buf.decode("utf-8", errors="replace")

    def _send(self, shell, text: str) -> None:
        shell.sendall((text + "\n").encode())

    # ------------------------------------------------------------------
    # Configure-mode lifecycle
    # ------------------------------------------------------------------

    def _enter_configure(self, shell) -> str:
        """Enter configure mode with real-time prompt handling (50ms poll)."""
        self._send(shell, "configure")

        buf = b""
        preempt_sent = False
        password_sent = False
        deadline = time.monotonic() + 25

        while time.monotonic() < deadline:
            if shell.recv_ready():
                buf += shell.recv(_RECV_SIZE)
                decoded = buf.decode("utf-8", errors="replace")
                # Success
                if "config(" in decoded:
                    return decoded

                # Preempt yes/no prompt — respond immediately
                if not preempt_sent and ("no]:" in decoded or "preempt" in decoded.lower()):
                    self._send(shell, "yes")
                    preempt_sent = True
                    buf = b""
                    continue

                # Password prompt — respond with admin password
                if not password_sent and "assword:" in decoded:
                    self._send(shell, self.password)
                    password_sent = True
                    buf = b""
                    continue

                # Back at user prompt — configure failed
                at_prompt = decoded.rstrip().endswith(">") and "config(" not in decoded
                if at_prompt:
                    if password_sent:
                        raise RuntimeError(
                            "Senha rejeitada ao entrar em configure mode no SonicWall. "
                            "Verifique se o usuário/senha do dispositivo estão corretos."
                        )
                    if preempt_sent:
                        raise RuntimeError("Falha no preempt do modo configure.")
                    # Returned to prompt without any dialog — unexpected failure
                    raise RuntimeError(
                        f"SonicWall retornou ao prompt sem entrar em configure mode. "
                        f"Resposta: {decoded!r}"
                    )

            time.sleep(0.05)  # fast poll

        raise RuntimeError(
            "Timeout ao entrar em modo configure. "
            f"Última resposta: {buf[-300:].decode('utf-8', errors='replace')!r}"
        )

    def _exit_configure(self, shell) -> str:
        """Send 'end'; handle the uncommitted-changes yes/no/cancel dialog."""
        self._send(shell, "end")
        out = self._wait_for(shell, [">", "cancel]:"], timeout=10)
        if "cancel]:" in out or ("yes" in out and "no" in out and "cancel" in out):
            self._send(shell, "yes")
            out += self._wait_for(shell, [">"], timeout=15)
        return out

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    def _run_cmd(self, shell, cmd: str) -> str:
        """Send one command, handle password/confirm prompts, return output."""
        self._send(shell, cmd)
        time.sleep(_CMD_DELAY)
        out = self._recv_all(shell)

        # If 'exit' left configure mode and shows uncommitted-changes dialog,
        # send 'cancel' to return to configure mode so remaining commands run.
        if "cancel]:" in out:
            self._send(shell, "cancel")
            out += self._wait_for(shell, ["config("], timeout=10)
            return out

        if cmd.strip() == "commit":
            # commit prompts for the admin password; wait longer for it to appear
            if "assword:" not in out:
                out += self._wait_for(shell, ["assword:", "config(", "%"], timeout=10)
            if "assword:" in out:
                self._send(shell, self.password)
                out += self._wait_for(shell, ["config(", "ommitted", "Error", "%"], timeout=15)
                if "ccess denied" in out or "ession terminated" in out:
                    raise RuntimeError(
                        "Senha rejeitada pelo SonicWall ao executar 'commit'. "
                        "Verifique as credenciais do dispositivo."
                    )

        return out

    # ------------------------------------------------------------------
    # Main entry point (runs in thread executor)
    # ------------------------------------------------------------------

    def _connect_and_run(self, commands: list[str]) -> tuple[bool, str]:
        import paramiko

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname=self.host,
                port=self.ssh_port,
                username=self.username,
                password=self.password,
                timeout=30,
                look_for_keys=False,
                allow_agent=False,
            )

            shell = client.invoke_shell(width=200, height=50)

            # SonicWall shows a shell-level "Password:" prompt after SSH connect.
            # Paramiko handles SSH-protocol auth; this separate prompt must be
            # answered manually before the CLI ">" appears.
            out_banner = self._wait_for(shell, [">", "assword:"], timeout=15)
            if "assword:" in out_banner and ">" not in out_banner:
                self._send(shell, self.password)
                out_banner += self._wait_for(shell, [">"], timeout=10)

            parts: list[str] = [out_banner]

            # Enter configure mode
            parts.append(self._enter_configure(shell))

            # Execute each command
            for cmd in commands:
                parts.append(self._run_cmd(shell, cmd))

            # Exit configure mode gracefully
            parts.append(self._exit_configure(shell))

            shell.close()
            client.close()

            full = "".join(parts)
            logger.info("SSH session completed on %s:%s", self.host, self.ssh_port)
            return True, full

        except RuntimeError as exc:
            return False, str(exc)
        except Exception as exc:
            import paramiko as _p
            if isinstance(exc, _p.AuthenticationException):
                return False, f"Falha de autenticação SSH em {self.host}:{self.ssh_port}: {exc}"
            if isinstance(exc, _p.SSHException):
                return False, f"Erro SSH em {self.host}:{self.ssh_port}: {exc}"
            if isinstance(exc, OSError):
                return False, f"Conexão SSH recusada em {self.host}:{self.ssh_port}: {exc}"
            return False, f"Erro SSH ({type(exc).__name__}): {exc}"
        finally:
            try:
                client.close()
            except Exception:
                pass

    async def execute_commands(self, commands: list[str]) -> SSHResult:
        """Execute a list of config-mode CLI commands via SSH."""
        if not commands:
            return SSHResult(success=False, error="Nenhum comando SSH fornecido")

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            success, output = await loop.run_in_executor(
                executor, self._connect_and_run, commands
            )

        return SSHResult(
            success=success,
            output=output,
            commands_executed=commands,
            error=None if success else output,
        )

    # ------------------------------------------------------------------
    # Show commands (user exec level — no configure mode)
    # ------------------------------------------------------------------

    def _read_until_prompt(self, shell, timeout: float = 20.0) -> str:
        """Read show command output handling --More-- pagination.

        Returns when the last non-whitespace line ends with '>' (user exec prompt)
        or '#' (configure prompt), or when timeout is reached.
        Sending space advances SonicWall's --More-- pager.
        """
        buf = b""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if shell.recv_ready():
                buf += shell.recv(_RECV_SIZE)
                decoded = buf.decode("utf-8", errors="replace")
                # Advance pager — keep accumulating so full output is preserved
                if "--More--" in decoded or "-- More --" in decoded:
                    shell.sendall(b" ")
                    continue
                # Prompt detected when last non-empty line ends with > or #
                last_line = decoded.rstrip().rsplit("\n", 1)[-1].rstrip()
                if last_line.endswith(">") or last_line.endswith("#"):
                    return decoded
            time.sleep(_POLL_SLEEP)
        return buf.decode("utf-8", errors="replace")

    def _connect_and_show(self, commands: list[str]) -> tuple[bool, str]:
        """Run show commands at user exec level without entering configure mode."""
        import paramiko

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname=self.host,
                port=self.ssh_port,
                username=self.username,
                password=self.password,
                timeout=30,
                look_for_keys=False,
                allow_agent=False,
            )

            # Large height tells SonicWall the terminal has many rows, reducing pagination
            shell = client.invoke_shell(width=250, height=1000)

            # Handle shell-level password prompt (same as _connect_and_run)
            out_banner = self._wait_for(shell, [">", "assword:"], timeout=15)
            if "assword:" in out_banner and ">" not in out_banner:
                self._send(shell, self.password)
                out_banner += self._wait_for(shell, [">"], timeout=10)

            parts: list[str] = [out_banner]

            for cmd in commands:
                self._send(shell, cmd)
                out = self._read_until_prompt(shell, timeout=20)
                parts.append(out)

            shell.close()
            client.close()

            full = "".join(parts)
            logger.info("SSH show session completed on %s:%s", self.host, self.ssh_port)
            return True, full

        except RuntimeError as exc:
            return False, str(exc)
        except Exception as exc:
            import paramiko as _p
            if isinstance(exc, _p.AuthenticationException):
                return False, f"Falha de autenticação SSH em {self.host}:{self.ssh_port}: {exc}"
            if isinstance(exc, _p.SSHException):
                return False, f"Erro SSH em {self.host}:{self.ssh_port}: {exc}"
            if isinstance(exc, OSError):
                return False, f"Conexão SSH recusada em {self.host}:{self.ssh_port}: {exc}"
            return False, f"Erro SSH ({type(exc).__name__}): {exc}"
        finally:
            try:
                client.close()
            except Exception:
                pass

    async def execute_show_commands(self, commands: list[str]) -> SSHResult:
        """Execute read-only show commands at user exec level (no configure mode)."""
        if not commands:
            return SSHResult(success=False, error="Nenhum comando show fornecido")

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            success, output = await loop.run_in_executor(
                executor, self._connect_and_show, commands
            )

        return SSHResult(
            success=success,
            output=output,
            commands_executed=commands,
            error=None if success else output,
        )
