"""SonicWall SSH connector — executes CLI commands via paramiko interactive shell."""
import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_READ_DELAY = 0.5   # seconds to wait after each command
_FINAL_DELAY = 1.0  # seconds for final drain
_RECV_SIZE = 65535


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
            time.sleep(1.0)  # wait for banner

            # drain welcome message
            if shell.recv_ready():
                shell.recv(_RECV_SIZE)

            output_parts: list[str] = []

            for cmd in commands:
                shell.sendall((cmd + "\n").encode())
                time.sleep(_READ_DELAY)
                chunk = b""
                while shell.recv_ready():
                    chunk += shell.recv(_RECV_SIZE)
                if chunk:
                    output_parts.append(chunk.decode("utf-8", errors="replace"))

            # final drain
            time.sleep(_FINAL_DELAY)
            chunk = b""
            while shell.recv_ready():
                chunk += shell.recv(_RECV_SIZE)
            if chunk:
                output_parts.append(chunk.decode("utf-8", errors="replace"))

            shell.close()
            client.close()

            full_output = "".join(output_parts)
            logger.info("SSH commands executed on %s:%s", self.host, self.ssh_port)
            return True, full_output

        except paramiko.AuthenticationException as exc:
            return False, f"Falha de autenticação SSH em {self.host}:{self.ssh_port}: {exc}"
        except paramiko.SSHException as exc:
            return False, f"Erro SSH em {self.host}:{self.ssh_port}: {exc}"
        except OSError as exc:
            return False, f"Conexão SSH recusada em {self.host}:{self.ssh_port}: {exc}"
        except Exception as exc:
            return False, f"Erro inesperado SSH ({type(exc).__name__}): {exc}"
        finally:
            try:
                client.close()
            except Exception:
                pass

    async def execute_commands(self, commands: list[str]) -> SSHResult:
        """Execute a list of CLI commands via SSH interactive shell."""
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
