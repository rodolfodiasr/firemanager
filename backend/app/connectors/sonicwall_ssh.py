"""SonicWall SSH connector — executes CLI commands via netmiko."""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


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
        try:
            from netmiko import ConnectHandler
            from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException
        except ImportError:
            return False, "netmiko não instalado"

        device_params = {
            "device_type": "sonicwall_ssh",
            "host": self.host,
            "username": self.username,
            "password": self.password,
            "port": self.ssh_port,
            "timeout": 30,
            "session_timeout": 60,
            "global_delay_factor": 2,
        }

        try:
            with ConnectHandler(**device_params) as conn:
                output = conn.send_config_set(commands, cmd_verify=False)
                try:
                    conn.save_config()
                except Exception:
                    pass
            logger.info("SSH commands executed successfully on %s", self.host)
            return True, output
        except Exception as exc:
            name = type(exc).__name__
            msg = str(exc)
            if "auth" in name.lower() or "authentication" in msg.lower():
                return False, f"Falha de autenticação SSH: {msg}"
            if "timeout" in name.lower() or "timed out" in msg.lower():
                return False, f"Timeout na conexão SSH com {self.host}: {msg}"
            return False, f"Erro SSH ({name}): {msg}"

    async def execute_commands(self, commands: list[str]) -> SSHResult:
        """Execute a list of CLI commands via SSH. Returns SSHResult."""
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
