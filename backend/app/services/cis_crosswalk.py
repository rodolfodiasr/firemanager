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

# ── Network device control ID → NIST / ISO mappings ──────────────────────────
# Covers FGT-* (Fortinet), CIS-* (Cisco IOS), HPC-* (HP Comware), GEN-* (generic SSH).
# Controls with "detect" meaning (syslog, logging): detect.
# NTP (time sync / asset identity): identify.
# All others: protect.

_NETWORK_CTRL_NIST: dict[str, NistFunction] = {
    # Fortinet
    "FGT-01": "protect",   # Admin idle timeout
    "FGT-02": "protect",   # HTTPS redirect (no HTTP mgmt)
    "FGT-03": "protect",   # TLS 1.2+ only
    "FGT-04": "protect",   # Strong crypto enabled
    "FGT-05": "protect",   # SNMP default communities removed
    "FGT-06": "identify",  # NTP configured
    "FGT-07": "detect",    # Syslog to remote server
    "FGT-08": "protect",   # No any→any allow rules
    "FGT-09": "detect",    # All rules have logging enabled
    "FGT-10": "protect",   # Multiple admin accounts + 2FA
    "FGT-11": "protect",   # Password policy enabled
    # Cisco IOS
    "CIS-01": "protect",   # SNMP default communities removed
    "CIS-02": "protect",   # SSH v2 only
    "CIS-03": "protect",   # Service password-encryption
    "CIS-04": "identify",  # NTP configured
    "CIS-05": "detect",    # Syslog to remote host
    "CIS-06": "protect",   # Enable secret configured
    "CIS-07": "protect",   # AAA new-model enabled
    "CIS-08": "protect",   # Login banner configured
    "CIS-09": "protect",   # Telnet disabled on VTY
    "CIS-10": "protect",   # CDP disabled globally
    # HP Comware
    "HPC-01": "protect",   # SNMP default communities removed
    "HPC-02": "protect",   # SSH v2 enabled
    "HPC-03": "identify",  # NTP configured
    "HPC-04": "detect",    # Syslog (info-center) enabled
    "HPC-05": "protect",   # VTY idle timeout ≤ 15 min
    "HPC-06": "protect",   # Password complexity policy
    "HPC-07": "protect",   # Telnet server disabled
    # Generic SSH fallback
    "GEN-01": "protect",   # SNMP default communities removed
    "GEN-02": "identify",  # NTP configured
    "GEN-03": "detect",    # Syslog remote configured
    # SonicWall — Gateway Anti-Virus
    "SW-GAV-01": "protect",  # GAV enabled
    "SW-GAV-02": "protect",  # HTTP inbound inspection
    "SW-GAV-03": "protect",  # SMTP inbound inspection
    "SW-GAV-04": "protect",  # Outbound inspection active
    "SW-GAV-05": "protect",  # Detection-only mode disabled
    "SW-GAV-06": "protect",  # MS Office macros blocked
    "SW-GAV-07": "protect",  # Password-protected ZIP blocked
    "SW-GAV-08": "protect",  # Cloud AV database enabled
    # SonicWall — Anti-Spyware
    "SW-SPY-01": "protect",  # Anti-Spyware enabled
    "SW-SPY-02": "protect",  # High-danger prevention active
    "SW-SPY-03": "protect",  # Medium-danger prevention active
    "SW-SPY-04": "detect",   # Outbound spyware inspection
    # SonicWall — Intrusion Prevention
    "SW-IPS-01": "detect",   # IPS enabled
    "SW-IPS-02": "detect",   # High-priority prevention active
    "SW-IPS-03": "detect",   # Medium-priority prevention active
}

_NETWORK_CTRL_ISO: dict[str, IsoDomain] = {
    # Fortinet
    "FGT-01": "A.5_access_auth",  # Admin idle timeout → Access Control
    "FGT-02": "A.8_config",       # HTTPS redirect → Configuration Mgmt
    "FGT-03": "A.8_crypto",       # TLS 1.2+ → Cryptography
    "FGT-04": "A.8_crypto",       # Strong crypto → Cryptography
    "FGT-05": "A.8_network",      # SNMP communities → Network Security
    "FGT-06": "A.8_logging",      # NTP → Logging (accurate timestamps)
    "FGT-07": "A.8_logging",      # Syslog → Logging and Monitoring
    "FGT-08": "A.8_network",      # No any→any → Network Segregation
    "FGT-09": "A.8_logging",      # Rule logging → Logging and Monitoring
    "FGT-10": "A.5_access_auth",  # Admin accounts + 2FA → Access Control
    "FGT-11": "A.5_access_auth",  # Password policy → Access Control
    # Cisco IOS
    "CIS-01": "A.8_network",      # SNMP communities → Network Security
    "CIS-02": "A.8_config",       # SSH v2 → Configuration Mgmt
    "CIS-03": "A.8_crypto",       # Password-encryption → Cryptography
    "CIS-04": "A.8_logging",      # NTP → Logging (accurate timestamps)
    "CIS-05": "A.8_logging",      # Syslog → Logging and Monitoring
    "CIS-06": "A.5_access_auth",  # Enable secret → Access Control
    "CIS-07": "A.5_access_auth",  # AAA → Access Control
    "CIS-08": "A.8_config",       # Login banner → Configuration Mgmt
    "CIS-09": "A.8_network",      # No telnet → Network Security
    "CIS-10": "A.8_network",      # CDP disabled → Network Security
    # HP Comware
    "HPC-01": "A.8_network",      # SNMP communities → Network Security
    "HPC-02": "A.8_config",       # SSH v2 → Configuration Mgmt
    "HPC-03": "A.8_logging",      # NTP → Logging (accurate timestamps)
    "HPC-04": "A.8_logging",      # Syslog → Logging and Monitoring
    "HPC-05": "A.5_access_auth",  # VTY timeout → Access Control
    "HPC-06": "A.5_access_auth",  # Password complexity → Access Control
    "HPC-07": "A.8_network",      # Telnet disabled → Network Security
    # Generic SSH fallback
    "GEN-01": "A.8_network",      # SNMP communities → Network Security
    "GEN-02": "A.8_logging",      # NTP → Logging (accurate timestamps)
    "GEN-03": "A.8_logging",      # Syslog → Logging and Monitoring
    # SonicWall — Gateway Anti-Virus
    "SW-GAV-01": "A.8_vuln",       # GAV enabled → Vulnerability Mgmt
    "SW-GAV-02": "A.8_network",    # HTTP inbound → Network Security
    "SW-GAV-03": "A.8_network",    # SMTP inbound → Network Security
    "SW-GAV-04": "A.8_network",    # Outbound inspection → Network Security
    "SW-GAV-05": "A.8_vuln",       # Detection-only disabled → Vuln Mgmt (blocking active)
    "SW-GAV-06": "A.8_config",     # MS macros blocked → Configuration Mgmt
    "SW-GAV-07": "A.8_config",     # ZIP password blocked → Configuration Mgmt
    "SW-GAV-08": "A.8_vuln",       # Cloud AV → Vulnerability Mgmt
    # SonicWall — Anti-Spyware
    "SW-SPY-01": "A.8_vuln",       # Anti-Spyware enabled → Vulnerability Mgmt
    "SW-SPY-02": "A.8_vuln",       # High-danger prevention → Vulnerability Mgmt
    "SW-SPY-03": "A.8_vuln",       # Medium-danger prevention → Vulnerability Mgmt
    "SW-SPY-04": "A.8_logging",    # Outbound inspection → Logging/Monitoring
    # SonicWall — Intrusion Prevention
    "SW-IPS-01": "A.8_network",    # IPS enabled → Network Security
    "SW-IPS-02": "A.8_network",    # High-priority prevention → Network Security
    "SW-IPS-03": "A.8_network",    # Medium-priority prevention → Network Security
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


def classify_controls_by_nist(controls: list[dict]) -> dict[str, list[dict]]:
    """
    Return each control assigned to its NIST CSF function.
    Only includes passed/failed controls (not_applicable excluded).
    Preserves server_id and server_name when present (tagged by _controls_data).
    """
    result: dict[str, list[dict]] = {f: [] for f in ALL_NIST_FUNCTIONS}
    for ctrl in controls:
        if ctrl.get("result", "not_applicable") == "not_applicable":
            continue
        func = _classify_nist(
            str(ctrl.get("control_id", "")),
            str(ctrl.get("title", "")),
        )
        entry: dict = {
            "control_id": ctrl.get("control_id", ""),
            "title":      ctrl.get("title", ""),
            "result":     ctrl.get("result", ""),
            "risk_level": ctrl.get("risk_level", "low"),
        }
        if ctrl.get("server_id"):
            entry["server_id"] = ctrl["server_id"]
        if ctrl.get("server_name"):
            entry["server_name"] = ctrl["server_name"]
        result[func].append(entry)
    return result


def classify_controls_by_iso(controls: list[dict]) -> dict[str, list[dict]]:
    """
    Return each control assigned to its ISO 27001:2022 domain.
    Only includes passed/failed controls (not_applicable excluded).
    Preserves server_id and server_name when present.
    """
    result: dict[str, list[dict]] = {d: [] for d in ALL_ISO_DOMAINS}
    for ctrl in controls:
        if ctrl.get("result", "not_applicable") == "not_applicable":
            continue
        domain = _classify_iso(
            str(ctrl.get("control_id", "")),
            str(ctrl.get("title", "")),
        )
        entry: dict = {
            "control_id": ctrl.get("control_id", ""),
            "title":      ctrl.get("title", ""),
            "result":     ctrl.get("result", ""),
            "risk_level": ctrl.get("risk_level", "low"),
        }
        if ctrl.get("server_id"):
            entry["server_id"] = ctrl["server_id"]
        if ctrl.get("server_name"):
            entry["server_name"] = ctrl["server_name"]
        result[domain].append(entry)
    return result


# ── Network device scoring (FGT-*, CIS-*, HPC-*, GEN-*) ──────────────────────

def score_network_by_nist(controls: list[dict]) -> dict[str, float | None]:
    """
    Return per-NIST-function pass rates from network device compliance controls.
    Uses explicit ID-based mapping (_NETWORK_CTRL_NIST) instead of section/keyword heuristics.
    None means no applicable controls were found for that function.
    """
    passed_w: dict[str, float] = defaultdict(float)
    total_w: dict[str, float] = defaultdict(float)

    for ctrl in controls:
        result = ctrl.get("result", "not_applicable")
        if result == "not_applicable":
            continue
        ctrl_id = str(ctrl.get("control_id", ""))
        func = _NETWORK_CTRL_NIST.get(ctrl_id)
        if func is None:
            continue  # unknown control ID — skip rather than misclassify
        w = _RISK_WEIGHT.get(str(ctrl.get("risk_level", "low")), 1)
        total_w[func] += w
        if result == "passed":
            passed_w[func] += w

    return {
        f: (round(passed_w[f] / total_w[f] * 100, 1) if total_w[f] > 0 else None)
        for f in ALL_NIST_FUNCTIONS
    }


def score_network_by_iso(controls: list[dict]) -> dict[str, float | None]:
    """
    Return per-ISO-domain pass rates from network device compliance controls.
    Uses explicit ID-based mapping (_NETWORK_CTRL_ISO).
    None means no applicable controls were found for that domain.
    """
    passed_w: dict[str, float] = defaultdict(float)
    total_w: dict[str, float] = defaultdict(float)

    for ctrl in controls:
        result = ctrl.get("result", "not_applicable")
        if result == "not_applicable":
            continue
        ctrl_id = str(ctrl.get("control_id", ""))
        domain = _NETWORK_CTRL_ISO.get(ctrl_id)
        if domain is None:
            continue  # unknown control ID — skip
        w = _RISK_WEIGHT.get(str(ctrl.get("risk_level", "low")), 1)
        total_w[domain] += w
        if result == "passed":
            passed_w[domain] += w

    return {
        d: (round(passed_w[d] / total_w[d] * 100, 1) if total_w[d] > 0 else None)
        for d in ALL_ISO_DOMAINS
    }


def blend_scores(
    server: float | None,
    network: float | None,
    server_weight: float = 0.60,
) -> float | None:
    """
    Blend server and network scores.
    - Both present: weighted average (server_weight for server, rest for network).
    - Only one present: return that one.
    - Neither: return None.
    """
    if server is not None and network is not None:
        net_weight = 1.0 - server_weight
        return round(server * server_weight + network * net_weight, 1)
    return server if server is not None else network
