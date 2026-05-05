"""CIS Benchmark → NIST CSF 2.0 and ISO 27001:2022 control crosswalk.

Methodology:
- CIS Benchmark Linux/Windows L1 section numbers align to CIS Controls v8 categories
- CIS Controls v8 has an official mapping to NIST CSF functions and ISO 27001 Annex A
  Reference: CIS Controls v8 Navigator (cisecurity.org/controls/cis-controls-navigator)
- For controls with numeric-only IDs (Wazuh SCA), classification falls back to keyword matching
  on the control title, since Wazuh SCA titles are CIS-aligned
- Risk weighting: critical=4, high=3, medium=2, low=1 — critical failures hurt the score more

NIST CSF functions:
  identify — Asset management, risk assessment (ID)
  protect  — Access control, data security, configuration (PR)
  detect   — Monitoring, anomaly detection (DE)
  respond  — Incident response, mitigation (RS)
  recover  — Recovery planning, maintenance (RC)

ISO 27001:2022 Annex A domains covered:
  A.5_access_auth  — A.5.15/16/17 Access Control, Identity, Authentication
  A.8_crypto       — A.8.10/24 Cryptography (replaces old A.10)
  A.8_logging      — A.8.15/16 Logging and Monitoring Activities
  A.8_network      — A.8.20/22 Network Security and Segregation
  A.8_vuln         — A.8.8 Management of Technical Vulnerabilities
  A.8_config       — A.8.9 Configuration Management
  A.8_assets       — A.8.3 Information Handling / Asset Management
"""
from __future__ import annotations

from collections import defaultdict
from typing import Literal

NistFunction = Literal["identify", "protect", "detect", "respond", "recover"]
IsoDomain = Literal[
    "A.5_access_auth",
    "A.8_crypto",
    "A.8_logging",
    "A.8_network",
    "A.8_vuln",
    "A.8_config",
    "A.8_assets",
]

ALL_NIST_FUNCTIONS: list[NistFunction] = [
    "identify", "protect", "detect", "respond", "recover",
]
ALL_ISO_DOMAINS: list[IsoDomain] = [
    "A.5_access_auth", "A.8_crypto", "A.8_logging",
    "A.8_network", "A.8_vuln", "A.8_config", "A.8_assets",
]

NIST_LABELS: dict[str, str] = {
    "identify": "Identificar (ID)",
    "protect":  "Proteger (PR)",
    "detect":   "Detectar (DE)",
    "respond":  "Responder (RS)",
    "recover":  "Recuperar (RC)",
}

ISO_LABELS: dict[str, str] = {
    "A.5_access_auth": "A.5 Controle de Acesso e Autenticação",
    "A.8_crypto":      "A.8.10/24 Criptografia",
    "A.8_logging":     "A.8.15/16 Logging e Monitoramento",
    "A.8_network":     "A.8.20/22 Segurança de Rede",
    "A.8_vuln":        "A.8.8 Gestão de Vulnerabilidades",
    "A.8_config":      "A.8.9 Gestão de Configuração",
    "A.8_assets":      "A.8.3 Gestão de Ativos",
}

# ── Section-based mapping (CIS Benchmark Linux/Windows section numbers) ──────

# CIS Benchmark Linux L1 sections align to CIS Controls v8:
#   1 (Filesystem init)  → CIS Control 3 (Data Protection)      → protect
#   2 (Services)         → CIS Control 4 (Secure Config)         → protect
#   3 (Network params)   → CIS Control 12 (Network Infra)        → protect
#   4 (Logging/Auditing) → CIS Control 8 (Audit Log Management)  → detect
#   5 (Auth/Access)      → CIS Control 5/6 (Account/Access Mgmt) → protect (PR.AC)
#   6 (Maintenance)      → CIS Control 7 (Vuln Management)       → recover
# Windows 18.x/19.x are equivalent config/access sections

_SECTION_NIST: dict[str, NistFunction] = {
    "1": "protect",
    "2": "protect",
    "3": "protect",
    "4": "detect",
    "5": "protect",
    "6": "recover",
    "9": "protect",
    "17": "detect",
    "18": "protect",
    "19": "protect",
}

_SECTION_ISO: dict[str, IsoDomain] = {
    "1": "A.8_config",
    "2": "A.8_vuln",
    "3": "A.8_network",
    "4": "A.8_logging",
    "5": "A.5_access_auth",
    "6": "A.8_config",
    "9": "A.8_config",
    "17": "A.8_logging",
    "18": "A.8_config",
    "19": "A.8_assets",
}

# ── Keyword fallbacks (Wazuh numeric IDs and unrecognised sections) ──────────

_KW_NIST: list[tuple[list[str], NistFunction]] = [
    (
        ["auditd", "audit log", "logging", "syslog", "event log",
         "journald", "log file", "log rotation", "log size"],
        "detect",
    ),
    (
        ["patch", "update", "upgrade", "version", "maintenance",
         "backup", "restore", "recovery"],
        "recover",
    ),
    (
        ["inventory", "authorized software", "authorized device",
         "asset", "discovery", "catalog"],
        "identify",
    ),
    (
        ["incident", "response", "notify", "alert escalat", "containment"],
        "respond",
    ),
    # default → protect (no entry needed, handled in classifier)
]

_KW_ISO: list[tuple[list[str], IsoDomain]] = [
    (
        ["ssh key", "pubkey", "permit root", "protocol 2", "cipher",
         "tls", "ssl", "encrypt", "kex ", "hostkey", " mac ",
         "bitlocker", "efs", "ntlm", "wdigest", "credential guard",
         "lsass", "schannel", "cryptograph"],
        "A.8_crypto",
    ),
    (
        ["audit log", "auditd", "syslog", "event log", "monitor",
         "journald", "log rotation", "log size", "powershell logging"],
        "A.8_logging",
    ),
    (
        ["network", "firewall", "iptables", "ufw", "port", "interface",
         "routing", "redirect", "ip forward", "icmp", "tcp syn"],
        "A.8_network",
    ),
    (
        ["password", "account", "user ", "sudo", "auth", "login",
         "privilege", "shell", "pam", "shadow", "expire", "rdp", "nla",
         "guest account", "local admin", "autologon"],
        "A.5_access_auth",
    ),
    (
        ["patch", "update", "upgrade", "vuln", "cve", "package version",
         "obsolete", "windows update", "defender", "antivirus"],
        "A.8_vuln",
    ),
    (
        ["service", "daemon", "running service", "process", "installed",
         "software", "smb", "telnet", "ftp", "snmp", "open port"],
        "A.8_assets",
    ),
    # default → A.8_config
]

_RISK_WEIGHT: dict[str, int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


# ── Classifiers ───────────────────────────────────────────────────────────────

def _classify_nist(control_id: str, title: str) -> NistFunction:
    title_lower = title.lower()

    # Section-based: "1.1.1", "4.2.3", "18.9.1"
    if control_id and "." in control_id:
        section = control_id.split(".")[0]
        if section in _SECTION_NIST:
            return _SECTION_NIST[section]

    # Keyword fallback (Wazuh numeric IDs or unrecognised sections)
    for keywords, func in _KW_NIST:
        if any(kw in title_lower for kw in keywords):
            return func

    return "protect"


def _classify_iso(control_id: str, title: str) -> IsoDomain:
    title_lower = title.lower()

    # Keyword matching takes priority (crypto keywords override section)
    for keywords, domain in _KW_ISO:
        if any(kw in title_lower for kw in keywords):
            return domain

    # Section-based fallback
    if control_id and "." in control_id:
        section = control_id.split(".")[0]
        if section in _SECTION_ISO:
            return _SECTION_ISO[section]

    return "A.8_config"


# ── Scoring functions ─────────────────────────────────────────────────────────

def score_by_nist(controls: list[dict]) -> dict[str, float | None]:
    """
    Return per-NIST-function pass rates from a list of CIS compliance controls.
    None means no applicable controls were found for that function — not the same as 0%.

    Control dict expected keys:
      control_id : str   e.g. "1.1.1" or "23500" (Wazuh)
      title      : str
      result     : "passed" | "failed" | "not_applicable"
      risk_level : "critical" | "high" | "medium" | "low"
    """
    passed_w: dict[str, float] = defaultdict(float)
    total_w: dict[str, float] = defaultdict(float)

    for ctrl in controls:
        result = ctrl.get("result", "not_applicable")
        if result == "not_applicable":
            continue
        func = _classify_nist(
            str(ctrl.get("control_id", "")),
            str(ctrl.get("title", "")),
        )
        w = _RISK_WEIGHT.get(str(ctrl.get("risk_level", "low")), 1)
        total_w[func] += w
        if result == "passed":
            passed_w[func] += w

    return {
        f: (round(passed_w[f] / total_w[f] * 100, 1) if total_w[f] > 0 else None)
        for f in ALL_NIST_FUNCTIONS
    }


def score_by_iso(controls: list[dict]) -> dict[str, float | None]:
    """
    Return per-ISO-domain pass rates from a list of CIS compliance controls.
    None means no applicable controls were found for that domain.
    """
    passed_w: dict[str, float] = defaultdict(float)
    total_w: dict[str, float] = defaultdict(float)

    for ctrl in controls:
        result = ctrl.get("result", "not_applicable")
        if result == "not_applicable":
            continue
        domain = _classify_iso(
            str(ctrl.get("control_id", "")),
            str(ctrl.get("title", "")),
        )
        w = _RISK_WEIGHT.get(str(ctrl.get("risk_level", "low")), 1)
        total_w[domain] += w
        if result == "passed":
            passed_w[domain] += w

    return {
        d: (round(passed_w[d] / total_w[d] * 100, 1) if total_w[d] > 0 else None)
        for d in ALL_ISO_DOMAINS
    }


def aggregate_score(scores: dict[str, float | None]) -> float | None:
    """Mean of non-None scores. Returns None only when all values are None (no data at all)."""
    valid = [v for v in scores.values() if v is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 1)
