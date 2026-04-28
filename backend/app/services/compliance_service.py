"""Compliance reporting service — CIS Benchmark via Wazuh SCA or SSH + AI."""
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
    if connector and force_source != "ssh":
        try:
            agent = await connector.find_agent_by_host(server.host)
            if agent:
                return "wazuh", agent.get("id"), connector
        except Exception:
            pass

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
    return await asyncio.to_thread(
        _ssh_collect_sync,
        server.host,
        server.ssh_port,
        creds.get("username", ""),
        creds.get("password", ""),
        creds.get("private_key", ""),
    )


# ── AI enrichment ─────────────────────────────────────────────────────────────

async def _call_ai(system: str, user_msg: str) -> dict:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    return json.loads(_strip_json(msg.content[0].text))


async def enrich_ssh_with_ai(raw_data: dict[str, str], server: Server) -> dict:
    formatted = "\n\n".join(f"=== {k} ===\n{v}" for k, v in raw_data.items())
    user_msg = f"Server: {server.name} ({server.host})\nOS type: Linux\n\n{formatted}"
    return await _call_ai(_AI_SYSTEM_SSH, user_msg)


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
        raise ValueError("Relatórios CIS via SSH suportam apenas servidores Linux nesta versão")

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
        failed = sum(1 for c in controls if c.get("result") == "failed")
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
            failed=failed,
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
