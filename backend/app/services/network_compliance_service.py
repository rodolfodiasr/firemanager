"""Network device compliance service — Fortinet REST + Cisco IOS/HP Comware SSH.

Checks are aligned to CIS Controls v8 and CIS Network Device Benchmarks.
Each check produces a control dict compatible with the server ComplianceReport model:
  control_id : str   e.g. "FGT-01"
  title      : str
  risk_level : "critical" | "high" | "medium" | "low"
  result     : "passed" | "failed" | "not_applicable"
  evidence   : str   what was observed
  remediation: str   how to fix (only for failed)
"""
from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance import ComplianceReport
from app.models.device import Device, VendorEnum

logger = logging.getLogger(__name__)

# ── helpers ───────────────────────────────────────────────────────────────────

def _ctrl(
    control_id: str,
    title: str,
    risk_level: str,
    result: str,
    evidence: str,
    remediation: str = "",
) -> dict:
    return {
        "control_id": control_id,
        "title": title,
        "risk_level": risk_level,
        "result": result,
        "evidence": evidence,
        "remediation": remediation if result == "failed" else "",
    }


def _pass(control_id: str, title: str, risk_level: str, evidence: str) -> dict:
    return _ctrl(control_id, title, risk_level, "passed", evidence)


def _fail(control_id: str, title: str, risk_level: str, evidence: str, fix: str) -> dict:
    return _ctrl(control_id, title, risk_level, "failed", evidence, fix)


def _na(control_id: str, title: str, risk_level: str, reason: str) -> dict:
    return _ctrl(control_id, title, risk_level, "not_applicable", reason)


# ── Fortinet checks ───────────────────────────────────────────────────────────

async def _collect_fortinet(device: Device) -> list[dict]:
    """Collect compliance data via Fortinet REST API and return control list."""
    from app.utils.crypto import decrypt_credentials

    creds = decrypt_credentials(device.encrypted_credentials)
    token = creds.get("token", "")
    vdom = creds.get("vdom") or "root"

    controls: list[dict] = []

    import httpx
    protocol = "https" if device.use_ssl else "http"
    base_url = f"{protocol}://{device.host}:{device.port}"
    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"},
        verify=False,
        timeout=20.0,
    ) as client:

        # ── FGT-01: Admin idle timeout ≤ 15 min ──────────────────────────────
        try:
            r = await client.get(f"/api/v2/cmdb/system/global?vdom={vdom}&format=admintimeout,admin-https-redirect,admin-https-ssl-versions,strong-crypto")
            if r.status_code == 200:
                g = r.json().get("results", {})
                timeout = g.get("admintimeout", 480)
                if timeout <= 15:
                    controls.append(_pass("FGT-01", "Timeout de sessão admin ≤ 15 min", "high",
                        f"admintimeout={timeout} min"))
                else:
                    controls.append(_fail("FGT-01", "Timeout de sessão admin ≤ 15 min", "high",
                        f"admintimeout={timeout} min (deve ser ≤ 15)",
                        "System > Settings > Administration Settings > Idle Timeout: defina ≤ 15 min"))

                # ── FGT-02: HTTPS redirect (HTTP mgmt desabilitado) ───────────
                redirect = g.get("admin-https-redirect", "enable")
                if redirect == "enable":
                    controls.append(_pass("FGT-02", "Redirecionamento HTTP→HTTPS habilitado", "high",
                        "admin-https-redirect=enable"))
                else:
                    controls.append(_fail("FGT-02", "Redirecionamento HTTP→HTTPS habilitado", "high",
                        "admin-https-redirect=disable — HTTP de gerenciamento exposto",
                        "config system global → set admin-https-redirect enable"))

                # ── FGT-03: TLS 1.2+ apenas ───────────────────────────────────
                ssl_vers = g.get("admin-https-ssl-versions", "")
                weak = any(v in str(ssl_vers) for v in ("tlsv1-0", "tlsv1-1", "sslv3"))
                if not weak:
                    controls.append(_pass("FGT-03", "TLS 1.2+ apenas no gerenciamento HTTPS", "high",
                        f"admin-https-ssl-versions={ssl_vers or 'padrão (TLS 1.2+)'}"))
                else:
                    controls.append(_fail("FGT-03", "TLS 1.2+ apenas no gerenciamento HTTPS", "high",
                        f"admin-https-ssl-versions inclui versões fracas: {ssl_vers}",
                        "config system global → set admin-https-ssl-versions tlsv1-2 tlsv1-3"))

                # ── FGT-04: Strong crypto ─────────────────────────────────────
                strong = g.get("strong-crypto", "disable")
                if strong == "enable":
                    controls.append(_pass("FGT-04", "Strong-crypto habilitado (ciphers seguros)", "medium",
                        "strong-crypto=enable"))
                else:
                    controls.append(_fail("FGT-04", "Strong-crypto habilitado (ciphers seguros)", "medium",
                        "strong-crypto=disable — ciphers fracos podem ser negociados",
                        "config system global → set strong-crypto enable"))
            else:
                controls.append(_na("FGT-01", "Timeout de sessão admin ≤ 15 min", "high",
                    f"Sem acesso a system/global (HTTP {r.status_code})"))
        except Exception as exc:
            logger.warning("FGT-01..04 falhou: %s", exc)
            controls.append(_na("FGT-01", "Timeout de sessão admin ≤ 15 min", "high",
                "Erro ao coletar system/global"))

        # ── FGT-05: SNMP — sem communities padrão ────────────────────────────
        try:
            r = await client.get(f"/api/v2/cmdb/system/snmp/community?vdom={vdom}")
            if r.status_code == 200:
                communities = r.json().get("results", [])
                dangerous = [c.get("name", "") for c in communities
                             if c.get("name", "").lower() in ("public", "private", "")]
                if not communities:
                    controls.append(_pass("FGT-05", "SNMP sem communities padrão inseguras", "critical",
                        "Nenhuma community SNMP configurada"))
                elif dangerous:
                    controls.append(_fail("FGT-05", "SNMP sem communities padrão inseguras", "critical",
                        f"Communities inseguras detectadas: {dangerous}",
                        "Remova as communities 'public'/'private' e use uma string complexa única"))
                else:
                    controls.append(_pass("FGT-05", "SNMP sem communities padrão inseguras", "critical",
                        f"{len(communities)} communities, nenhuma é 'public' ou 'private'"))
            elif r.status_code == 404:
                controls.append(_na("FGT-05", "SNMP sem communities padrão inseguras", "critical",
                    "SNMP não configurado"))
            else:
                controls.append(_na("FGT-05", "SNMP sem communities padrão inseguras", "critical",
                    f"HTTP {r.status_code} — sem permissão para leitura de SNMP"))
        except Exception as exc:
            logger.warning("FGT-05 falhou: %s", exc)

        # ── FGT-06: NTP configurado ───────────────────────────────────────────
        try:
            r = await client.get(f"/api/v2/cmdb/system/ntp?vdom={vdom}")
            if r.status_code == 200:
                ntp = r.json().get("results", {})
                ntpd_enabled = ntp.get("ntpd-server", "disable") == "enable" or ntp.get("type") in ("custom", "fortiguard")
                servers = ntp.get("ntpserver", [])
                if ntpd_enabled or servers:
                    controls.append(_pass("FGT-06", "NTP configurado para sincronização de tempo", "medium",
                        f"Servidores NTP: {[s.get('server') for s in servers] or 'FortiGuard NTP'}"))
                else:
                    controls.append(_fail("FGT-06", "NTP configurado para sincronização de tempo", "medium",
                        "NTP não configurado — timestamps de log podem ser imprecisos",
                        "config system ntp → set ntpd-server enable → config ntpserver → set server <IP>"))
            else:
                controls.append(_na("FGT-06", "NTP configurado para sincronização de tempo", "medium",
                    f"HTTP {r.status_code}"))
        except Exception as exc:
            logger.warning("FGT-06 falhou: %s", exc)

        # ── FGT-07: Syslog para servidor remoto ───────────────────────────────
        try:
            r = await client.get(f"/api/v2/cmdb/log/syslogd/setting?vdom={vdom}")
            if r.status_code == 200:
                syslog = r.json().get("results", {})
                status = syslog.get("status", "disable")
                server = syslog.get("server", "")
                if status == "enable" and server:
                    controls.append(_pass("FGT-07", "Logs enviados para servidor syslog remoto", "high",
                        f"syslogd status=enable, server={server}"))
                else:
                    controls.append(_fail("FGT-07", "Logs enviados para servidor syslog remoto", "high",
                        f"syslogd status={status}, server='{server}' — logs não centralizados",
                        "Log & Report > Log Settings > Remote Logging: habilite Syslog e configure servidor"))
            else:
                controls.append(_na("FGT-07", "Logs enviados para servidor syslog remoto", "high",
                    f"HTTP {r.status_code}"))
        except Exception as exc:
            logger.warning("FGT-07 falhou: %s", exc)

        # ── FGT-08 + FGT-09: Análise de regras ───────────────────────────────
        try:
            r = await client.get(f"/api/v2/cmdb/firewall/policy?vdom={vdom}")
            if r.status_code == 200:
                policies = r.json().get("results", [])
                enabled = [p for p in policies if p.get("status", "enable") == "enable"]

                # Any→Any allow
                any_any = []
                for p in enabled:
                    srcaddr = [s.get("name", "") for s in p.get("srcaddr", [])]
                    dstaddr = [s.get("name", "") for s in p.get("dstaddr", [])]
                    service = [s.get("name", "") for s in p.get("service", [])]
                    action = p.get("action", "deny")
                    if (action == "accept" and
                            any(a.lower() in ("all", "any") for a in srcaddr) and
                            any(a.lower() in ("all", "any") for a in dstaddr) and
                            any(s.upper() in ("ALL", "ANY") for s in service)):
                        any_any.append(p.get("name", str(p.get("policyid", "?"))))

                if any_any:
                    controls.append(_fail("FGT-08", "Sem regras allow any→any sem restrição de serviço", "critical",
                        f"Regras any→any/ALL detectadas: {any_any[:5]}",
                        "Substitua regras any→any por regras específicas com origem, destino e serviço definidos"))
                else:
                    controls.append(_pass("FGT-08", "Sem regras allow any→any sem restrição de serviço", "critical",
                        f"{len(enabled)} regras ativas verificadas — nenhuma any→any/ALL encontrada"))

                # Regras sem logging
                no_log = [p.get("name", str(p.get("policyid", "?"))) for p in enabled
                          if p.get("logtraffic", "disable") in ("disable", "")]
                if no_log:
                    controls.append(_fail("FGT-09", "Todas as regras habilitadas com logging ativo", "high",
                        f"{len(no_log)} regras sem log: {no_log[:5]}{'...' if len(no_log) > 5 else ''}",
                        "Edite cada regra → Log Allowed Traffic: 'All Sessions' ou 'Security Events'"))
                else:
                    controls.append(_pass("FGT-09", "Todas as regras habilitadas com logging ativo", "high",
                        f"Todas as {len(enabled)} regras ativas têm logging habilitado"))
            else:
                controls.append(_na("FGT-08", "Sem regras allow any→any sem restrição de serviço", "critical",
                    f"HTTP {r.status_code}"))
        except Exception as exc:
            logger.warning("FGT-08/09 falhou: %s", exc)

        # ── FGT-10: Múltiplas contas admin (sem admin único) ──────────────────
        try:
            r = await client.get(f"/api/v2/cmdb/system/admin?vdom={vdom}&format=name,accprofile,two-factor")
            if r.status_code == 200:
                admins = r.json().get("results", [])
                # Filter to real admin-level accounts (not read-only)
                rw_admins = [a for a in admins if a.get("accprofile", "") not in ("", "no_access")]
                if len(rw_admins) >= 2:
                    names = [a.get("name", "?") for a in rw_admins]
                    # Check if anyone has 2FA
                    two_fa = [a.get("name") for a in rw_admins if a.get("two-factor", "disable") != "disable"]
                    if two_fa:
                        controls.append(_pass("FGT-10", "Múltiplas contas admin com 2FA habilitado", "high",
                            f"{len(rw_admins)} contas admin. Com 2FA: {two_fa}"))
                    else:
                        controls.append(_fail("FGT-10", "Múltiplas contas admin com 2FA habilitado", "high",
                            f"{len(rw_admins)} contas admin sem 2FA configurado: {names}",
                            "System > Administrators: habilite FortiToken ou email 2FA em cada conta admin"))
                elif len(rw_admins) == 1:
                    controls.append(_fail("FGT-10", "Múltiplas contas admin com 2FA habilitado", "high",
                        f"Apenas 1 conta admin ('{rw_admins[0].get('name', '?')}') — sem separação de privilégios",
                        "Crie contas individuais para cada administrador; evite conta admin genérica compartilhada"))
                else:
                    controls.append(_na("FGT-10", "Múltiplas contas admin com 2FA habilitado", "high",
                        "Não foi possível listar admins"))
            elif r.status_code in (401, 403):
                controls.append(_na("FGT-10", "Múltiplas contas admin com 2FA habilitado", "high",
                    "Token sem permissão para listar admins"))
        except Exception as exc:
            logger.warning("FGT-10 falhou: %s", exc)

        # ── FGT-11: Password policy habilitada ───────────────────────────────
        try:
            r = await client.get(f"/api/v2/cmdb/system/password-policy?vdom={vdom}")
            if r.status_code == 200:
                pp = r.json().get("results", {})
                status = pp.get("status", "disable")
                if status == "enable":
                    min_len = pp.get("min-length", 0)
                    controls.append(_pass("FGT-11", "Política de senha habilitada", "high",
                        f"password-policy status=enable, min-length={min_len}"))
                else:
                    controls.append(_fail("FGT-11", "Política de senha habilitada", "high",
                        "password-policy status=disable — senhas fracas permitidas",
                        "System > Settings > Password Policy: habilite e defina comprimento mínimo ≥ 12"))
            else:
                controls.append(_na("FGT-11", "Política de senha habilitada", "high",
                    f"HTTP {r.status_code}"))
        except Exception as exc:
            logger.warning("FGT-11 falhou: %s", exc)

    return controls


# ── Cisco IOS checks ──────────────────────────────────────────────────────────

async def _collect_cisco_ios(device: Device) -> list[dict]:
    """Collect compliance data via SSH show commands on Cisco IOS."""
    from app.connectors.factory import get_ssh_connector

    conn = get_ssh_connector(device)

    controls: list[dict] = []

    cmds = [
        "show running-config | include snmp-server community",
        "show running-config | include ip ssh version",
        "show running-config | include service password-encryption",
        "show running-config | include ntp server",
        "show running-config | include logging host",
        "show running-config | include enable secret",
        "show running-config | include aaa new-model",
        "show running-config | include banner login",
        "show running-config | include transport input",
        "show running-config | include no cdp run",
    ]

    try:
        result = await conn.execute_show_commands(cmds)
        raw = result.output
    except Exception as exc:
        logger.warning("Cisco IOS SSH collection failed: %s", exc)
        return [_na(f"CIS-{i:02d}", f"Check {i}", "medium", f"SSH collection failed: {exc}") for i in range(1, 11)]

    # Parse output — each command output is separated by prompts
    lines = raw.lower()

    # ── CIS-01: SNMP default communities ─────────────────────────────────────
    snmp_lines = [l for l in raw.splitlines() if "snmp-server community" in l.lower()]
    dangerous_snmp = [l for l in snmp_lines if re.search(r"\bpublic\b|\bprivate\b", l, re.I)]
    if not snmp_lines:
        controls.append(_pass("CIS-01", "SNMP sem communities padrão inseguras", "critical",
            "Nenhuma community SNMP configurada"))
    elif dangerous_snmp:
        controls.append(_fail("CIS-01", "SNMP sem communities padrão inseguras", "critical",
            f"Communities inseguras: {dangerous_snmp[:3]}",
            "no snmp-server community public; no snmp-server community private"))
    else:
        controls.append(_pass("CIS-01", "SNMP sem communities padrão inseguras", "critical",
            f"{len(snmp_lines)} community(ies) configuradas, nenhuma é 'public'/'private'"))

    # ── CIS-02: SSH v2 only ───────────────────────────────────────────────────
    ssh_ver = [l for l in raw.splitlines() if "ip ssh version" in l.lower()]
    if any("version 2" in l.lower() for l in ssh_ver):
        controls.append(_pass("CIS-02", "SSH versão 2 configurado", "high",
            "ip ssh version 2 encontrado"))
    elif ssh_ver:
        controls.append(_fail("CIS-02", "SSH versão 2 configurado", "high",
            f"SSH configurado com versão insegura: {ssh_ver}",
            "ip ssh version 2"))
    else:
        controls.append(_fail("CIS-02", "SSH versão 2 configurado", "high",
            "ip ssh version não encontrado na configuração",
            "ip ssh version 2"))

    # ── CIS-03: Service password-encryption ──────────────────────────────────
    if "service password-encryption" in lines:
        controls.append(_pass("CIS-03", "Criptografia de senhas habilitada (service password-encryption)", "high",
            "service password-encryption presente"))
    else:
        controls.append(_fail("CIS-03", "Criptografia de senhas habilitada (service password-encryption)", "high",
            "service password-encryption ausente — senhas em texto claro no running-config",
            "service password-encryption"))

    # ── CIS-04: NTP ───────────────────────────────────────────────────────────
    ntp_lines = [l for l in raw.splitlines() if "ntp server" in l.lower()]
    if ntp_lines:
        controls.append(_pass("CIS-04", "NTP configurado para sincronização de tempo", "medium",
            f"Servidores NTP: {ntp_lines[:3]}"))
    else:
        controls.append(_fail("CIS-04", "NTP configurado para sincronização de tempo", "medium",
            "Nenhum servidor NTP configurado",
            "ntp server <IP_DO_NTP_SERVER>"))

    # ── CIS-05: Syslog remoto ─────────────────────────────────────────────────
    log_lines = [l for l in raw.splitlines() if "logging host" in l.lower()]
    if log_lines:
        controls.append(_pass("CIS-05", "Syslog enviado para servidor remoto", "high",
            f"logging host: {log_lines[:2]}"))
    else:
        controls.append(_fail("CIS-05", "Syslog enviado para servidor remoto", "high",
            "Nenhum logging host configurado",
            "logging host <IP_DO_SYSLOG>"))

    # ── CIS-06: Enable secret ─────────────────────────────────────────────────
    if "enable secret" in lines:
        controls.append(_pass("CIS-06", "Enable secret configurado (não enable password)", "critical",
            "enable secret presente — senha em hash"))
    else:
        controls.append(_fail("CIS-06", "Enable secret configurado (não enable password)", "critical",
            "enable secret não encontrado — acesso privilegiado pode estar desprotegido",
            "enable secret <senha_forte>"))

    # ── CIS-07: AAA new-model ─────────────────────────────────────────────────
    if "aaa new-model" in lines:
        controls.append(_pass("CIS-07", "AAA habilitado (aaa new-model)", "high",
            "aaa new-model presente"))
    else:
        controls.append(_fail("CIS-07", "AAA habilitado (aaa new-model)", "high",
            "aaa new-model não encontrado — autenticação centralizada não configurada",
            "aaa new-model"))

    # ── CIS-08: Login banner ──────────────────────────────────────────────────
    if "banner login" in lines:
        controls.append(_pass("CIS-08", "Banner de aviso legal configurado", "low",
            "banner login presente"))
    else:
        controls.append(_fail("CIS-08", "Banner de aviso legal configurado", "low",
            "banner login não configurado — sem aviso legal antes do login",
            "banner login ^C\nAcesso restrito. Uso não autorizado sujeito a penalidades legais.\n^C"))

    # ── CIS-09: Sem telnet (só SSH) ───────────────────────────────────────────
    transport_lines = [l for l in raw.splitlines() if "transport input" in l.lower()]
    telnet_exposed = any(
        re.search(r"transport input.*(telnet|all)", l, re.I) and "no telnet" not in l.lower()
        for l in transport_lines
    )
    if telnet_exposed:
        controls.append(_fail("CIS-09", "Telnet desabilitado nas linhas VTY", "high",
            f"transport input com telnet detectado: {transport_lines[:3]}",
            "line vty 0 15\n  transport input ssh"))
    elif transport_lines:
        controls.append(_pass("CIS-09", "Telnet desabilitado nas linhas VTY", "high",
            f"transport input configurado: {transport_lines[:2]}"))
    else:
        controls.append(_na("CIS-09", "Telnet desabilitado nas linhas VTY", "high",
            "Configuração de transport input não encontrada"))

    # ── CIS-10: CDP desabilitado globalmente ──────────────────────────────────
    if "no cdp run" in lines:
        controls.append(_pass("CIS-10", "CDP desabilitado globalmente", "medium",
            "no cdp run presente"))
    else:
        controls.append(_fail("CIS-10", "CDP desabilitado globalmente", "medium",
            "CDP provavelmente habilitado — expõe informações de topologia",
            "no cdp run"))

    return controls


# ── HP Comware checks ─────────────────────────────────────────────────────────

async def _collect_hp_comware(device: Device) -> list[dict]:
    """Collect compliance data via SSH display commands on HP Comware."""
    from app.connectors.factory import get_ssh_connector

    conn = get_ssh_connector(device)
    controls: list[dict] = []

    cmds = [
        "display snmp-agent community",
        "display ssh server status",
        "display ntp-service status",
        "display info-center",
        "display user-interface vty 0 15",
        "display local-user",
        "display version",
    ]

    try:
        result = await conn.execute_show_commands(cmds)
        raw = result.output
    except Exception as exc:
        logger.warning("HP Comware SSH collection failed: %s", exc)
        return [_na(f"HPC-{i:02d}", f"Check {i}", "medium", f"SSH collection failed: {exc}") for i in range(1, 8)]

    lines_lower = raw.lower()

    # ── HPC-01: SNMP default communities ─────────────────────────────────────
    snmp_block = ""
    in_snmp = False
    for line in raw.splitlines():
        if "snmp-agent community" in line.lower() or "community name" in line.lower():
            in_snmp = True
        if in_snmp:
            snmp_block += line + "\n"
        if in_snmp and line.strip() == "":
            in_snmp = False

    dangerous_snmp = bool(re.search(r"\bpublic\b|\bprivate\b", snmp_block, re.I))
    if not snmp_block.strip():
        controls.append(_pass("HPC-01", "SNMP sem communities padrão inseguras", "critical",
            "Nenhuma community SNMP configurada ou output vazio"))
    elif dangerous_snmp:
        controls.append(_fail("HPC-01", "SNMP sem communities padrão inseguras", "critical",
            "Community 'public' ou 'private' detectada",
            "undo snmp-agent community public\nundo snmp-agent community private"))
    else:
        controls.append(_pass("HPC-01", "SNMP sem communities padrão inseguras", "critical",
            "Nenhuma community padrão insegura detectada"))

    # ── HPC-02: SSH v2 ────────────────────────────────────────────────────────
    ssh_status = re.search(r"ssh server (version|status|enable|version.*?2)", raw, re.I)
    if re.search(r"ssh version\s*2|sshd version\s*2|ssh2", lines_lower):
        controls.append(_pass("HPC-02", "SSH versão 2 habilitado", "high",
            "SSH v2 confirmado"))
    elif re.search(r"ssh.*enable|ssh.*running|ssh server.*enable", lines_lower):
        controls.append(_fail("HPC-02", "SSH versão 2 habilitado", "high",
            "SSH habilitado mas versão não confirmada como v2",
            "ssh server version 2"))
    else:
        controls.append(_fail("HPC-02", "SSH versão 2 habilitado", "high",
            "SSH não habilitado ou status não encontrado",
            "ssh server enable\nssh server version 2"))

    # ── HPC-03: NTP ───────────────────────────────────────────────────────────
    if re.search(r"ntp.*enable|ntp-service.*enable|clock source", lines_lower):
        controls.append(_pass("HPC-03", "NTP configurado para sincronização de tempo", "medium",
            "NTP habilitado"))
    else:
        controls.append(_fail("HPC-03", "NTP configurado para sincronização de tempo", "medium",
            "NTP não parece estar habilitado",
            "ntp-service unicast-server <IP_NTP>"))

    # ── HPC-04: Syslog ────────────────────────────────────────────────────────
    if re.search(r"info-center.*enable|loghost|syslog.*enable", lines_lower):
        controls.append(_pass("HPC-04", "Syslog habilitado (info-center)", "high",
            "info-center habilitado com loghost configurado"))
    else:
        controls.append(_fail("HPC-04", "Syslog habilitado (info-center)", "high",
            "info-center não habilitado ou loghost não configurado",
            "info-center enable\ninfo-center loghost <IP_SYSLOG>"))

    # ── HPC-05: Timeout de VTY ────────────────────────────────────────────────
    timeout_match = re.search(r"idle-timeout\s+(\d+)\s+(\d+)", raw, re.I)
    if timeout_match:
        minutes = int(timeout_match.group(1))
        if minutes <= 15:
            controls.append(_pass("HPC-05", "Timeout de VTY ≤ 15 min", "high",
                f"idle-timeout={minutes} min"))
        else:
            controls.append(_fail("HPC-05", "Timeout de VTY ≤ 15 min", "high",
                f"idle-timeout={minutes} min (deve ser ≤ 15)",
                "user-interface vty 0 4\n  idle-timeout 15 0"))
    else:
        controls.append(_fail("HPC-05", "Timeout de VTY ≤ 15 min", "high",
            "idle-timeout não configurado nas VTYs — sessões não expiram",
            "user-interface vty 0 4\n  idle-timeout 15 0"))

    # ── HPC-06: Complexidade de senha ─────────────────────────────────────────
    if re.search(r"password.*(complexity|minimum|policy)", lines_lower):
        controls.append(_pass("HPC-06", "Política de complexidade de senha configurada", "high",
            "Política de senha detectada"))
    else:
        controls.append(_fail("HPC-06", "Política de complexidade de senha configurada", "high",
            "Política de complexidade de senha não detectada",
            "password-control enable\npassword-control complexity check enable\npassword-control length 12"))

    # ── HPC-07: Telnet desabilitado ───────────────────────────────────────────
    if re.search(r"undo telnet server enable|telnet server.*disable", lines_lower):
        controls.append(_pass("HPC-07", "Servidor Telnet desabilitado", "high",
            "Telnet server desabilitado"))
    elif re.search(r"telnet server enable", lines_lower):
        controls.append(_fail("HPC-07", "Servidor Telnet desabilitado", "high",
            "Telnet server habilitado — acesso inseguro exposto",
            "undo telnet server enable"))
    else:
        controls.append(_na("HPC-07", "Servidor Telnet desabilitado", "high",
            "Status do Telnet server não determinado"))

    return controls


# ── SonicWall security services checks ───────────────────────────────────────

def _parse_sonicwall_gav(output: str) -> dict:
    """Parse 'show gateway-antivirus' output into a structured dict."""
    result: dict[str, Any] = {
        "enabled": False,
        "inbound": [],
        "outbound": [],
        "restrict_password_zip": [],
        "restrict_ms_macros": [],
        "restrict_packed_exec": [],
        "detection_only": False,
        "block_multiple_compress": False,
        "cloud_av": False,
        "eicar_detection": False,
        "scan_high_compression": False,
    }
    for raw_line in output.splitlines():
        line = raw_line.strip()
        negated = line.startswith("no ")
        cmd = line[3:] if negated else line

        if cmd == "enable":
            result["enabled"] = not negated
        elif cmd == "detection-only":
            result["detection_only"] = not negated
        elif cmd == "block-multiple-compress-files":
            result["block_multiple_compress"] = not negated
        elif cmd == "eicar-detection":
            result["eicar_detection"] = not negated
        elif cmd == "scan-high-compression":
            result["scan_high_compression"] = not negated
        elif cmd.startswith("cloud anti-virus-database"):
            result["cloud_av"] = not negated
        elif cmd.startswith("inbound-inspection "):
            proto = cmd.split()[-1]
            if not negated and proto not in result["inbound"]:
                result["inbound"].append(proto)
        elif cmd.startswith("outbound-inspection "):
            proto = cmd.split()[-1]
            if not negated and proto not in result["outbound"]:
                result["outbound"].append(proto)
        elif cmd.startswith("restrict password-protected-zip "):
            proto = cmd.split()[-1]
            if not negated and proto not in result["restrict_password_zip"]:
                result["restrict_password_zip"].append(proto)
        elif cmd.startswith("restrict ms-office-macros "):
            proto = cmd.split()[-1]
            if not negated and proto not in result["restrict_ms_macros"]:
                result["restrict_ms_macros"].append(proto)
        elif cmd.startswith("restrict packed-executables "):
            proto = cmd.split()[-1]
            if not negated and proto not in result["restrict_packed_exec"]:
                result["restrict_packed_exec"].append(proto)
    return result


def _parse_sonicwall_spyware(output: str) -> dict:
    """Parse 'show anti-spyware' output into a structured dict."""
    result: dict[str, Any] = {
        "enabled": False,
        "high_prevent": False,
        "medium_prevent": False,
        "low_prevent": False,
        "high_detect": False,
        "medium_detect": False,
        "low_detect": False,
        "inspection_inbound": [],
        "inspection_outbound": False,
    }
    for raw_line in output.splitlines():
        line = raw_line.strip()
        negated = line.startswith("no ")
        cmd = line[3:] if negated else line

        if cmd == "enable":
            result["enabled"] = not negated
        elif cmd == "signature-group high-danger prevent-all":
            result["high_prevent"] = not negated
        elif cmd == "signature-group medium-danger prevent-all":
            result["medium_prevent"] = not negated
        elif cmd == "signature-group low-danger prevent-all":
            result["low_prevent"] = not negated
        elif cmd == "signature-group high-danger detect-all":
            result["high_detect"] = not negated
        elif cmd == "signature-group medium-danger detect-all":
            result["medium_detect"] = not negated
        elif cmd == "signature-group low-danger detect-all":
            result["low_detect"] = not negated
        elif cmd == "inspection outbound":
            result["inspection_outbound"] = not negated
        elif cmd.startswith("inspection inbound "):
            proto = cmd.split()[-1]
            if not negated and proto not in result["inspection_inbound"]:
                result["inspection_inbound"].append(proto)
    return result


def _parse_sonicwall_ips(output: str) -> dict:
    """Parse 'show intrusion-prevention' output into a structured dict."""
    result: dict[str, Any] = {
        "enabled": False,
        "high_prevent": False,
        "medium_prevent": False,
        "low_prevent": False,
        "high_detect": False,
        "medium_detect": False,
        "low_detect": False,
    }
    for raw_line in output.splitlines():
        line = raw_line.strip()
        negated = line.startswith("no ")
        cmd = line[3:] if negated else line

        if cmd == "enable":
            result["enabled"] = not negated
        elif cmd == "signature-group high-priority prevent-all":
            result["high_prevent"] = not negated
        elif cmd == "signature-group medium-priority prevent-all":
            result["medium_prevent"] = not negated
        elif cmd == "signature-group low-priority prevent-all":
            result["low_prevent"] = not negated
        elif cmd == "signature-group high-priority detect-all":
            result["high_detect"] = not negated
        elif cmd == "signature-group medium-priority detect-all":
            result["medium_detect"] = not negated
        elif cmd == "signature-group low-priority detect-all":
            result["low_detect"] = not negated
    return result


async def _collect_sonicwall(device: Device) -> list[dict]:
    """Collect compliance data for SonicWall via SSH configure-mode show commands.

    Covers 15 controls across Gateway AV (8), Anti-Spyware (4) and IPS (3).
    Falls back to generic SSH checks on connection failure.
    """
    from app.connectors.sonicwall_ssh import SonicWallSSHConnector
    from app.utils.crypto import decrypt_credentials

    creds = decrypt_credentials(device.encrypted_credentials)
    ssh_creds = creds.get("ssh", {}) or creds
    host = device.host.replace("https://", "").replace("http://", "").split("/")[0]
    username = ssh_creds.get("username") or creds.get("username", "admin")
    password = ssh_creds.get("password") or creds.get("password", "")
    ssh_port = int(ssh_creds.get("ssh_port") or creds.get("ssh_port") or 22)

    connector = SonicWallSSHConnector(
        host=host,
        username=username,
        password=password,
        ssh_port=ssh_port,
    )

    controls: list[dict] = []

    try:
        raw = await connector.collect_security_services()
    except Exception as exc:
        logger.warning("SonicWall security services collection failed: %s", exc)
        return [_na(f"SW-GAV-0{i}", f"SonicWall GAV check {i}", "high",
                    f"Coleta SSH falhou: {exc}") for i in range(1, 9)] + \
               [_na(f"SW-SPY-0{i}", f"SonicWall Anti-Spyware check {i}", "high",
                    f"Coleta SSH falhou: {exc}") for i in range(1, 5)] + \
               [_na(f"SW-IPS-0{i}", f"SonicWall IPS check {i}", "high",
                    f"Coleta SSH falhou: {exc}") for i in range(1, 4)]

    gav = _parse_sonicwall_gav(raw.get("gateway_antivirus", ""))
    spy = _parse_sonicwall_spyware(raw.get("anti_spyware", ""))
    ips = _parse_sonicwall_ips(raw.get("intrusion_prevention", ""))

    # ── Gateway Anti-Virus checks ────────────────────────────────────────────

    # SW-GAV-01: GAV enabled
    if gav["enabled"]:
        controls.append(_pass("SW-GAV-01", "Gateway Anti-Virus habilitado", "critical",
            "enable encontrado — serviço GAV ativo"))
    else:
        controls.append(_fail("SW-GAV-01", "Gateway Anti-Virus habilitado", "critical",
            "GAV desabilitado — malwares em tráfego de rede não são inspecionados",
            "configure → gateway-antivirus → enable → commit"))

    # SW-GAV-02: HTTP inbound inspection
    if "http" in gav["inbound"]:
        controls.append(_pass("SW-GAV-02", "Inspeção HTTP inbound habilitada (GAV)", "high",
            f"inbound-inspection http ativo. Todos os protocolos inbound: {gav['inbound']}"))
    else:
        controls.append(_fail("SW-GAV-02", "Inspeção HTTP inbound habilitada (GAV)", "high",
            f"inbound-inspection http ausente. Protocolos ativos: {gav['inbound'] or 'nenhum'}",
            "gateway-antivirus → inbound-inspection http → commit"))

    # SW-GAV-03: SMTP inbound inspection
    if "smtp" in gav["inbound"]:
        controls.append(_pass("SW-GAV-03", "Inspeção SMTP inbound habilitada (GAV)", "high",
            "inbound-inspection smtp ativo — e-mails com malware são bloqueados"))
    else:
        controls.append(_fail("SW-GAV-03", "Inspeção SMTP inbound habilitada (GAV)", "high",
            "inbound-inspection smtp ausente — anexos maliciosos em e-mail não inspecionados",
            "gateway-antivirus → inbound-inspection smtp → commit"))

    # SW-GAV-04: Outbound inspection
    if gav["outbound"]:
        controls.append(_pass("SW-GAV-04", "Inspeção outbound habilitada (GAV)", "medium",
            f"Protocolos outbound inspecionados: {gav['outbound']}"))
    else:
        controls.append(_fail("SW-GAV-04", "Inspeção outbound habilitada (GAV)", "medium",
            "Nenhum protocolo outbound inspecionado — exfiltração de malware não detectada",
            "gateway-antivirus → outbound-inspection http → outbound-inspection smtp → commit"))

    # SW-GAV-05: Detection-only mode disabled (should be blocking)
    if not gav["detection_only"]:
        controls.append(_pass("SW-GAV-05", "Modo detection-only desabilitado (GAV bloqueia)", "high",
            "detection-only desabilitado — GAV está em modo de bloqueio ativo"))
    else:
        controls.append(_fail("SW-GAV-05", "Modo detection-only desabilitado (GAV bloqueia)", "high",
            "detection-only ativo — GAV apenas loga, NÃO bloqueia ameaças",
            "gateway-antivirus → no detection-only → commit"))

    # SW-GAV-06: MS Office macros blocked
    if gav["restrict_ms_macros"]:
        controls.append(_pass("SW-GAV-06", "Bloqueio de macros MS Office habilitado (GAV)", "high",
            f"restrict ms-office-macros ativo em: {gav['restrict_ms_macros']}"))
    else:
        controls.append(_fail("SW-GAV-06", "Bloqueio de macros MS Office habilitado (GAV)", "high",
            "Macros MS Office não bloqueadas — vetor comum de ransomware e malware",
            "gateway-antivirus → restrict ms-office-macros http → restrict ms-office-macros smtp → commit"))

    # SW-GAV-07: Password-protected ZIP blocked
    if gav["restrict_password_zip"]:
        controls.append(_pass("SW-GAV-07", "Bloqueio de ZIP com senha habilitado (GAV)", "medium",
            f"restrict password-protected-zip ativo em: {gav['restrict_password_zip']}"))
    else:
        controls.append(_fail("SW-GAV-07", "Bloqueio de ZIP com senha habilitado (GAV)", "medium",
            "ZIPs com senha não bloqueados — GAV não consegue inspecionar conteúdo cifrado",
            "gateway-antivirus → restrict password-protected-zip smtp → restrict password-protected-zip http → commit"))

    # SW-GAV-08: Cloud AV database
    if gav["cloud_av"]:
        controls.append(_pass("SW-GAV-08", "Cloud Anti-Virus database habilitado", "medium",
            "cloud anti-virus-database ativo — assinaturas em nuvem complementam a base local"))
    else:
        controls.append(_fail("SW-GAV-08", "Cloud Anti-Virus database habilitado", "medium",
            "Cloud AV desabilitado — detecção limitada à base local de assinaturas",
            "gateway-antivirus → cloud anti-virus-database → commit"))

    # ── Anti-Spyware checks ──────────────────────────────────────────────────

    # SW-SPY-01: Anti-Spyware enabled
    if spy["enabled"]:
        controls.append(_pass("SW-SPY-01", "Anti-Spyware habilitado", "critical",
            "enable encontrado — serviço Anti-Spyware ativo"))
    else:
        controls.append(_fail("SW-SPY-01", "Anti-Spyware habilitado", "critical",
            "Anti-Spyware desabilitado — spyware e C2 callbacks não são detectados",
            "configure → anti-spyware → enable → commit"))

    # SW-SPY-02: High-danger prevention
    if spy["high_prevent"]:
        controls.append(_pass("SW-SPY-02", "Prevenção de ameaças HIGH-DANGER ativa (Anti-Spyware)", "critical",
            "signature-group high-danger prevent-all ativo — ameaças críticas bloqueadas"))
    else:
        controls.append(_fail("SW-SPY-02", "Prevenção de ameaças HIGH-DANGER ativa (Anti-Spyware)", "critical",
            "signature-group high-danger prevent-all ausente — ameaças de alto risco apenas logadas, não bloqueadas",
            "anti-spyware → signature-group high-danger prevent-all → commit"))

    # SW-SPY-03: Medium-danger prevention
    if spy["medium_prevent"]:
        controls.append(_pass("SW-SPY-03", "Prevenção de ameaças MEDIUM-DANGER ativa (Anti-Spyware)", "high",
            "signature-group medium-danger prevent-all ativo"))
    else:
        controls.append(_fail("SW-SPY-03", "Prevenção de ameaças MEDIUM-DANGER ativa (Anti-Spyware)", "high",
            "signature-group medium-danger prevent-all ausente — ameaças de médio risco não bloqueadas",
            "anti-spyware → signature-group medium-danger prevent-all → commit"))

    # SW-SPY-04: Outbound spyware inspection
    if spy["inspection_outbound"]:
        controls.append(_pass("SW-SPY-04", "Inspeção outbound Anti-Spyware habilitada", "medium",
            "inspection outbound ativo — callbacks de spyware saindo da rede são detectados"))
    else:
        controls.append(_fail("SW-SPY-04", "Inspeção outbound Anti-Spyware habilitada", "medium",
            "inspection outbound desabilitado — spyware infectado internamente pode comunicar com C2 sem detecção",
            "anti-spyware → inspection outbound → commit"))

    # ── Intrusion Prevention checks ──────────────────────────────────────────

    # SW-IPS-01: IPS enabled
    if ips["enabled"]:
        controls.append(_pass("SW-IPS-01", "Intrusion Prevention (IPS) habilitado", "critical",
            "enable encontrado — serviço IPS ativo"))
    else:
        controls.append(_fail("SW-IPS-01", "Intrusion Prevention (IPS) habilitado", "critical",
            "IPS desabilitado — exploits e ataques de rede não são detectados ou bloqueados",
            "configure → intrusion-prevention → enable → commit"))

    # SW-IPS-02: High-priority prevention
    if ips["high_prevent"]:
        controls.append(_pass("SW-IPS-02", "Prevenção IPS HIGH-PRIORITY ativa", "critical",
            "signature-group high-priority prevent-all ativo — exploits críticos bloqueados"))
    else:
        controls.append(_fail("SW-IPS-02", "Prevenção IPS HIGH-PRIORITY ativa", "critical",
            "signature-group high-priority prevent-all ausente — ataques de alta prioridade apenas logados",
            "intrusion-prevention → signature-group high-priority prevent-all → commit"))

    # SW-IPS-03: Medium-priority prevention
    if ips["medium_prevent"]:
        controls.append(_pass("SW-IPS-03", "Prevenção IPS MEDIUM-PRIORITY ativa", "high",
            "signature-group medium-priority prevent-all ativo"))
    else:
        controls.append(_fail("SW-IPS-03", "Prevenção IPS MEDIUM-PRIORITY ativa", "high",
            "signature-group medium-priority prevent-all ausente — ataques de média prioridade não bloqueados",
            "intrusion-prevention → signature-group medium-priority prevent-all → commit"))

    return controls


# ── Generic SSH fallback ──────────────────────────────────────────────────────

async def _collect_dell_n(device: Device) -> list[dict]:
    """Collect compliance data via SSH show commands on Dell N-Series (DNOS6)."""
    from app.connectors.factory import get_ssh_connector

    conn = get_ssh_connector(device)
    controls: list[dict] = []

    try:
        result = await conn.execute_show_commands(["show running-config"])
        raw = result.output
    except Exception as exc:
        logger.warning("Dell N SSH collection failed: %s", exc)
        return [_na(f"DN-{i:02d}", f"Check {i}", "medium", f"SSH collection failed: {exc}") for i in range(1, 7)]

    lines_lower = raw.lower()

    # ── DN-01: SNMP default communities ───────────────────────────────────────
    snmp_lines = [l for l in raw.splitlines() if "snmp-server community" in l.lower()]
    dangerous_snmp = [l for l in snmp_lines if re.search(r"\bpublic\b|\bprivate\b", l, re.I)]
    if not snmp_lines:
        controls.append(_pass("DN-01", "SNMP sem communities padrão inseguras", "critical",
            "Nenhuma community SNMP configurada"))
    elif dangerous_snmp:
        controls.append(_fail("DN-01", "SNMP sem communities padrão inseguras", "critical",
            f"Communities inseguras detectadas: {dangerous_snmp[:3]}",
            "no snmp-server community public\nno snmp-server community private"))
    else:
        controls.append(_pass("DN-01", "SNMP sem communities padrão inseguras", "critical",
            f"{len(snmp_lines)} community(ies) configuradas, nenhuma é 'public'/'private'"))

    # ── DN-02: SSH v2 ─────────────────────────────────────────────────────────
    if re.search(r"ip ssh version 2", lines_lower):
        controls.append(_pass("DN-02", "SSH versão 2 configurado", "high", "ip ssh version 2 encontrado"))
    elif re.search(r"ip ssh", lines_lower):
        controls.append(_fail("DN-02", "SSH versão 2 configurado", "high",
            "SSH habilitado mas versão 2 não forçada",
            "ip ssh version 2"))
    else:
        controls.append(_fail("DN-02", "SSH versão 2 configurado", "high",
            "SSH não configurado",
            "crypto key generate rsa\nip ssh version 2"))

    # ── DN-03: NTP/SNTP configurado ───────────────────────────────────────────
    if re.search(r"sntp server|ntp server", lines_lower):
        controls.append(_pass("DN-03", "NTP/SNTP configurado para sincronização de tempo", "medium",
            "Servidor NTP/SNTP encontrado na configuração"))
    else:
        controls.append(_fail("DN-03", "NTP/SNTP configurado para sincronização de tempo", "medium",
            "Nenhum servidor NTP/SNTP configurado",
            "sntp server <IP_NTP>"))

    # ── DN-04: Syslog remoto configurado ─────────────────────────────────────
    syslog_match = re.search(r"^logging \d", raw, re.MULTILINE) or re.search(r"logging server|logging host", lines_lower)
    if syslog_match:
        controls.append(_pass("DN-04", "Syslog enviado para servidor remoto", "high",
            "Destino de logging remoto detectado"))
    else:
        controls.append(_fail("DN-04", "Syslog enviado para servidor remoto", "high",
            "Nenhum destino syslog remoto configurado",
            "logging <IP_SYSLOG>"))

    # ── DN-05: Telnet desabilitado nas VTYs ──────────────────────────────────
    vty_ssh_only = re.search(r"transport input ssh", lines_lower)
    telnet_on    = re.search(r"transport input.*(telnet|all)\b", lines_lower)
    if vty_ssh_only and not telnet_on:
        controls.append(_pass("DN-05", "Telnet desabilitado nas linhas VTY", "high",
            "transport input ssh configurado"))
    elif telnet_on:
        controls.append(_fail("DN-05", "Telnet desabilitado nas linhas VTY", "high",
            "Telnet habilitado nas VTYs — acesso inseguro exposto",
            "line vty\n  transport input ssh"))
    else:
        controls.append(_na("DN-05", "Telnet desabilitado nas linhas VTY", "high",
            "Configuração de transport input não detectada"))

    # ── DN-06: Senha de enable criptografada ─────────────────────────────────
    if re.search(r"enable password 7\b|enable secret", lines_lower):
        controls.append(_pass("DN-06", "Senha de enable criptografada", "critical",
            "Senha de enable armazenada de forma cifrada"))
    elif re.search(r"enable password 0\b|enable password [^7\n]", lines_lower):
        controls.append(_fail("DN-06", "Senha de enable criptografada", "critical",
            "Senha de enable em texto claro detectada",
            "enable password encrypted <hash>"))
    else:
        controls.append(_na("DN-06", "Senha de enable criptografada", "critical",
            "Configuração de enable não detectada no running-config"))

    return controls


async def _collect_generic_ssh(device: Device) -> list[dict]:
    """Generic SSH-based compliance for Juniper, Aruba, other vendors."""
    from app.connectors.factory import get_ssh_connector

    conn = get_ssh_connector(device)
    controls: list[dict] = []

    try:
        result = await conn.execute_show_commands(["show configuration | display set"])
        raw = result.output
    except Exception:
        try:
            result = await conn.execute_show_commands(["show running-config"])
            raw = result.output
        except Exception as exc:
            return [_na("GEN-01", "Coleta de configuração", "medium", f"SSH collection failed: {exc}")]

    lines_lower = raw.lower()

    snmp_community_public = bool(re.search(r"community\s+(public|private)", lines_lower))
    if snmp_community_public:
        controls.append(_fail("GEN-01", "SNMP sem communities padrão inseguras", "critical",
            "Community 'public' ou 'private' detectada na configuração",
            "Remova as communities SNMP padrão e configure uma string única"))
    else:
        controls.append(_pass("GEN-01", "SNMP sem communities padrão inseguras", "critical",
            "Nenhuma community padrão (public/private) detectada"))

    if re.search(r"ntp.*(server|peer)|set system ntp", lines_lower):
        controls.append(_pass("GEN-02", "NTP configurado", "medium", "Configuração NTP detectada"))
    else:
        controls.append(_fail("GEN-02", "NTP configurado", "medium",
            "Configuração NTP não detectada", "Configure sincronização NTP com servidor interno"))

    if re.search(r"syslog.*(host|server)|logging.*(host|server)", lines_lower):
        controls.append(_pass("GEN-03", "Syslog remoto configurado", "high", "Destino syslog remoto detectado"))
    else:
        controls.append(_fail("GEN-03", "Syslog remoto configurado", "high",
            "Destino syslog remoto não detectado", "Configure envio de logs para servidor SIEM/syslog"))

    return controls


# ── Routing function ──────────────────────────────────────────────────────────

async def collect_device_compliance(device: Device) -> tuple[str, list[dict]]:
    """Route to the correct collector based on device vendor. Returns (policy_name, controls)."""
    vendor = device.vendor

    if vendor == VendorEnum.fortinet:
        controls = await _collect_fortinet(device)
        policy_name = "CIS FortiGate Benchmark"
        return policy_name, controls

    elif vendor in (VendorEnum.cisco_ios, VendorEnum.cisco_nxos):
        controls = await _collect_cisco_ios(device)
        policy_name = "CIS Cisco IOS Benchmark"
        return policy_name, controls

    elif vendor == VendorEnum.hp_comware:
        controls = await _collect_hp_comware(device)
        policy_name = "CIS HP Comware Benchmark"
        return policy_name, controls

    elif vendor == VendorEnum.dell_n:
        controls = await _collect_dell_n(device)
        policy_name = "CIS Dell N-Series Benchmark"
        return policy_name, controls

    elif vendor in (VendorEnum.sonicwall,):
        controls = await _collect_sonicwall(device)
        policy_name = "SonicWall Security Services Compliance"
        return policy_name, controls

    else:
        # Juniper, Aruba, Dell, Ubiquiti — generic SSH
        controls = await _collect_generic_ssh(device)
        policy_name = f"Network Device Compliance ({vendor.value})"
        return policy_name, controls


# ── AI enrichment ─────────────────────────────────────────────────────────────

async def enrich_with_ai(device: Device, controls: list[dict]) -> dict:
    """Generate AI summary and prioritized recommendations for network device compliance."""
    try:
        import anthropic
        import os

        failed_controls = [c for c in controls if c.get("result") == "failed"]
        critical_high = [c for c in failed_controls if c.get("risk_level") in ("critical", "high")]

        controls_text = "\n".join(
            f"[{c['result'].upper()}] {c['control_id']} ({c['risk_level']}) — {c['title']}: {c['evidence']}"
            for c in controls
            if c.get("result") in ("passed", "failed")
        )

        prompt = f"""Você é um especialista em segurança de redes. Analise os resultados de conformidade do dispositivo de rede abaixo e produza:

Dispositivo: {device.name} ({device.vendor.value}) — {device.host}

Resultados dos checks:
{controls_text}

Produza EXATAMENTE o seguinte JSON (sem markdown, sem texto extra):
{{
  "ai_summary": "Resumo executivo em 3-4 frases descrevendo a postura de segurança do dispositivo, os principais riscos e prioridades.",
  "ai_recommendations": [
    {{
      "priority": 1,
      "title": "Título da recomendação",
      "description": "Descrição do risco e impacto",
      "remediation_steps": "Comandos CLI ou passos de configuração exatos"
    }}
  ]
}}

Inclua no máximo 5 recomendações, priorizando por risco (critical > high > medium > low).
Foque apenas nos controles que FALHARAM. Se todos passaram, diga isso no resumo e retorne recomendações vazias."""

        client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        import json
        text = msg.content[0].text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)

        data = json.loads(text)
        return {
            "ai_summary": data.get("ai_summary", ""),
            "ai_recommendations": data.get("ai_recommendations", []),
        }

    except Exception as exc:
        logger.warning("AI enrichment failed for network compliance: %s", exc)
        return {"ai_summary": "", "ai_recommendations": []}


# ── Main entry point ──────────────────────────────────────────────────────────

async def generate_report(
    db: AsyncSession,
    tenant_id: UUID,
    device_id: UUID,
) -> ComplianceReport:
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.tenant_id == tenant_id)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise ValueError("Dispositivo não encontrado")

    policy_name, controls = await collect_device_compliance(device)
    ai_data = await enrich_with_ai(device, controls)

    passed = sum(1 for c in controls if c.get("result") == "passed")
    failed_cnt = sum(1 for c in controls if c.get("result") == "failed")
    na = sum(1 for c in controls if c.get("result") == "not_applicable")
    total = passed + failed_cnt + na
    score = round(passed / (passed + failed_cnt) * 100, 1) if (passed + failed_cnt) > 0 else 0.0

    report = ComplianceReport(
        tenant_id=tenant_id,
        server_id=None,
        device_id=device_id,
        device_type=device.category.value,  # "firewall" | "switch" | "routing"
        source="rest" if device.vendor == VendorEnum.fortinet else "ssh",
        agent_id=None,
        policy_id=None,
        policy_name=policy_name,
        score_pct=score,
        total_checks=total,
        passed=passed,
        failed=failed_cnt,
        not_applicable=na,
        controls=controls,
        ai_summary=ai_data.get("ai_summary", ""),
        ai_recommendations=ai_data.get("ai_recommendations", []),
        framework="cis_benchmark",
    )

    db.add(report)
    await db.flush()
    await db.refresh(report)
    return report


async def list_reports(
    db: AsyncSession,
    tenant_id: UUID,
    device_type: str | None = None,
) -> list[ComplianceReport]:
    from sqlalchemy import and_

    filters = [
        ComplianceReport.tenant_id == tenant_id,
        ComplianceReport.device_id.isnot(None),
    ]
    if device_type:
        filters.append(ComplianceReport.device_type == device_type)

    result = await db.execute(
        select(ComplianceReport)
        .where(and_(*filters))
        .order_by(ComplianceReport.created_at.desc())
    )
    return list(result.scalars().all())
