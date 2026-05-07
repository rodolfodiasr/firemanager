"""Service functions for Fase 17 — Golden Config Templates."""
from __future__ import annotations

import asyncio
import re

# ── System Templates (built-in library) ──────────────────────────────────────

SYSTEM_TEMPLATES: list[dict] = [
    {
        "id": "sys-fortinet-filial",
        "tenant_id": None,
        "name": "Filial Padrão — Fortinet FortiGate",
        "description": "Template base para FortiGate em filial: interface LAN, rota padrão e NTP.",
        "vendor": "fortinet",
        "category": "filial",
        "version": 1,
        "is_system": True,
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "variables": [
            {"key": "BRANCH_NAME", "type": "string",   "label": "Nome da filial",       "required": True,  "hint": "Ex: Filial-SP"},
            {"key": "BRANCH_LAN",  "type": "cidr",     "label": "Rede LAN (CIDR)",      "required": True,  "hint": "Ex: 192.168.10.0/24"},
            {"key": "GW_IP",       "type": "ip",       "label": "Gateway WAN (ISP)",    "required": True,  "hint": "IP fornecido pela operadora"},
            {"key": "TUNNEL_HQ",   "type": "ip",       "label": "IP túnel para HQ",     "required": False, "hint": "Deixe vazio se não usar VPN"},
            {"key": "NTP_SERVER",  "type": "ip",       "label": "Servidor NTP",         "required": False, "default": "200.160.0.8"},
        ],
        "content": (
            'config system interface\n'
            '    edit "lan"\n'
            '        set alias "{BRANCH_NAME}-LAN"\n'
            '        set ip {BRANCH_LAN}\n'
            '        set allowaccess ping https ssh\n'
            '        set role lan\n'
            '    next\n'
            'end\n\n'
            'config router static\n'
            '    edit 0\n'
            '        set gateway {GW_IP}\n'
            '        set device "wan1"\n'
            '    next\n'
            'end\n\n'
            'config system ntp\n'
            '    set type custom\n'
            '    set ntpsync enable\n'
            '    config ntpserver\n'
            '        edit 1\n'
            '            set server "{NTP_SERVER}"\n'
            '        next\n'
            '    end\n'
            'end\n'
        ),
    },
    {
        "id": "sys-sonicwall-filial",
        "tenant_id": None,
        "name": "Filial Padrão — SonicWall",
        "description": "Template base para SonicWall em filial: interface LAN, rota padrão.",
        "vendor": "sonicwall",
        "category": "filial",
        "version": 1,
        "is_system": True,
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "variables": [
            {"key": "BRANCH_NAME", "type": "string", "label": "Nome da filial",     "required": True},
            {"key": "BRANCH_LAN",  "type": "cidr",   "label": "Rede LAN (CIDR)",   "required": True,  "hint": "Ex: 192.168.10.0/24"},
            {"key": "GW_IP",       "type": "ip",     "label": "Gateway WAN (ISP)", "required": True},
        ],
        "content": (
            'interface X0\n'
            '    ip-assignment static\n'
            '    ip {BRANCH_LAN}\n'
            '    name "{BRANCH_NAME}-LAN"\n'
            '    zone LAN\n\n'
            'ip route 0.0.0.0/0 {GW_IP}\n'
        ),
    },
    {
        "id": "sys-cisco-switch-acesso",
        "tenant_id": None,
        "name": "Switch de Acesso Padrão — Cisco IOS",
        "description": "Template Cisco IOS para switch de acesso: VLANs, gerência, STP e NTP.",
        "vendor": "cisco_ios",
        "category": "switch_acesso",
        "version": 1,
        "is_system": True,
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "variables": [
            {"key": "BRANCH_NAME", "type": "string",  "label": "Hostname do switch",   "required": True},
            {"key": "MGMT_IP",     "type": "cidr",    "label": "IP de gerência (CIDR)","required": True,  "hint": "Ex: 192.168.1.10/24"},
            {"key": "GW_IP",       "type": "ip",      "label": "Gateway de gerência",   "required": True},
            {"key": "VLAN_DATA",   "type": "integer", "label": "VLAN de dados",         "required": True,  "default": "10"},
            {"key": "VLAN_VOICE",  "type": "integer", "label": "VLAN de voz",           "required": False, "default": "20"},
            {"key": "VLAN_MGMT",   "type": "integer", "label": "VLAN de gerência",      "required": True,  "default": "99"},
            {"key": "NTP_SERVER",  "type": "ip",      "label": "Servidor NTP",          "required": False, "default": "200.160.0.8"},
        ],
        "content": (
            'hostname {BRANCH_NAME}\n\n'
            'vlan {VLAN_DATA}\n name DATA\nvlan {VLAN_VOICE}\n name VOICE\nvlan {VLAN_MGMT}\n name MGMT\n\n'
            'interface Vlan{VLAN_MGMT}\n ip address {MGMT_IP}\n no shutdown\n\n'
            'ip default-gateway {GW_IP}\n\n'
            'spanning-tree mode rapid-pvst\nspanning-tree portfast default\nspanning-tree portfast bpduguard default\n\n'
            'ntp server {NTP_SERVER}\n\n'
            'line vty 0 4\n login local\n transport input ssh\n\n'
            'service password-encryption\n'
        ),
    },
    {
        "id": "sys-hp-comware-switch",
        "tenant_id": None,
        "name": "Switch de Acesso Padrão — HP Comware",
        "description": "Template base HP/H3C Comware: VLAN, gerência, STP e SSH.",
        "vendor": "hp_comware",
        "category": "switch_acesso",
        "version": 1,
        "is_system": True,
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "variables": [
            {"key": "BRANCH_NAME", "type": "string",  "label": "Sysname",             "required": True},
            {"key": "MGMT_IP",     "type": "ip",      "label": "IP de gerência",       "required": True},
            {"key": "MGMT_MASK",   "type": "string",  "label": "Máscara de gerência",  "required": True,  "default": "255.255.255.0"},
            {"key": "GW_IP",       "type": "ip",      "label": "Gateway padrão",        "required": True},
            {"key": "VLAN_MGMT",   "type": "integer", "label": "VLAN de gerência",      "required": True,  "default": "99"},
            {"key": "NTP_SERVER",  "type": "ip",      "label": "Servidor NTP",          "required": False, "default": "200.160.0.8"},
        ],
        "content": (
            'sysname {BRANCH_NAME}\n\n'
            'vlan {VLAN_MGMT}\n description MGMT\n\n'
            'interface Vlan-interface{VLAN_MGMT}\n ip address {MGMT_IP} {MGMT_MASK}\n\n'
            'ip route-static 0.0.0.0 0.0.0.0 {GW_IP}\n\n'
            'stp mode rstp\nstp enable\n\n'
            'ntp-service unicast-server {NTP_SERVER}\n\n'
            'ssh server enable\nuser-interface vty 0 4\n authentication-mode scheme\n protocol inbound ssh\n\n'
            'save force\n'
        ),
    },
]


def get_system_template(template_id: str) -> dict | None:
    for t in SYSTEM_TEMPLATES:
        if t["id"] == template_id:
            return t
    return None


# ── Rendering ────────────────────────────────────────────────────────────────

def render_template(content: str, variable_values: dict[str, str]) -> tuple[str, list[str]]:
    """Replace {VAR} placeholders. Returns (rendered_content, unresolved_keys)."""
    unresolved: list[str] = []

    def replacer(m: re.Match) -> str:
        key = m.group(1)
        val = variable_values.get(key, "").strip()
        if not val:
            unresolved.append(key)
            return m.group(0)
        return val

    rendered = re.sub(r"\{([A-Z0-9_]+)\}", replacer, content)
    return rendered, list(dict.fromkeys(unresolved))


# ── Divergence helpers ────────────────────────────────────────────────────────

def detect_section(line: str) -> str:
    ll = line.lower()
    if any(k in ll for k in ("interface", "ethernet", "gigabit", "port", "vlan-interface", "edit \"lan")):
        return "Interfaces"
    if "vlan" in ll:
        return "VLANs"
    if any(k in ll for k in ("route", "router", "ip route", "ip default-gateway", "gateway")):
        return "Roteamento"
    if "ntp" in ll:
        return "NTP"
    if any(k in ll for k in ("aaa", "tacacs", "radius")):
        return "AAA"
    if "snmp" in ll:
        return "SNMP"
    if any(k in ll for k in ("logging", "syslog")):
        return "Logging"
    if "banner" in ll:
        return "Banner"
    if any(k in ll for k in ("username", "password", "enable secret", "service password")):
        return "Usuários"
    if "spanning-tree" in ll or "stp" in ll:
        return "STP"
    if any(k in ll for k in ("ssh", "line vty", "transport input")):
        return "Acesso Remoto"
    if "hostname" in ll or "sysname" in ll:
        return "Identidade"
    return "Configuração Geral"


def compute_divergence(rendered: str, live_config: str) -> list[dict]:
    def clean(text: str) -> set[str]:
        return {
            l.strip()
            for l in text.splitlines()
            if l.strip() and not l.strip().startswith(("!", "#", "Building", "Current", "version "))
        }

    tmpl_lines = clean(rendered)
    dev_lines = clean(live_config)

    items: list[dict] = []
    for line in sorted(tmpl_lines - dev_lines):
        items.append({"section": detect_section(line), "value": line, "status": "missing"})
    for line in sorted(dev_lines - tmpl_lines):
        items.append({"section": detect_section(line), "value": line, "status": "extra"})
    return items


_SHOW_CONFIG: dict[str, str] = {
    "cisco_ios":  "show running-config",
    "cisco_nxos": "show running-config",
    "juniper":    "show configuration",
    "aruba":      "show running-config",
    "dell":       "show running-config",
    "dell_n":     "show running-config",
    "ubiquiti":   "show configuration",
    "edgeswitch": "show running-config",
    "hp_comware": "display current-configuration",
}


async def fetch_live_config(device, timeout: int = 30) -> str | None:
    from app.connectors.factory import CLI_VENDORS, get_ssh_connector

    if device.vendor not in CLI_VENDORS:
        return None

    cmd = _SHOW_CONFIG.get(device.vendor.value, "show running-config")
    try:
        conn = get_ssh_connector(device)
        result = await asyncio.wait_for(
            conn.execute_show_commands([cmd]),
            timeout=timeout,
        )
        return result.output if result.success else None
    except Exception:
        return None


async def resolve_device_variables(device, db) -> dict[str, str]:
    """Inherit tenant variables then override with device variables (Phase 13 logic)."""
    from sqlalchemy import select
    from app.models.variable import TenantVariable, DeviceVariable

    merged: dict[str, str] = {}

    tenant_rows = await db.execute(
        select(TenantVariable).where(TenantVariable.tenant_id == device.tenant_id)
    )
    for v in tenant_rows.scalars().all():
        merged[v.name.upper()] = v.value

    device_rows = await db.execute(
        select(DeviceVariable).where(DeviceVariable.device_id == device.id)
    )
    for v in device_rows.scalars().all():
        merged[v.name.upper()] = v.value

    return merged
