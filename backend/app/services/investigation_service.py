"""Investigation Service — iterative read-only diagnostic framework.

Shared by NetworkAgent, FirewallAgent and N3 Analyst for phased investigation.
All command execution is strictly read-only; write commands are rejected before
reaching the device.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.investigation import InvestigationMessage, InvestigationPhase, InvestigationSession

log = logging.getLogger(__name__)

# ── Read-only command validation ──────────────────────────────────────────────
# These prefixes are safe across all vendors we support.
_READONLY_PREFIXES = re.compile(
    r"^(show|display|get|list|ping|traceroute|tracert|nmap|dig|nslookup|"
    r"ip route|ip addr|ip link|ss|netstat|df|free|uptime|ps|top|journalctl|"
    r"cat /proc|cat /sys|dmesg|uname|hostname|date|who|last|w|id|whoami|"
    r"systemctl status|service .* status|kubectl get|kubectl describe|"
    r"docker ps|docker stats|docker inspect|"
    r"Get-|Select-|Format-|Out-|Measure-|Test-NetConnection|"
    r"Invoke-WebRequest|Resolve-DnsName)",
    re.IGNORECASE,
)

_WRITE_KEYWORDS = re.compile(
    r"\b(set|create|delete|remove|add|insert|update|modify|replace|reset|"
    r"reboot|shutdown|restart|commit|save|write|push|deploy|apply|"
    r"flush|clear|drop|truncate|rm|rmdir|mv|cp|chmod|chown|kill|pkill|"
    r"sudo (?!cat|ls|ps|df|free|uptime|journalctl|dmesg|ip route|ip addr|"
    r"netstat|ss|lsof|who|last|systemctl status|service .* status))\b",
    re.IGNORECASE,
)


def _validate_readonly(commands: list[str]) -> list[str]:
    """Return list of commands that fail the read-only check."""
    violations: list[str] = []
    for cmd in commands:
        cmd_stripped = cmd.strip()
        if not _READONLY_PREFIXES.match(cmd_stripped) and _WRITE_KEYWORDS.search(cmd_stripped):
            violations.append(cmd_stripped)
    return violations


# ── Claude prompts ────────────────────────────────────────────────────────────

_VENDOR_CLI_HINTS: dict[str, str] = {
    "fortinet":   "FortiOS CLI — exemplos: get system status, get system performance status, diagnose sys top 1 20, diagnose netlink interface list, diagnose hardware sysinfo cpu, diagnose hardware sysinfo memory",
    "sonicwall":  "SonicOS CLI — exemplos: show system-uptime, show cpu, show memory, show current-users, show arp-cache, show interface, show log",
    "pfsense":    "pfSense shell (bash) — exemplos: top -b -n 1, vmstat -w 1 5, netstat -s, ifconfig, df -h, cat /var/run/dmesg.boot",
    "opnsense":   "OPNsense shell (bash) — exemplos: top -b -n 1, vmstat -w 1 5, netstat -s, ifconfig, df -h",
    "mikrotik":   "RouterOS CLI — exemplos: /system resource print, /system resource cpu print, /interface print stats, /ip route print, /ip firewall connection print count-only, /log print",
    "endian":     "Endian shell (bash) — exemplos: top -b -n 1, free -m, df -h, netstat -an | head -40",
    "sophos":     "Sophos XG CLI — exemplos: show cpu-usage, show memory-usage, show arp-cache, show interface statistics, system diagnostics show ip-routing-table",
    "cisco_ios":  "Cisco IOS/IOS-XE CLI — exemplos: show processes cpu sorted, show memory summary, show interfaces, show ip route, show version",
    "cisco_nxos": "Cisco NX-OS CLI — exemplos: show system resources, show processes cpu sort, show interface brief, show ip route, show version",
    "cisco_asa":  "Cisco ASA CLI — exemplos: show cpu usage, show memory, show conn count, show interface, show version",
    "juniper":    "Junos CLI (operational mode) — exemplos: show chassis routing-engine, show system processes extensive, show interfaces, show route summary, show version",
    "aruba":      "ArubaOS CLI — exemplos: show cpu, show memory, show ap active, show interface counters, show version",
    "ubiquiti":   "Ubiquiti EdgeOS/UniFi CLI — exemplos: show system processes, show interfaces, show ip route, show arp",
    "edgeswitch": "Ubiquiti EdgeSwitch CLI — exemplos: show system, show port utilization, show mac-addr-table, show interface ethernet",
    "dell":       "Dell OS10 (SmartFabric OS10) CLI — exemplos: show processes cpu, show memory, show interface status, show version, show spanning-tree",
    "dell_n":     "Dell N-Series DNOS6 CLI — exemplos: show processes cpu sort cpu, show memory, show system, show version, show interfaces status, show spanning-tree",
    "hp_comware": "HP Comware CLI — exemplos: display cpu-usage, display memory, display version, display interface brief, display ip routing-table",
    "palo_alto":  "PAN-OS CLI — exemplos: show system resources, show system info, show interface all, show routing route, show system statistics",
    "checkpoint": "Check Point Gaia CLI — exemplos: show routed, show interfaces all, show route, cpview, fw stat",
}

_PLAN_SYSTEM = """Você é um especialista em diagnóstico de infraestrutura de redes e segurança.
Sua tarefa é criar um plano de investigação em fases para diagnosticar um problema descrito pelo analista.

REGRA MAIS IMPORTANTE: Use SOMENTE comandos nativos do vendor/OS indicado no contexto do dispositivo.
Não misture sintaxe de vendors diferentes. Se o device for Dell OS10, use comandos Dell OS10.
Se for Fortinet, use FortiOS. Se for servidor Linux, use bash. Etc.

Regras críticas:
- Todos os comandos devem ser SOMENTE LEITURA (show, display, get, cat, ps, etc.)
- NUNCA inclua comandos que modifiquem configuração, reiniciem serviços ou alterem dados
- Adapte os comandos ao vendor e OS exatos informados no contexto
- Para servidores Linux: use comandos como ps, df, free, ss, journalctl, cat /proc/...
- Para servidores Windows: use Get-* do PowerShell e Test-NetConnection

Retorne SOMENTE JSON válido, sem markdown:
{
  "initial_hypothesis": "hipótese inicial sobre a causa do problema",
  "phases": [
    {
      "phase_number": 1,
      "phase_name": "Nome curto da fase",
      "phase_purpose": "O que esta fase pretende descobrir",
      "commands": ["comando1", "comando2", ...]
    }
  ]
}

Crie de 2 a 4 fases. Cada fase tem no máximo 5 comandos. Vá do diagnóstico geral (fase 1) para o específico.
"""

_ANALYZE_SYSTEM = """Você é um especialista em diagnóstico de infraestrutura de redes e segurança.
Analise os resultados coletados e forneça um diagnóstico claro e acionável.

Responda em Português do Brasil. Seja direto e técnico mas compreensível para um analista N2/N3.

Estruture sua resposta assim:
1. **O que foi encontrado** — resumo do que os dados mostram
2. **Diagnóstico** — causa mais provável do problema
3. **Findings** — lista de achados importantes (pode ser vazia se tudo normal)
4. **Próximos passos** — o que investigar a seguir ou ação recomendada

Se detectar sinais de que o problema envolve outro domínio (firewall quando está analisando rede,
servidores quando está analisando firewall, etc.), mencione explicitamente:
"CROSS_DOMAIN: [descrição breve do que precisa ser investigado no outro domínio]"

Não invente dados que não estejam no output fornecido.
"""

_CHAT_SYSTEM = """Você é um especialista em diagnóstico de infraestrutura de redes e segurança.
Está conduzindo uma investigação iterativa com o analista.

Você tem acesso ao histórico de investigação: fases executadas, dados coletados e análises anteriores.
Responda perguntas do analista com base nesses dados.
Se o analista pedir para executar algo, lembre que esta é uma sessão de diagnóstico read-only.
Se detectar necessidade de investigar outro domínio, sugira "Expandir diagnóstico para [domínio]".

Responda em Português do Brasil.
"""

# ── Phase planning ────────────────────────────────────────────────────────────

async def plan_investigation(
    db: AsyncSession,
    session: InvestigationSession,
) -> list[InvestigationPhase]:
    """Call Claude to generate phased investigation plan and persist phases."""
    from app.services.llm_provider import get_provider
    provider = get_provider(None)

    device_context = await _build_device_context(db, session)
    user_prompt = (
        f"Problema relatado: {session.problem_description}\n\n"
        f"Contexto do ambiente:\n{device_context}\n\n"
        "Gere um plano de investigação em fases usando SOMENTE os comandos do vendor/OS indicado acima."
    )

    messages = [{"role": "user", "content": user_prompt}]
    raw, _, _ = await provider.chat(messages, _PLAN_SYSTEM)

    try:
        plan = json.loads(raw)
    except Exception:
        # Try to extract JSON from markdown blocks
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        plan = json.loads(m.group(1)) if m else {"phases": [], "initial_hypothesis": ""}

    phases: list[InvestigationPhase] = []
    for p in plan.get("phases", []):
        phase = InvestigationPhase(
            session_id=session.id,
            phase_number=p.get("phase_number", len(phases) + 1),
            phase_name=p.get("phase_name", f"Fase {len(phases) + 1}"),
            phase_purpose=p.get("phase_purpose"),
            commands=p.get("commands", []),
            status="pending",
        )
        db.add(phase)
        phases.append(phase)

    # Add planning assistant message with hypothesis
    hypothesis = plan.get("initial_hypothesis", "")
    if hypothesis:
        msg = InvestigationMessage(
            session_id=session.id,
            role="assistant",
            content=f"**Hipótese inicial:** {hypothesis}\n\nPlano de investigação criado com {len(phases)} fases.",
        )
        db.add(msg)

    await db.flush()
    session.status = "active"
    return phases


# ── Phase execution ───────────────────────────────────────────────────────────

async def execute_phase(
    db: AsyncSession,
    session: InvestigationSession,
    phase: InvestigationPhase,
) -> str:
    """Execute a phase's commands read-only against the target device/server.
    Returns combined raw output.
    """
    violations = _validate_readonly(phase.commands)
    if violations:
        raise ValueError(f"Comandos não permitidos (somente leitura): {violations}")

    phase.status = "executing"
    await db.flush()

    raw_output = ""
    if session.agent_type in ("network", "firewall"):
        raw_output = await _execute_device_commands(db, session, phase.commands)
    elif session.agent_type == "n3":
        raw_output = await _execute_server_commands(db, session, phase.commands)
    else:
        raw_output = "(Agente unificado — execute cada sub-agente individualmente)"

    phase.raw_output = raw_output
    phase.executed_at = datetime.now(timezone.utc)
    phase.status = "done"
    await db.flush()

    return raw_output


async def _execute_device_commands(
    db: AsyncSession,
    session: InvestigationSession,
    commands: list[str],
) -> str:
    from app.models.device import Device
    from app.connectors.factory import get_ssh_connector

    result = await db.execute(
        select(Device).where(Device.id == session.device_id)
    )
    device = result.scalar_one_or_none()
    if not device:
        return "Dispositivo não encontrado."

    # All investigation uses SSH — read-only show commands
    try:
        connector = get_ssh_connector(device)
        ssh_result = await connector.execute_show_commands(commands)
        return ssh_result.output or "(sem saída)"
    except NotImplementedError:
        return (
            f"Investigação via SSH não suportada para o vendor '{device.vendor.value}'. "
            "Use o Inspetor ao Vivo para visualizar o estado atual deste dispositivo."
        )
    except Exception as exc:
        return f"Erro ao conectar via SSH: {exc}"


async def _execute_server_commands(
    db: AsyncSession,
    session: InvestigationSession,
    commands: list[str],
) -> str:
    from app.models.server import Server, ServerOsType
    from app.connectors.ssh_linux import SshLinuxConnector
    from app.connectors.winrm_windows import WinRMConnector
    from app.utils.crypto import decrypt_credentials

    if not session.server_id:
        # N3 without a specific server — collect from Zabbix/Wazuh only
        return await _collect_monitoring_data(db, session)

    result = await db.execute(
        select(Server).where(Server.id == session.server_id)
    )
    server = result.scalar_one_or_none()
    if not server:
        return "Servidor não encontrado."

    creds = decrypt_credentials(server.encrypted_credentials)
    outputs: list[str] = []

    if server.os_type == ServerOsType.windows:
        connector: SshLinuxConnector | WinRMConnector = WinRMConnector(
            host=server.host,
            port=server.ssh_port,
            username=creds.get("username", ""),
            password=creds.get("password", ""),
            auth_type=creds.get("auth_type", "ntlm"),
            verify_ssl=creds.get("verify_ssl", False),
        )
    else:
        connector = SshLinuxConnector(
            host=server.host,
            port=server.ssh_port,
            username=creds.get("username", ""),
            password=creds.get("password", ""),
            private_key=creds.get("private_key", ""),
        )

    output, _ok = await connector.run_commands(commands)
    outputs.append(output)

    # Optionally append monitoring data for cross-correlation
    if session.integration_ids:
        mon = await _collect_monitoring_data(db, session)
        if mon:
            outputs.append(f"\n--- Dados de Monitoramento ---\n{mon}")

    return "\n\n".join(outputs)


async def _collect_monitoring_data(db: AsyncSession, session: InvestigationSession) -> str:
    """Pull Zabbix/Wazuh data for N3 sessions that have integration_ids."""
    if not session.integration_ids:
        return ""

    from app.models.integration import Integration, IntegrationType
    from app.connectors.zabbix import ZabbixConnector
    from app.connectors.wazuh_platform import WazuhConnector
    from app.utils.crypto import decrypt_credentials

    parts: list[str] = []
    for iid_str in session.integration_ids:
        try:
            iid = UUID(iid_str)
        except Exception:
            continue
        result = await db.execute(
            select(Integration).where(
                Integration.id == iid,
                Integration.is_active.is_(True),
            )
        )
        intg = result.scalar_one_or_none()
        if not intg:
            continue
        config = decrypt_credentials(intg.encrypted_config)
        try:
            if intg.type == IntegrationType.zabbix:
                c = ZabbixConnector(
                    url=config.get("url", ""),
                    token=config.get("token", ""),
                    version=config.get("version", "7"),
                    verify_ssl=config.get("verify_ssl", False),
                )
                diag = await c.gather_diagnostics()
                parts.append(f"=== Zabbix: {intg.name} ===\n{_fmt_zabbix_brief(diag)}")
            elif intg.type == IntegrationType.wazuh:
                w = WazuhConnector(
                    url=config.get("url", ""),
                    username=config.get("username", ""),
                    password=config.get("password", ""),
                    verify_ssl=config.get("verify_ssl", False),
                )
                diag = await w.gather_diagnostics()
                parts.append(f"=== Wazuh: {intg.name} ===\n{_fmt_wazuh_brief(diag)}")
        except Exception as exc:
            parts.append(f"=== {intg.name} ===\nERRO: {exc}")
    return "\n\n".join(parts)


def _fmt_zabbix_brief(diag: dict) -> str:
    lines = []
    problems = diag.get("active_problems", [])
    if problems:
        lines.append(f"Problemas ativos: {len(problems)}")
        for p in problems[:10]:
            lines.append(f"  [{p.get('severity','?')}] {p.get('name', p.get('objectid'))}")
    else:
        lines.append("Sem problemas ativos.")
    return "\n".join(lines)


def _fmt_wazuh_brief(diag: dict) -> str:
    lines = []
    alerts = diag.get("recent_high_alerts", [])
    if alerts:
        lines.append(f"Alertas recentes (≥10): {len(alerts)}")
        for a in alerts[:10]:
            rule = a.get("rule", {})
            lines.append(f"  [L{rule.get('level','?')}] {rule.get('description','?')}")
    else:
        lines.append("Sem alertas recentes de alto nível.")
    return "\n".join(lines)


# ── Phase analysis ────────────────────────────────────────────────────────────

async def analyze_phase(
    db: AsyncSession,
    session: InvestigationSession,
    phase: InvestigationPhase,
) -> str:
    """Call Claude to analyze raw output and produce structured findings."""
    from app.services.llm_provider import get_provider
    provider = get_provider(None)

    history_text = _build_history_context(session)
    user_prompt = (
        f"Problema investigado: {session.problem_description}\n\n"
        f"Fase atual: {phase.phase_name}\n"
        f"Propósito: {phase.phase_purpose or 'N/A'}\n\n"
        f"Comandos executados e saída:\n{phase.raw_output or '(sem saída)'}\n\n"
        f"{history_text}"
    )

    messages = [{"role": "user", "content": user_prompt}]
    analysis, _, _ = await provider.chat(messages, _ANALYZE_SYSTEM)

    # Extract cross-domain hint if present
    cross_match = re.search(r"CROSS_DOMAIN:\s*(.+)", analysis)
    if cross_match:
        session.cross_domain_detected = True
        session.cross_domain_hint = cross_match.group(1).strip()

    # Extract findings (numbered or bulleted lines)
    findings: list[str] = []
    for line in analysis.split("\n"):
        line = line.strip()
        if line.startswith(("- ", "• ", "* ")) or re.match(r"^\d+\.", line):
            text = re.sub(r"^[-•*\d.]\s+", "", line).strip()
            if text and len(text) > 10:
                findings.append(text)

    phase.analysis = analysis
    phase.findings = findings[:10]  # cap at 10
    await db.flush()

    # Persist as assistant message
    msg = InvestigationMessage(
        session_id=session.id,
        role="assistant",
        content=analysis,
        phase_number=phase.phase_number,
    )
    db.add(msg)
    await db.flush()

    # Update session current_phase
    if phase.phase_number > session.current_phase:
        session.current_phase = phase.phase_number
    await db.flush()

    return analysis


# ── Iterative chat ────────────────────────────────────────────────────────────

async def chat_in_investigation(
    db: AsyncSession,
    session: InvestigationSession,
    user_message: str,
) -> str:
    """Continue a conversation within an active investigation."""
    from app.services.llm_provider import get_provider
    provider = get_provider(None)

    # Persist user message
    db.add(InvestigationMessage(
        session_id=session.id,
        role="user",
        content=user_message,
        phase_number=session.current_phase or None,
    ))
    await db.flush()

    # Build full conversation for Claude
    history_context = _build_history_context(session)
    system = (
        _CHAT_SYSTEM
        + f"\n\nContexto da investigação:\n{history_context}"
    )

    # Build messages list from saved history
    chat_messages = []
    for m in session.messages:
        if m.role in ("user", "assistant"):
            chat_messages.append({"role": m.role, "content": m.content})

    response, _, _ = await provider.chat(chat_messages, system)

    # Detect cross-domain escalation suggestions in response
    cross_match = re.search(r"CROSS_DOMAIN:\s*(.+)", response)
    if cross_match and not session.cross_domain_detected:
        session.cross_domain_detected = True
        session.cross_domain_hint = cross_match.group(1).strip()
        await db.flush()

    db.add(InvestigationMessage(
        session_id=session.id,
        role="assistant",
        content=response,
        phase_number=session.current_phase or None,
    ))
    await db.flush()

    return response


# ── Synthesis ─────────────────────────────────────────────────────────────────

async def synthesize_investigation(
    db: AsyncSession,
    session: InvestigationSession,
) -> str:
    """Generate final synthesis after all phases are done."""
    from app.services.llm_provider import get_provider
    provider = get_provider(None)

    phases_text = ""
    for phase in session.phases:
        if phase.status == "done" and phase.analysis:
            phases_text += f"\n### Fase {phase.phase_number}: {phase.phase_name}\n"
            phases_text += f"Comandos: {', '.join(phase.commands)}\n"
            phases_text += f"Análise: {phase.analysis}\n"

    system = """Você é especialista em diagnóstico de infraestrutura.
Gere uma síntese executiva da investigação completa.
Inclua: causa raiz identificada (ou hipóteses rankeadas), ações recomendadas priorizadas,
e se há necessidade de investigação em outro domínio (redes, firewall, servidores).
Responda em Português do Brasil, de forma clara e acionável."""

    user_prompt = (
        f"Problema original: {session.problem_description}\n\n"
        f"Resultados das fases:\n{phases_text}"
    )

    synthesis, _, _ = await provider.chat(
        [{"role": "user", "content": user_prompt}], system
    )

    session.synthesis = synthesis
    session.status = "done"
    await db.flush()

    return synthesis


# ── Export to AI Assistant ────────────────────────────────────────────────────

async def export_to_assistant(
    db: AsyncSession,
    session: InvestigationSession,
    user_id: UUID,
    tenant_id: UUID,
) -> UUID:
    """Create an AI Assistant session pre-loaded with investigation context.
    Returns the new assistant session ID.
    """
    from app.models.assistant import AssistantSession, AssistantMessage

    context = _build_export_context(session)
    title = f"Runbook: {session.problem_description[:60]}"

    asst_session = AssistantSession(
        tenant_id=tenant_id,
        user_id=user_id,
        title=title,
        model_used="claude-sonnet-4-6",
    )
    db.add(asst_session)
    await db.flush()
    await db.refresh(asst_session)

    # Seed first message with investigation summary as context
    seed_content = (
        f"**Contexto de investigação importado**\n\n"
        f"Problema: {session.problem_description}\n\n"
        f"{context}\n\n"
        "O que mais você precisa sobre esta investigação?"
    )
    db.add(AssistantMessage(
        session_id=asst_session.id,
        role="assistant",
        content=seed_content,
        model="claude-sonnet-4-6",
    ))
    await db.flush()

    return asst_session.id


# ── Context helpers ───────────────────────────────────────────────────────────

async def _build_device_context(db: AsyncSession, session: InvestigationSession) -> str:
    from app.models.device import Device
    from app.models.server import Server

    parts = [f"Tipo de agente: {session.agent_type}"]

    if session.device_id:
        result = await db.execute(select(Device).where(Device.id == session.device_id))
        device = result.scalar_one_or_none()
        if device:
            parts.append(f"Device: {device.name}")
            parts.append(f"Vendor: {device.vendor.value}")
            parts.append(f"Categoria: {device.category.value}")
            if device.firmware_version:
                parts.append(f"Firmware/OS: {device.firmware_version}")
            hint = _VENDOR_CLI_HINTS.get(device.vendor.value)
            if hint:
                parts.append(f"Sintaxe CLI correta para este vendor: {hint}")
        else:
            parts.append(f"Device ID: {session.device_id}")

    if session.server_id:
        result = await db.execute(select(Server).where(Server.id == session.server_id))
        server = result.scalar_one_or_none()
        if server:
            parts.append(f"Servidor: {server.name} ({server.os_type.value if hasattr(server.os_type, 'value') else server.os_type})")
        else:
            parts.append(f"Server ID: {session.server_id}")

    if session.integration_ids:
        parts.append(f"Integrações: {', '.join(session.integration_ids)}")

    return "\n".join(parts)


def _build_history_context(session: InvestigationSession) -> str:
    if not session.phases:
        return ""
    lines = ["Investigação anterior:"]
    for phase in session.phases:
        if phase.status == "done" and phase.analysis:
            lines.append(f"\nFase {phase.phase_number} — {phase.phase_name}: concluída")
            if phase.findings:
                lines.append(f"Achados: {'; '.join(phase.findings[:3])}")
    return "\n".join(lines) if len(lines) > 1 else ""


def _build_export_context(session: InvestigationSession) -> str:
    lines: list[str] = []
    if session.synthesis:
        lines.append(f"**Síntese final:**\n{session.synthesis}")
    else:
        for phase in session.phases:
            if phase.status == "done" and phase.analysis:
                lines.append(f"**Fase {phase.phase_number}: {phase.phase_name}**")
                lines.append(phase.analysis[:500])
    if session.cross_domain_hint:
        lines.append(f"\n⚠️ **Ponto de escalação:** {session.cross_domain_hint}")
    return "\n\n".join(lines)
