"""Read-only Windows Server connector via WinRM (pywinrm + asyncio.to_thread)."""
import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# PowerShell commands — all read-only, all return JSON where possible
_PS_COMMANDS: dict[str, str] = {
    "os_info": (
        "Get-CimInstance Win32_OperatingSystem | "
        "Select-Object Caption, Version, BuildNumber, "
        "@{N='UptimeHours';E={[math]::Round((Get-Date - $_.LastBootUpTime).TotalHours,1)}} | "
        "ConvertTo-Json -Compress"
    ),
    "cpu": (
        "Get-CimInstance Win32_Processor | "
        "Select-Object Name, LoadPercentage, NumberOfCores, NumberOfLogicalProcessors | "
        "ConvertTo-Json -Compress"
    ),
    "memory": (
        "Get-CimInstance Win32_OperatingSystem | "
        "Select-Object "
        "@{N='TotalGB';E={[math]::Round($_.TotalVisibleMemorySize/1MB,2)}}, "
        "@{N='FreeGB';E={[math]::Round($_.FreePhysicalMemory/1MB,2)}}, "
        "@{N='UsedPct';E={[math]::Round(100-($_.FreePhysicalMemory/$_.TotalVisibleMemorySize*100),1)}} | "
        "ConvertTo-Json -Compress"
    ),
    "disk": (
        "Get-PSDrive -PSProvider FileSystem | "
        "Select-Object Name, Root, "
        "@{N='UsedGB';E={[math]::Round($_.Used/1GB,1)}}, "
        "@{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}} | "
        "ConvertTo-Json -Compress"
    ),
    "failed_services": (
        "Get-Service | Where-Object {$_.Status -eq 'Stopped' -and $_.StartType -eq 'Automatic'} | "
        "Select-Object Name, DisplayName, Status | ConvertTo-Json -Compress"
    ),
    "running_services_count": (
        "Write-Output \"Running: $((Get-Service | Where-Object Status -eq Running).Count) / "
        "$((Get-Service).Count) total\""
    ),
    "top_processes": (
        "Get-Process | Sort-Object CPU -Descending | Select-Object -First 15 "
        "Name, "
        "@{N='CPU_s';E={[math]::Round($_.CPU,1)}}, "
        "@{N='RAM_MB';E={[math]::Round($_.WorkingSet64/1MB,1)}} | "
        "ConvertTo-Json -Compress"
    ),
    "event_log_errors": (
        "try { Get-EventLog -LogName System -EntryType Error,Warning -Newest 20 | "
        "Select-Object TimeGenerated, Source, "
        "@{N='Message';E={$_.Message.Substring(0,[Math]::Min(200,$_.Message.Length))}} | "
        "ConvertTo-Json -Compress } catch { 'Sem acesso ao Event Log' }"
    ),
    "open_ports": (
        "Get-NetTCPConnection -State Listen | "
        "Select-Object LocalAddress, LocalPort | "
        "Sort-Object LocalPort | ConvertTo-Json -Compress"
    ),
    "recent_updates": (
        "Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 10 "
        "HotFixID, Description, InstalledOn | ConvertTo-Json -Compress"
    ),
    "defender_status": (
        "try { Get-MpComputerStatus | "
        "Select-Object AntivirusEnabled, RealTimeProtectionEnabled, "
        "AntivirusSignatureAge, QuickScanAge | ConvertTo-Json -Compress } "
        "catch { 'Windows Defender indisponível ou não instalado' }"
    ),
    "pending_reboot": (
        "$reboot = Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired'; "
        "Write-Output \"Reboot pendente: $reboot\""
    ),
}


def _run_commands_sync(
    host: str,
    port: int,
    username: str,
    password: str,
    auth_type: str,
    verify_ssl: bool,
    commands: dict[str, str],
) -> dict[str, str]:
    import winrm

    transport = auth_type if auth_type in ("ntlm", "kerberos", "ssl", "basic") else "ntlm"
    cert_validation = "validate" if verify_ssl else "ignore"

    session = winrm.Session(
        target=f"http{'s' if transport == 'ssl' else ''}://{host}:{port}/wsman",
        auth=(username, password),
        transport=transport,
        server_cert_validation=cert_validation,
    )

    results: dict[str, str] = {}
    for key, cmd in commands.items():
        try:
            r = session.run_ps(cmd)
            out = r.std_out.decode("utf-8", errors="replace").strip()
            err = r.std_err.decode("utf-8", errors="replace").strip()
            results[key] = out or err or "(sem saída)"
        except Exception as e:
            results[key] = f"ERRO: {e}"

    return results


class WinRMConnector:
    def __init__(
        self,
        host: str,
        port: int = 5985,
        username: str = "",
        password: str = "",
        auth_type: str = "ntlm",
        verify_ssl: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.auth_type = auth_type
        self.verify_ssl = verify_ssl

    async def gather_diagnostics(self) -> dict[str, str]:
        return await asyncio.to_thread(
            _run_commands_sync,
            self.host,
            self.port,
            self.username,
            self.password,
            self.auth_type,
            self.verify_ssl,
            _PS_COMMANDS,
        )

    async def ping(self) -> tuple[bool, str]:
        try:
            result = await asyncio.to_thread(
                _run_commands_sync,
                self.host,
                self.port,
                self.username,
                self.password,
                self.auth_type,
                self.verify_ssl,
                {"ping": "Write-Output 'ok'"},
            )
            ping_out = result.get("ping", "").strip()
            if ping_out == "ok":
                return True, "WinRM OK"
            return False, ping_out or "Resposta inesperada"
        except Exception as exc:
            return False, str(exc)
