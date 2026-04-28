"""N3 server analyst service — aggregates Zabbix, Wazuh, and SSH data for AI analysis."""
import json
import logging
from uuid import UUID

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.connectors.ssh_linux import SshLinuxConnector
from app.connectors.wazuh_platform import WazuhConnector
from app.connectors.zabbix import ZabbixConnector
from app.models.integration import Integration, IntegrationType
from app.models.server import Server
from app.utils.crypto import decrypt_credentials

logger = logging.getLogger(__name__)

_ANALYST_SYSTEM = """Você é um Analista N3 de Infraestrutura especializado em Linux e Windows Servers.

Seu papel:
- Analisar dados de monitoramento (Zabbix), segurança (Wazuh) e diagnósticos SSH coletados em tempo real
- Identificar problemas, anomalias, gargalos e riscos com base nos dados fornecidos
- Responder com clareza técnica mas sem jargão desnecessário
- Priorizar problemas críticos (vermelho → laranja → amarelo)
- Sugerir ações corretivas quando aplicável, sem executar nada você mesmo
- Sempre citar qual fonte embasou cada conclusão (ex: "Conforme dados do Zabbix...", "O SSH mostrou...")

Restrições importantes:
- Você NÃO executa comandos — apenas analisa e orienta
- Não invente dados que não estejam no contexto fornecido
- Se os dados forem insuficientes para responder, diga claramente e indique o que precisaria ser coletado
- Responda sempre em Português do Brasil
"""


def _fmt_ssh(name: str, diag: dict[str, str]) -> str:
    lines = [f"=== SSH: {name} ==="]
    for key, val in diag.items():
        lines.append(f"[{key}]\n{val}")
    return "\n".join(lines)


def _fmt_zabbix(diag: dict) -> str:
    lines = ["=== Zabbix ==="]
    hosts = diag.get("hosts", [])
    lines.append(f"Hosts monitorados: {len(hosts)}")
    for h in hosts[:10]:
        status = "OK" if h.get("status") == "0" else "PROBLEMA"
        lines.append(f"  • {h.get('name', h.get('host'))} [{status}]")

    problems = diag.get("active_problems", [])
    if problems:
        lines.append(f"\nProblemas ativos ({len(problems)}):")
        for p in problems[:20]:
            lines.append(f"  • [{p.get('severity', '?')}] {p.get('name', p.get('objectid'))}")

    triggers = diag.get("active_triggers", [])
    if triggers:
        lines.append(f"\nTriggers disparados ({len(triggers)}):")
        for t in triggers[:15]:
            prio = t.get("priority", "?")
            lines.append(f"  • [P{prio}] {t.get('description', '?')}")

    return "\n".join(lines)


def _fmt_wazuh(diag: dict) -> str:
    lines = ["=== Wazuh ==="]
    agents = diag.get("agents", [])
    lines.append(f"Agentes: {len(agents)}")
    disconnected = [a for a in agents if a.get("status") != "active"]
    if disconnected:
        lines.append(f"Desconectados: {', '.join(a.get('name', '?') for a in disconnected[:10])}")

    vulns = diag.get("agent_vulnerabilities", {})
    for agent_name, vlist in vulns.items():
        if vlist:
            lines.append(f"\nVulnerabilidades críticas/altas em {agent_name} ({len(vlist)}):")
            for v in vlist[:10]:
                lines.append(f"  • [{v.get('severity','?')}] {v.get('cve','?')} — {v.get('name','?')}")

    alerts = diag.get("recent_high_alerts", [])
    if alerts:
        lines.append(f"\nAlertas recentes nível≥10 ({len(alerts)}):")
        for a in alerts[:15]:
            rule = a.get("rule", {})
            lines.append(f"  • [L{rule.get('level','?')}] {rule.get('description','?')} — agente: {a.get('agent',{}).get('name','?')}")

    return "\n".join(lines)


async def analyze(
    db: AsyncSession,
    tenant_id: UUID,
    question: str,
    server_ids: list[UUID],
    integration_ids: list[UUID],
    host_filter: str | None = None,
) -> tuple[str, list[str]]:
    """Collect data from requested sources and query AI analyst."""
    context_parts: list[str] = []
    sources_used: list[str] = []

    # ── SSH servers ────────────────────────────────────────────────────────────
    for sid in server_ids:
        result = await db.execute(
            select(Server).where(Server.id == sid, Server.tenant_id == tenant_id)
        )
        server = result.scalar_one_or_none()
        if not server:
            continue
        creds = decrypt_credentials(server.encrypted_credentials)
        connector = SshLinuxConnector(
            host=server.host,
            port=server.ssh_port,
            username=creds.get("username", ""),
            password=creds.get("password", ""),
            private_key=creds.get("private_key", ""),
        )
        try:
            diag = await connector.gather_diagnostics()
            context_parts.append(_fmt_ssh(server.name, diag))
            sources_used.append(f"SSH:{server.name}")
        except Exception as exc:
            context_parts.append(f"=== SSH: {server.name} ===\nERRO ao conectar: {exc}")
            sources_used.append(f"SSH:{server.name}(erro)")

    # ── Integrations (Zabbix / Wazuh) ─────────────────────────────────────────
    for iid in integration_ids:
        result = await db.execute(
            select(Integration).where(
                Integration.id == iid,
                (Integration.tenant_id == tenant_id) | Integration.tenant_id.is_(None),
                Integration.is_active.is_(True),
            )
        )
        intg = result.scalar_one_or_none()
        if not intg:
            continue

        config = decrypt_credentials(intg.encrypted_config)

        if intg.type == IntegrationType.zabbix:
            connector_z = ZabbixConnector(
                url=config.get("url", ""),
                token=config.get("token", ""),
                version=config.get("version", "7"),
                verify_ssl=config.get("verify_ssl", False),
            )
            try:
                diag = await connector_z.gather_diagnostics(host_filter=host_filter)
                context_parts.append(_fmt_zabbix(diag))
                sources_used.append(f"Zabbix:{intg.name}")
            except Exception as exc:
                context_parts.append(f"=== Zabbix: {intg.name} ===\nERRO: {exc}")
                sources_used.append(f"Zabbix:{intg.name}(erro)")

        elif intg.type == IntegrationType.wazuh:
            connector_w = WazuhConnector(
                url=config.get("url", ""),
                username=config.get("username", ""),
                password=config.get("password", ""),
                version=config.get("version", "4"),
                verify_ssl=config.get("verify_ssl", False),
            )
            try:
                diag = await connector_w.gather_diagnostics(agent_filter=host_filter)
                context_parts.append(_fmt_wazuh(diag))
                sources_used.append(f"Wazuh:{intg.name}")
            except Exception as exc:
                context_parts.append(f"=== Wazuh: {intg.name} ===\nERRO: {exc}")
                sources_used.append(f"Wazuh:{intg.name}(erro)")

    if not context_parts:
        return (
            "Nenhuma fonte de dados foi selecionada ou todas falharam. "
            "Selecione ao menos um servidor SSH, Zabbix ou Wazuh para análise.",
            [],
        )

    context_text = "\n\n".join(context_parts)
    user_prompt = (
        f"Dados coletados:\n\n{context_text}\n\n"
        f"Pergunta do analista:\n{question}"
    )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=settings.anthropic_max_tokens,
        system=_ANALYST_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )
    answer = msg.content[0].text if msg.content else "Sem resposta do modelo."
    return answer, sources_used
