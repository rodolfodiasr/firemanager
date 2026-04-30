"""Compliance reporting service — CIS Benchmark via Wazuh SCA, SSH, or WinRM + AI."""
import asyncio
import json
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.connectors.wazuh_platform import WazuhConnector
from app.models.compliance import ComplianceReport
from app.models.integration import IntegrationType
from app.models.server import Server, ServerOsType
from app.services.integration_service import resolve_integration
from app.utils.crypto import decrypt_credentials

# ── SSH hardening commands ────────────────────────────────────────────────────

_SSH_HARDENING_CMDS: dict[str, str] = {
    "os_release":      "cat /etc/os-release 2>/dev/null | head -10",
    "uname":           "uname -r",
    "sshd_config":     "cat /etc/ssh/sshd_config 2>/dev/null | grep -v '^#' | grep -v '^$'",
    "sysctl_net":      "sysctl net.ipv4.conf.all.send_redirects net.ipv4.conf.default.send_redirects net.ipv4.icmp_echo_ignore_broadcasts net.ipv4.tcp_syncookies net.ipv6.conf.all.disable_ipv6 2>/dev/null",
    "sysctl_kernel":   "sysctl kernel.randomize_va_space kernel.dmesg_restrict kernel.kptr_restrict 2>/dev/null",
    "interactive_users": "awk -F: '($7 !~ /nologin|false|sync|halt|shutdown/) {print $1,$3,$7}' /etc/passwd",
    "shadow_perms":    "stat -c '%a %U %G %n' /etc/shadow /etc/passwd /etc/gshadow 2>/dev/null",
    "sudo_nopasswd":   "grep -r 'NOPASSWD' /etc/sudoers /etc/sudoers.d/ 2>/dev/null || echo 'none'",
    "pwquality":       "cat /etc/security/pwquality.conf 2>/dev/null | grep -v '^#' | grep -v '^$' || echo 'not configured'",
    "login_defs":      "grep -E '^(PASS_MAX_DAYS|PASS_MIN_DAYS|PASS_WARN_AGE|LOGIN_RETRIES)' /etc/login.defs 2>/dev/null",
    "running_services":"systemctl list-units --type=service --state=running --no-pager 2>/dev/null | head -40",
    "auditd_status":   "systemctl is-active auditd 2>/dev/null || echo inactive",
    "firewall_status": "ufw status 2>/dev/null || firewall-cmd --state 2>/dev/null || iptables -L -n --line-numbers 2>/dev/null | head -20 || echo 'no firewall detected'",
    "crontabs":        "ls /etc/cron.d/ /etc/cron.daily/ /etc/cron.weekly/ 2>/dev/null; crontab -l 2>/dev/null || echo 'no root crontab'",
    "world_writable":  "find /etc /usr/bin /usr/sbin -perm -002 -type f 2>/dev/null | head -10 || echo 'none'",
    "suid_binaries":   "find /usr/bin /usr/sbin /bin /sbin -perm -4000 -type f 2>/dev/null | head -20",
}

_AI_SYSTEM_SSH = """\
You are a CIS Benchmark Level 1 compliance auditor for Linux servers.
Given raw server configuration data collected via SSH, analyze it against CIS Benchmark L1 controls.

Respond ONLY with a valid JSON object (no markdown, no explanation):
{
  "policy_name": "CIS <OS> Benchmark Level 1",
  "score_pct": <0-100 float>,
  "passed": <int>,
  "failed": <int>,
  "not_applicable": <int>,
  "controls": [
    {
      "control_id": "1.1.1",
      "title": "...",
      "result": "passed|failed|not_applicable",
      "risk_level": "critical|high|medium|low",
      "description": "what was checked",
      "remediation": "exact command or step to fix"
    }
  ],
  "ai_summary": "2-3 paragraph executive narrative for a security audit report",
  "ai_recommendations": [
    {
      "priority": 1,
      "title": "...",
      "description": "...",
      "remediation_steps": "step-by-step fix or Ansible task"
    }
  ]
}

Include 15-25 controls covering: SSH hardening, kernel parameters, file permissions,
password policy, user accounts, auditd, firewall, and SUID binaries.
ai_recommendations must contain the top 10 most critical failures only.
"""

# ── WinRM CIS hardening commands ─────────────────────────────────────────────

_WINRM_CIS_CMDS: dict[str, str] = {
    "os_info": (
        "Get-CimInstance Win32_OperatingSystem | "
        "Select-Object Caption, Version, BuildNumber | ConvertTo-Json -Compress"
    ),
    "password_policy": "net accounts",
    "audit_policy": (
        "try { auditpol /get /category:* 2>&1 } catch { 'auditpol indisponivel' }"
    ),
    "uac_settings": (
        "try { Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System' "
        "-Name EnableLUA,ConsentPromptBehaviorAdmin,PromptOnSecureDesktop "
        "-ErrorAction SilentlyContinue | ConvertTo-Json -Compress } catch { 'N/A' }"
    ),
    "firewall_profiles": (
        "Get-NetFirewallProfile | "
        "Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction | "
        "ConvertTo-Json -Compress"
    ),
    "smb_settings": (
        "try { $v1 = (Get-SmbServerConfiguration | Select-Object EnableSMB1Protocol).EnableSMB1Protocol; "
        "$sig = (Get-SmbServerConfiguration | Select-Object RequireSecuritySignature).RequireSecuritySignature; "
        "\"SMBv1 Enabled: $v1 | Signing Required: $sig\" } catch { 'N/A' }"
    ),
    "rdp_settings": (
        "try { $nla = (Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp' "
        "-Name UserAuthentication -ErrorAction SilentlyContinue).UserAuthentication; "
        "$enc = (Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp' "
        "-Name MinEncryptionLevel -ErrorAction SilentlyContinue).MinEncryptionLevel; "
        "$rdp = (Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server' "
        "-Name fDenyTSConnections -ErrorAction SilentlyContinue).fDenyTSConnections; "
        "\"RDP Disabled: $rdp | NLA Required: $nla | Encryption Level: $enc\" } catch { 'N/A' }"
    ),
    "windows_update": (
        "try { Get-ItemProperty 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU' "
        "-ErrorAction SilentlyContinue | "
        "Select-Object NoAutoUpdate,AUOptions,ScheduledInstallDay | ConvertTo-Json -Compress } "
        "catch { 'Politica WU nao configurada via GPO' }"
    ),
    "defender_status": (
        "try { Get-MpComputerStatus | "
        "Select-Object AntivirusEnabled,RealTimeProtectionEnabled,"
        "AntivirusSignatureAge,AntivirusSignatureLastUpdated,QuickScanAge | "
        "ConvertTo-Json -Compress } catch { 'Windows Defender indisponivel' }"
    ),
    "lsass_protection": (
        "try { $v = (Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa' "
        "-Name RunAsPPL -ErrorAction SilentlyContinue).RunAsPPL; "
        "\"RunAsPPL: $v\" } catch { 'N/A' }"
    ),
    "ntlm_auth_level": (
        "try { $v = (Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa' "
        "-Name LmCompatibilityLevel -ErrorAction SilentlyContinue).LmCompatibilityLevel; "
        "\"LmCompatibilityLevel: $v (5=NTLMv2 only)\" } catch { 'N/A' }"
    ),
    "wdigest_auth": (
        "try { $v = (Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\WDigest' "
        "-Name UseLogonCredential -ErrorAction SilentlyContinue).UseLogonCredential; "
        "\"WDigest UseLogonCredential: $v (0=disabled is secure)\" } catch { 'chave nao encontrada - seguro por padrao' }"
    ),
    "guest_account": (
        "try { Get-LocalUser -Name Guest | "
        "Select-Object Name,Enabled | ConvertTo-Json -Compress } catch { 'N/A' }"
    ),
    "local_admins": (
        "try { Get-LocalGroupMember -Group 'Administrators' | "
        "Select-Object Name,PrincipalSource | ConvertTo-Json -Compress } catch { 'N/A' }"
    ),
    "auto_logon": (
        "try { $v = (Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon' "
        "-Name AutoAdminLogon -ErrorAction SilentlyContinue).AutoAdminLogon; "
        "\"AutoAdminLogon: $v (0=disabled is secure)\" } catch { 'N/A' }"
    ),
    "insecure_services": (
        "Get-Service Telnet,SNMP,FTP,W3SVC,RemoteRegistry "
        "-ErrorAction SilentlyContinue | "
        "Select-Object Name,Status,StartType | ConvertTo-Json -Compress"
    ),
    "tls_registry": (
        "try { $paths = @("
        "'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\SSL 2.0\\Server',"
        "'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\SSL 3.0\\Server',"
        "'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.0\\Server',"
        "'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.1\\Server'"
        "); $results = @(); foreach ($p in $paths) { "
        "if (Test-Path $p) { $e = (Get-ItemProperty $p -Name Enabled -EA SilentlyContinue).Enabled; "
        "$results += \"$($p.Split('\\')[-2]): Enabled=$e\" } else { $results += \"$($p.Split('\\')[-2]): not configured\" } }; "
        "$results -join ' | ' } catch { 'N/A' }"
    ),
    "screen_lock": (
        "try { $t = (Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System' "
        "-Name InactivityTimeoutSecs -ErrorAction SilentlyContinue).InactivityTimeoutSecs; "
        "\"InactivityTimeoutSecs: $t\" } catch { 'N/A' }"
    ),
    "powershell_logging": (
        "try { $sb = (Get-ItemProperty 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell\\ScriptBlockLogging' "
        "-Name EnableScriptBlockLogging -ErrorAction SilentlyContinue).EnableScriptBlockLogging; "
        "$mod = (Get-ItemProperty 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell\\ModuleLogging' "
        "-Name EnableModuleLogging -ErrorAction SilentlyContinue).EnableModuleLogging; "
        "\"ScriptBlockLogging: $sb | ModuleLogging: $mod\" } catch { 'N/A' }"
    ),
    "event_log_config": (
        "try { Get-EventLog -List | "
        "Where-Object { $_.Log -in 'System','Security','Application' } | "
        "Select-Object Log,MaximumKilobytes | ConvertTo-Json -Compress } catch { 'N/A' }"
    ),
    "bitlocker_status": (
        "try { Get-BitLockerVolume -MountPoint 'C:' | "
        "Select-Object VolumeStatus,ProtectionStatus,EncryptionPercentage | "
        "ConvertTo-Json -Compress } catch { 'BitLocker indisponivel ou sem permissao' }"
    ),
    "open_ports": (
        "Get-NetTCPConnection -State Listen | "
        "Select-Object LocalAddress,LocalPort | Sort-Object LocalPort | "
        "ConvertTo-Json -Compress"
    ),
    "running_services": (
        "Get-Service | Where-Object { $_.Status -eq 'Running' } | "
        "Select-Object Name,DisplayName | ConvertTo-Json -Compress"
    ),
}

_AI_SYSTEM_WINRM = """\
You are a CIS Benchmark Level 1 compliance auditor for Windows Server.
Given raw Windows configuration data collected via WinRM/PowerShell, analyze it against
CIS Microsoft Windows Server Benchmark L1 controls.

Respond ONLY with a valid JSON object (no markdown, no explanation):
{
  "policy_name": "CIS Windows Server Benchmark Level 1",
  "score_pct": <0-100 float>,
  "passed": <int>,
  "failed": <int>,
  "not_applicable": <int>,
  "controls": [
    {
      "control_id": "2.3.1.1",
      "title": "...",
      "result": "passed|failed|not_applicable",
      "risk_level": "critical|high|medium|low",
      "description": "what was checked and what was found",
      "remediation": "exact PowerShell command or GPO path to fix"
    }
  ],
  "ai_summary": "2-3 paragraph executive narrative for a security audit report",
  "ai_recommendations": [
    {
      "priority": 1,
      "title": "...",
      "description": "...",
      "remediation_steps": "step-by-step PowerShell or GPO fix"
    }
  ]
}

Include 15-25 controls covering: account policy, audit policy, UAC, Windows Firewall,
SMB hardening, RDP security, Windows Defender/AV, LSASS protection, NTLMv2 level,
WDigest authentication, guest account, auto logon, TLS/SSL protocols, screen lock,
PowerShell logging, event log sizes, and BitLocker.
Use CIS control IDs from the CIS Microsoft Windows Server Benchmark (e.g. 1.1.x, 2.2.x, 9.x, 18.x).
ai_recommendations must contain the top 10 most critical failures only.
"""

_AI_SYSTEM_WAZUH = """\
You are a CIS Benchmark compliance analyst.
Given Wazuh SCA check results, produce an executive report enrichment.

Respond ONLY with a valid JSON object (no markdown, no explanation):
{
  "ai_summary": "2-3 paragraph executive narrative for a security audit report",
  "ai_recommendations": [
    {
      "priority": 1,
      "title": "...",
      "description": "why this matters",
      "remediation_steps": "exact command or Ansible task to fix"
    }
  ]
}

Focus ai_recommendations on the top 10 FAILED controls ordered by severity.
Write the ai_summary as if presenting results to a CISO — include the score,
top risks, and trend commentary.
"""


def _strip_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    return raw.strip()


def _safe_parse_json(raw: str) -> dict:
    """Try json.loads; if it fails, extract the outermost {...} block and retry."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Find the first { and last } to extract the JSON object
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise


def _sanitize_ssh_output(data: dict[str, str], max_chars: int = 600) -> dict[str, str]:
    """Truncate long outputs and remove characters that break JSON strings."""
    cleaned: dict[str, str] = {}
    for key, value in data.items():
        # Remove null bytes and other control chars except newline/tab
        value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
        # Truncate
        if len(value) > max_chars:
            value = value[:max_chars] + f"... [truncado, {len(value)} chars total]"
        cleaned[key] = value
    return cleaned


# ── Source detection ──────────────────────────────────────────────────────────

async def _get_wazuh_connector(db: AsyncSession, tenant_id: UUID) -> WazuhConnector | None:
    cfg = await resolve_integration(db, IntegrationType.wazuh, tenant_id)
    if not cfg:
        return None
    return WazuhConnector(
        url=cfg.get("url", ""),
        username=cfg.get("username", ""),
        password=cfg.get("password", ""),
        version=cfg.get("version", "4"),
        verify_ssl=cfg.get("verify_ssl", False),
    )


async def detect_source(
    server: Server,
    db: AsyncSession,
    tenant_id: UUID,
    force_source: str | None = None,
) -> tuple[str, str | None, WazuhConnector | None]:
    """Returns (source, agent_id_or_None, wazuh_connector_or_None)."""
    if force_source == "ssh":
        return "ssh", None, None

    connector = await _get_wazuh_connector(db, tenant_id)
    if connector:
        try:
            agent = await connector.find_agent_by_host(server.host, name_hint=server.name)
            if agent:
                return "wazuh", agent.get("id"), connector
            if force_source == "wazuh":
                raise ValueError(
                    f"Nenhum agente Wazuh encontrado para o host '{server.host}'. "
                    "Verifique se o agente está instalado e ativo no Wazuh."
                )
        except Exception as exc:
            if force_source == "wazuh":
                raise
            logger.warning("Wazuh indisponível, usando SSH: %s", exc)

    elif force_source == "wazuh":
        raise ValueError("Integração Wazuh não configurada para este tenant.")

    return "ssh", None, None


# ── Wazuh SCA collection ──────────────────────────────────────────────────────

async def collect_wazuh(
    connector: WazuhConnector,
    agent_id: str,
    policy_id: str | None,
) -> dict[str, Any]:
    policies = await connector.get_sca_policies(agent_id)
    if not policies:
        raise ValueError(f"Nenhuma política SCA encontrada para o agente {agent_id}")

    # Pick the requested policy or the first available one
    if policy_id:
        policy = next((p for p in policies if p.get("policy_id") == policy_id), policies[0])
    else:
        # Prefer CIS policies
        cis = [p for p in policies if "cis" in p.get("name", "").lower()]
        policy = cis[0] if cis else policies[0]

    pid = policy.get("policy_id", "")
    policy_name = policy.get("name", pid)

    checks = await connector.get_sca_checks(agent_id, pid)

    controls = []
    for chk in checks:
        result_raw = chk.get("result", "not applicable")
        if result_raw == "passed":
            result = "passed"
        elif result_raw == "failed":
            result = "failed"
        else:
            result = "not_applicable"

        controls.append({
            "control_id": str(chk.get("id", "")),
            "title": chk.get("title", ""),
            "description": chk.get("description", ""),
            "rationale": chk.get("rationale", ""),
            "remediation": chk.get("remediation", ""),
            "result": result,
            "risk_level": "high" if result == "failed" else "low",
            "references": chk.get("references", ""),
        })

    passed = sum(1 for c in controls if c["result"] == "passed")
    failed = sum(1 for c in controls if c["result"] == "failed")
    na = sum(1 for c in controls if c["result"] == "not_applicable")
    total = passed + failed
    score_pct = round((passed / total * 100) if total > 0 else 0.0, 1)

    return {
        "policy_id": pid,
        "policy_name": policy_name,
        "score_pct": score_pct,
        "passed": passed,
        "failed": failed,
        "not_applicable": na,
        "total_checks": len(controls),
        "controls": controls,
    }


# ── SSH collection ────────────────────────────────────────────────────────────

def _ssh_collect_sync(
    host: str, port: int, username: str, password: str, private_key: str
) -> dict[str, str]:
    import paramiko
    import io

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs: dict[str, Any] = {
        "hostname": host, "port": port, "username": username,
        "timeout": 20, "allow_agent": False, "look_for_keys": False,
    }
    if private_key:
        kwargs["pkey"] = paramiko.RSAKey.from_private_key(io.StringIO(private_key))
    else:
        kwargs["password"] = password

    results: dict[str, str] = {}
    client.connect(**kwargs)
    for key, cmd in _SSH_HARDENING_CMDS.items():
        try:
            _, stdout, stderr = client.exec_command(cmd, timeout=20)
            out = stdout.read().decode(errors="replace").strip()
            err = stderr.read().decode(errors="replace").strip()
            results[key] = out or err or "(sem saída)"
        except Exception as exc:
            results[key] = f"ERRO: {exc}"
    client.close()
    return results


async def collect_ssh(server: Server, creds: dict) -> dict[str, str]:
    import socket
    try:
        socket.getaddrinfo(server.host, server.ssh_port)
    except socket.gaierror:
        raise ValueError(
            f"Não foi possível resolver o hostname '{server.host}'. "
            "Se for um endereço interno/privado, cadastre o servidor usando o IP em vez do hostname."
        )
    return await asyncio.to_thread(
        _ssh_collect_sync,
        server.host,
        server.ssh_port,
        creds.get("username", ""),
        creds.get("password", ""),
        creds.get("private_key", ""),
    )


# ── WinRM collection ─────────────────────────────────────────────────────────

def _winrm_collect_sync(
    host: str, port: int, username: str, password: str, auth_type: str
) -> dict[str, str]:
    import winrm

    if auth_type == "kerberos":
        auth_type = "ntlm"
    transport = auth_type if auth_type in ("ntlm", "ssl", "basic") else "ntlm"
    session = winrm.Session(
        target=f"http{'s' if transport == 'ssl' else ''}://{host}:{port}/wsman",
        auth=(username, password),
        transport=transport,
        server_cert_validation="ignore",
    )
    results: dict[str, str] = {}
    for key, cmd in _WINRM_CIS_CMDS.items():
        try:
            r = session.run_ps(cmd)
            out = r.std_out.decode("utf-8", errors="replace").strip()
            err = r.std_err.decode("utf-8", errors="replace").strip()
            results[key] = out or err or "(sem saída)"
        except Exception as exc:
            results[key] = f"ERRO: {exc}"
    return results


async def collect_winrm(server: Server, creds: dict) -> dict[str, str]:
    return await asyncio.to_thread(
        _winrm_collect_sync,
        server.host,
        server.ssh_port,
        creds.get("username", ""),
        creds.get("password", ""),
        creds.get("auth_type", "ntlm"),
    )


# ── AI enrichment ─────────────────────────────────────────────────────────────

async def _call_ai(system: str, user_msg: str) -> dict:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model="claude-opus-4-7",
        max_tokens=8192,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    return _safe_parse_json(_strip_json(msg.content[0].text))


async def enrich_ssh_with_ai(raw_data: dict[str, str], server: Server) -> dict:
    sanitized = _sanitize_ssh_output(raw_data, max_chars=600)
    formatted = "\n\n".join(f"=== {k} ===\n{v}" for k, v in sanitized.items())
    user_msg = f"Server: {server.name} ({server.host})\nOS type: Linux\n\n{formatted}"
    return await _call_ai(_AI_SYSTEM_SSH, user_msg)


async def enrich_winrm_with_ai(raw_data: dict[str, str], server: Server) -> dict:
    sanitized = _sanitize_ssh_output(raw_data, max_chars=600)
    formatted = "\n\n".join(f"=== {k} ===\n{v}" for k, v in sanitized.items())
    user_msg = f"Server: {server.name} ({server.host})\nOS type: Windows\n\n{formatted}"
    return await _call_ai(_AI_SYSTEM_WINRM, user_msg)


async def enrich_wazuh_with_ai(sca_data: dict, server: Server) -> dict:
    failed_controls = [c for c in sca_data["controls"] if c["result"] == "failed"][:30]
    summary = {
        "server": server.name,
        "policy": sca_data["policy_name"],
        "score_pct": sca_data["score_pct"],
        "passed": sca_data["passed"],
        "failed": sca_data["failed"],
        "not_applicable": sca_data["not_applicable"],
        "top_failures": failed_controls,
    }
    return await _call_ai(_AI_SYSTEM_WAZUH, json.dumps(summary, ensure_ascii=False))


# ── Main entry ────────────────────────────────────────────────────────────────

async def generate_report(
    db: AsyncSession,
    tenant_id: UUID,
    server_id: UUID,
    policy_id: str | None = None,
    force_source: str | None = None,
) -> ComplianceReport:
    result = await db.execute(
        select(Server).where(Server.id == server_id, Server.tenant_id == tenant_id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise ValueError("Servidor não encontrado")

    if server.os_type == ServerOsType.windows:
        creds = decrypt_credentials(server.encrypted_credentials)
        raw = await collect_winrm(server, creds)
        ai_data = await enrich_winrm_with_ai(raw, server)
        controls = ai_data.get("controls", [])
        passed = sum(1 for c in controls if c.get("result") == "passed")
        failed_cnt = sum(1 for c in controls if c.get("result") == "failed")
        na = sum(1 for c in controls if c.get("result") == "not_applicable")
        report = ComplianceReport(
            tenant_id=tenant_id,
            server_id=server_id,
            source="winrm",
            agent_id=None,
            policy_id=None,
            policy_name=ai_data.get("policy_name", "CIS Windows Server Benchmark L1"),
            score_pct=ai_data.get("score_pct", 0.0),
            total_checks=len(controls),
            passed=passed,
            failed=failed_cnt,
            not_applicable=na,
            controls=controls,
            ai_summary=ai_data.get("ai_summary", ""),
            ai_recommendations=ai_data.get("ai_recommendations", []),
        )
    else:
        source, agent_id, wazuh_conn = await detect_source(server, db, tenant_id, force_source)

        if source == "wazuh" and wazuh_conn and agent_id:
            sca_data = await collect_wazuh(wazuh_conn, agent_id, policy_id)
            ai_data = await enrich_wazuh_with_ai(sca_data, server)
            report = ComplianceReport(
                tenant_id=tenant_id,
                server_id=server_id,
                source="wazuh",
                agent_id=agent_id,
                policy_id=sca_data["policy_id"],
                policy_name=sca_data["policy_name"],
                score_pct=sca_data["score_pct"],
                total_checks=sca_data["total_checks"],
                passed=sca_data["passed"],
                failed=sca_data["failed"],
                not_applicable=sca_data["not_applicable"],
                controls=sca_data["controls"],
                ai_summary=ai_data.get("ai_summary", ""),
                ai_recommendations=ai_data.get("ai_recommendations", []),
            )
        else:
            creds = decrypt_credentials(server.encrypted_credentials)
            raw = await collect_ssh(server, creds)
            ai_data = await enrich_ssh_with_ai(raw, server)
            controls = ai_data.get("controls", [])
            passed = sum(1 for c in controls if c.get("result") == "passed")
            failed_cnt = sum(1 for c in controls if c.get("result") == "failed")
            na = sum(1 for c in controls if c.get("result") == "not_applicable")
            report = ComplianceReport(
                tenant_id=tenant_id,
                server_id=server_id,
                source="ssh",
                agent_id=None,
                policy_id=None,
                policy_name=ai_data.get("policy_name", "CIS Linux Benchmark L1"),
                score_pct=ai_data.get("score_pct", 0.0),
                total_checks=len(controls),
                passed=passed,
                failed=failed_cnt,
                not_applicable=na,
                controls=controls,
                ai_summary=ai_data.get("ai_summary", ""),
                ai_recommendations=ai_data.get("ai_recommendations", []),
            )

    db.add(report)
    await db.flush()
    await db.refresh(report)
    return report


async def list_reports(db: AsyncSession, tenant_id: UUID) -> list[ComplianceReport]:
    result = await db.execute(
        select(ComplianceReport)
        .where(ComplianceReport.tenant_id == tenant_id)
        .order_by(ComplianceReport.created_at.desc())
    )
    return list(result.scalars().all())


async def get_report(db: AsyncSession, tenant_id: UUID, report_id: UUID) -> ComplianceReport | None:
    result = await db.execute(
        select(ComplianceReport).where(
            ComplianceReport.id == report_id,
            ComplianceReport.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


_CONTROL_CATEGORIES: list[tuple[str, list[str]]] = [
    ("Filesystem e partições", [
        "partition", "/tmp", "/var/tmp", "/var/log", "/var/log/audit", "/home",
        "/dev/shm", "nodev", "nosuid", "noexec", "mount",
    ]),
    ("Integridade do sistema (AIDE, AppArmor, GRUB)", [
        "aide", "apparmor", "bootloader", "grub", "boot", "integrity",
        "apport", "error reporting",
    ]),
    ("Auditd — instalação e configuração", [
        "auditd", "audit log", "audit tool", "audit backlog", "audit config",
        "audispd", "augenrules", "auditctl",
    ]),
    ("Auditd — regras de coleta", [
        "audit rule", "collected", "date and time", "network environment",
        "user/group", "session initiation", "login and logout", "mandatory access",
        "administration scope", "sudoers", "another user",
    ]),
    ("SSH — configuração e hardening", [
        "sshd", "ssh", "permitrootlogin", "maxauthtries", "logingracetime",
        "clientalive", "macs", "banner", "forwarding", "maxstartups",
    ]),
    ("PAM e política de senhas", [
        "pam", "password", "pwquality", "pwhistory", "faillock", "libpam",
        "privilege escalation", "su command", "sudo log", "inactive",
        "minimum password", "expiration", "dictionary",
    ]),
    ("Firewall (UFW / nftables / iptables)", [
        "ufw", "nftables", "iptables", "ip6tables", "firewall", "loopback",
        "default deny", "chain", "table",
    ]),
    ("Serviços, pacotes e permissões", [
        "cron", "telnet", "ftp", "web server", "apache", "nginx",
        "chrony", "time", "permission", "owner", "group owner",
        "shadow", "gshadow", "journal", "systemd-journal",
    ]),
]


def _categorize_controls(controls: list[dict]) -> dict[str, list[dict]]:
    """Group failed controls into thematic categories for remediation."""
    categorized: dict[str, list[dict]] = {name: [] for name, _ in _CONTROL_CATEGORIES}
    other_key = "Outros controles"
    categorized[other_key] = []

    for ctrl in controls:
        if ctrl.get("result") != "failed":
            continue
        text = (
            ctrl.get("title", "") + " " +
            ctrl.get("description", "") + " " +
            ctrl.get("remediation", "")
        ).lower()

        matched = False
        for cat_name, keywords in _CONTROL_CATEGORIES:
            if any(kw in text for kw in keywords):
                categorized[cat_name].append(ctrl)
                matched = True
                break
        if not matched:
            categorized[other_key].append(ctrl)

    return {k: v for k, v in categorized.items() if v}


async def create_remediation_from_controls(
    db: AsyncSession,
    tenant_id: UUID,
    report: ComplianceReport,
) -> list:
    """Categorize all failed controls and create one RemediationPlan per category."""
    from app.services.remediation_service import generate_plan

    controls: list[dict] = report.controls or []
    failed = [c for c in controls if c.get("result") == "failed"]
    if not failed:
        raise ValueError("Nenhum controle com falha encontrado neste relatório.")

    grouped = _categorize_controls(failed)

    plans = []
    for category, ctrl_list in grouped.items():
        sample = ctrl_list[:15]
        lines = [f"- [{c.get('control_id','')}] {c.get('title','')}" for c in sample]
        if len(ctrl_list) > 15:
            lines.append(f"... and {len(ctrl_list) - 15} more controls in this category")

        controls_block = "\n".join(lines)
        request = (
            f"[CIS Benchmark — {category}]\n\n"
            f"Failed controls ({len(ctrl_list)} total):\n{controls_block}\n\n"
            f"Generate a remediation plan ordered by dependency. "
            f"Max 8 shell commands. Consolidate related steps."
        )

        plan = await generate_plan(
            db=db,
            tenant_id=tenant_id,
            server_id=report.server_id,
            request=request,
            max_tokens=4096,
        )
        plans.append(plan)

    return plans


async def create_remediation_from_report(
    db: AsyncSession,
    tenant_id: UUID,
    report: ComplianceReport,
    recommendation_index: int | None,
) -> list:
    """Create RemediationPlan(s) from compliance recommendations via AI."""
    from app.services.remediation_service import generate_plan

    recs: list[dict] = report.ai_recommendations or []
    if not recs:
        raise ValueError("Este relatório não possui recomendações para remediar.")

    if recommendation_index is not None:
        if recommendation_index < 0 or recommendation_index >= len(recs):
            raise ValueError(f"Índice de recomendação inválido: {recommendation_index}")
        targets = [(recommendation_index, recs[recommendation_index])]
    else:
        targets = list(enumerate(recs))

    plans = []
    for _idx, rec in targets:
        title = rec.get("title", "Remediação CIS")
        steps = rec.get("remediation_steps", "")
        description = rec.get("description", "")
        priority = rec.get("priority", _idx + 1)

        request = (
            f"[CIS Benchmark — Prioridade {priority}] {title}\n\n"
            f"Contexto: {description}\n\n"
            f"Passos de remediação:\n{steps}"
        )

        plan = await generate_plan(
            db=db,
            tenant_id=tenant_id,
            server_id=report.server_id,
            request=request,
        )
        plans.append(plan)

    return plans
