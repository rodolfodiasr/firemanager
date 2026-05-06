"""
Switch config renderer — converts normalized IR + port_mapping to CLI commands
for the target vendor.

port_mapping: { "source_port_name": "target_port_name" }
  Example: {"0/1": "GigabitEthernet1/0/1", "0/2": "GigabitEthernet1/0/2"}

Returns: {"commands": [str], "warnings": [str]}
"""
from __future__ import annotations

from typing import Any


# ── Sorting helpers ───────────────────────────────────────────────────────────

def _vlan_key(v: str) -> int:
    try:
        return int(v)
    except ValueError:
        return 9999


def _comma_vlans(vlans: list[str]) -> str:
    return ",".join(sorted(vlans, key=_vlan_key))


def _space_vlans(vlans: list[str]) -> str:
    return " ".join(sorted(vlans, key=_vlan_key))


# ── EdgeSwitch renderer ───────────────────────────────────────────────────────

def _render_edgeswitch(ir: dict[str, Any], port_mapping: dict[str, str]) -> dict[str, Any]:
    cmds: list[str] = []
    warns: list[str] = []

    if ir.get("hostname"):
        cmds += [f"hostname {ir['hostname']}", ""]

    vlans = ir.get("vlans", {})
    if vlans:
        cmds.append("vlan database")
        for vid in sorted(vlans, key=_vlan_key):
            name = vlans[vid].get("name")
            cmds.append(f" vlan {vid}" + (f" name {name}" if name else ""))
        cmds += ["exit", ""]

    for iface in ir.get("interfaces", []):
        src = iface["name"]
        tgt = port_mapping.get(src)
        if not tgt:
            warns.append(f"Porta '{src}' sem mapeamento — ignorada")
            continue

        mode    = iface.get("mode", "access")
        pvid    = iface.get("pvid")
        tagged  = [v for v in iface.get("tagged_vlans", []) if v != "all"]

        cmds.append(f"interface {tgt}")
        if iface.get("description"):
            cmds.append(f" description {iface['description']}")

        if mode == "trunk":
            if pvid:
                cmds.append(f" vlan pvid {pvid}")
            if tagged:
                cmds.append(f" vlan tagging {_comma_vlans(tagged)}")
                all_vlans = sorted(set(tagged) | ({pvid} if pvid else set()), key=_vlan_key)
                cmds.append(f" vlan participation include {_comma_vlans(all_vlans)}")
        else:
            if pvid:
                cmds.append(f" vlan pvid {pvid}")
                cmds.append(f" vlan participation include {pvid}")
        cmds += ["exit", ""]

    return {"commands": cmds, "warnings": warns}


# ── Dell N-Series renderer ────────────────────────────────────────────────────

def _render_dell_n(ir: dict[str, Any], port_mapping: dict[str, str]) -> dict[str, Any]:
    cmds: list[str] = []
    warns: list[str] = []

    if ir.get("hostname"):
        cmds += [f"hostname {ir['hostname']}", "!"]

    for vid, vinfo in sorted(ir.get("vlans", {}).items(), key=lambda kv: _vlan_key(kv[0])):
        cmds.append(f"vlan {vid}")
        if vinfo.get("name"):
            cmds.append(f" name {vinfo['name']}")
        cmds += ["exit", "!"]

    for iface in ir.get("interfaces", []):
        src = iface["name"]
        tgt = port_mapping.get(src)
        if not tgt:
            warns.append(f"Porta '{src}' sem mapeamento — ignorada")
            continue

        mode   = iface.get("mode", "access")
        pvid   = iface.get("pvid")
        tagged = [v for v in iface.get("tagged_vlans", []) if v != "all"]

        cmds.append(f"interface {tgt}")
        if iface.get("description"):
            cmds.append(f" description {iface['description']}")
        cmds.append(f" switchport mode {mode}")
        if mode == "trunk":
            if pvid:
                cmds.append(f" switchport trunk native vlan {pvid}")
            if tagged:
                cmds.append(f" switchport trunk allowed vlan add {_comma_vlans(tagged)}")
        else:
            if pvid:
                cmds.append(f" switchport access vlan {pvid}")
        cmds += ["exit", "!"]

    return {"commands": cmds, "warnings": warns}


# ── Cisco IOS renderer ────────────────────────────────────────────────────────

def _render_cisco_ios(ir: dict[str, Any], port_mapping: dict[str, str]) -> dict[str, Any]:
    cmds: list[str] = []
    warns: list[str] = []

    if ir.get("hostname"):
        cmds += [f"hostname {ir['hostname']}", "!"]

    for vid, vinfo in sorted(ir.get("vlans", {}).items(), key=lambda kv: _vlan_key(kv[0])):
        cmds.append(f"vlan {vid}")
        if vinfo.get("name"):
            cmds.append(f" name {vinfo['name']}")
        cmds += ["!", ""]

    for iface in ir.get("interfaces", []):
        src = iface["name"]
        tgt = port_mapping.get(src)
        if not tgt:
            warns.append(f"Porta '{src}' sem mapeamento — ignorada")
            continue

        mode   = iface.get("mode", "access")
        pvid   = iface.get("pvid")
        tagged = [v for v in iface.get("tagged_vlans", []) if v != "all"]

        cmds.append(f"interface {tgt}")
        if iface.get("description"):
            cmds.append(f" description {iface['description']}")
        cmds.append(f" switchport mode {mode}")
        if mode == "trunk":
            if pvid:
                cmds.append(f" switchport trunk native vlan {pvid}")
            if tagged:
                cmds.append(f" switchport trunk allowed vlan {_comma_vlans(tagged)}")
        else:
            if pvid:
                cmds.append(f" switchport access vlan {pvid}")
        cmds += ["!", ""]

    return {"commands": cmds, "warnings": warns}


# ── HP Comware renderer ───────────────────────────────────────────────────────

def _render_hp_comware(ir: dict[str, Any], port_mapping: dict[str, str]) -> dict[str, Any]:
    cmds: list[str] = []
    warns: list[str] = []

    if ir.get("hostname"):
        cmds += [f"sysname {ir['hostname']}", ""]

    for vid, vinfo in sorted(ir.get("vlans", {}).items(), key=lambda kv: _vlan_key(kv[0])):
        cmds.append(f"vlan {vid}")
        if vinfo.get("name"):
            cmds.append(f" name {vinfo['name']}")
        cmds += ["quit", ""]

    for iface in ir.get("interfaces", []):
        src = iface["name"]
        tgt = port_mapping.get(src)
        if not tgt:
            warns.append(f"Porta '{src}' sem mapeamento — ignorada")
            continue

        mode   = iface.get("mode", "access")
        pvid   = iface.get("pvid")
        tagged = iface.get("tagged_vlans", [])

        cmds.append(f"interface {tgt}")
        if iface.get("description"):
            cmds.append(f" description {iface['description']}")
        cmds.append(f" port link-type {mode}")
        if mode == "trunk":
            if pvid:
                cmds.append(f" port trunk pvid vlan {pvid}")
            if tagged == ["all"]:
                cmds.append(" port trunk permit vlan all")
            elif tagged:
                cmds.append(f" port trunk permit vlan {_space_vlans(tagged)}")
            else:
                warns.append(
                    f"Porta '{src}' modo trunk sem VLANs tagged — adicione manualmente: "
                    f"port trunk permit vlan <IDs>"
                )
        else:
            if pvid:
                cmds.append(f" port access vlan {pvid}")
            else:
                warns.append(
                    f"Porta '{src}' sem VLAN de acesso — adicione manualmente: "
                    f"port access vlan <ID>"
                )
        cmds += ["quit", ""]

    return {"commands": cmds, "warnings": warns}


# ── Registry ──────────────────────────────────────────────────────────────────

_RENDERERS = {
    "edgeswitch": _render_edgeswitch,
    "dell_n":     _render_dell_n,
    "cisco_ios":  _render_cisco_ios,
    "cisco_nxos": _render_cisco_ios,
    "hp_comware": _render_hp_comware,
    "aruba":      _render_cisco_ios,
}


def render_config(
    ir: dict[str, Any],
    target_vendor: str,
    port_mapping: dict[str, str],
) -> dict[str, Any]:
    """Render CLI commands for target_vendor from IR + port_mapping. Never raises."""
    renderer = _RENDERERS.get(target_vendor)
    if renderer is None:
        return {
            "commands": [],
            "warnings": [f"Vendor '{target_vendor}' não tem renderer implementado"],
        }
    try:
        return renderer(ir, port_mapping)
    except Exception as exc:
        return {"commands": [], "warnings": [f"Erro no renderer ({target_vendor}): {exc}"]}
