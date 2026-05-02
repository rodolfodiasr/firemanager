"""Read-only Linux SSH connector using paramiko (via asyncio.to_thread)."""
import asyncio
import logging
from typing import Any

import paramiko

logger = logging.getLogger(__name__)

_READ_COMMANDS: dict[str, str] = {
    "uptime":              "uptime",
    "os_release":         "cat /etc/os-release 2>/dev/null || cat /etc/redhat-release 2>/dev/null",
    "uname":              "uname -a",
    "memory":             "free -h",
    "disk":               "df -h",
    "cpu_load":           "top -bn1 | grep -E 'Cpu|cpu' | head -1",
    "processes_top":      "ps aux --sort=-%cpu 2>/dev/null | head -20 || ps aux | head -20",
    "failed_services":    "systemctl list-units --failed --no-pager 2>/dev/null || echo 'systemd unavailable'",
    "open_ports":         "ss -tuln 2>/dev/null || netstat -tuln 2>/dev/null || echo 'ss/netstat unavailable'",
    "recent_errors":      "journalctl -p err --since='2 hours ago' --no-pager -n 30 2>/dev/null || tail -n 30 /var/log/syslog 2>/dev/null || echo 'no log access'",
    "last_logins":        "last -n 10 2>/dev/null",
    "disk_inodes":        "df -i 2>/dev/null | head -10",
    "kernel_messages":    "dmesg --level=err,warn 2>/dev/null | tail -20 || echo 'dmesg unavailable'",
}


def _run_commands_sync(
    host: str,
    port: int,
    username: str,
    password: str,
    private_key_content: str,
    commands: dict[str, str],
    timeout: int,
) -> dict[str, str]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs: dict[str, Any] = {
        "hostname": host,
        "port": port,
        "username": username,
        "timeout": timeout,
        "allow_agent": False,
        "look_for_keys": False,
    }
    if private_key_content:
        import io
        pkey = paramiko.RSAKey.from_private_key(io.StringIO(private_key_content))
        connect_kwargs["pkey"] = pkey
    else:
        connect_kwargs["password"] = password

    results: dict[str, str] = {}
    try:
        client.connect(**connect_kwargs)
        for key, cmd in commands.items():
            try:
                _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
                out = stdout.read().decode(errors="replace").strip()
                err = stderr.read().decode(errors="replace").strip()
                results[key] = out or err or "(sem saída)"
            except Exception as e:
                results[key] = f"ERRO: {e}"
    finally:
        client.close()

    return results


class SshLinuxConnector:
    def __init__(
        self,
        host: str,
        port: int = 22,
        username: str = "",
        password: str = "",
        private_key: str = "",
        timeout: int = 15,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key = private_key
        self.timeout = timeout

    async def gather_diagnostics(self) -> dict[str, str]:
        return await asyncio.to_thread(
            _run_commands_sync,
            self.host,
            self.port,
            self.username,
            self.password,
            self.private_key,
            _READ_COMMANDS,
            self.timeout,
        )

    async def run_commands(self, commands: list[str]) -> tuple[str, bool]:
        """Run arbitrary commands sequentially. Returns (formatted_output, success)."""
        cmd_dict = {f"__cmd_{i}__": cmd for i, cmd in enumerate(commands)}
        try:
            results = await asyncio.to_thread(
                _run_commands_sync,
                self.host, self.port, self.username, self.password,
                self.private_key, cmd_dict, self.timeout,
            )
            lines: list[str] = []
            for i, cmd in enumerate(commands):
                lines.append(f"$ {cmd}")
                lines.append(results.get(f"__cmd_{i}__", "(sem saída)"))
            return "\n".join(lines), True
        except Exception as exc:
            return f"Erro de conexão SSH: {exc}", False

    async def ping(self) -> tuple[bool, str]:
        try:
            result = await asyncio.to_thread(
                _run_commands_sync,
                self.host,
                self.port,
                self.username,
                self.password,
                self.private_key,
                {"ping": "echo ok"},
                10,
            )
            ok = result.get("ping", "").strip() == "ok"
            return ok, "SSH OK" if ok else "Resposta inesperada"
        except Exception as exc:
            return False, str(exc)
