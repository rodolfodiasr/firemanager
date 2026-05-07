"""
Switch config renderer — converts normalized IR + port_mapping to CLI commands
for the target vendor.

port_mapping: { "source_port_name": "target_port_name" }
  Example: {"0/1": "GigabitEthernet1/0/1", "0/2": "GigabitEthernet1/0/2"}

Returns: {"commands": [str], "warnings": [str]}
"""
from __future__ import annotations

from typing import Any


# ── LAG helpers ───────────────────────────────────────────────────────────────

import re as _re

_LAG_IFACE_RE = _re.compile(
    r"^(lag|port-channel|port\s+channel|bridge-aggregation|aggregation|ae)\s*\d+$",
    _re.I,
)


def _is_lag_iface(name: str) -> bool:
    return bool(_LAG_IFACE_RE.match(name.strip()))


def _lag_num(tgt_name: str) -> str:
    """Extract trailing integer from a LAG target name: 'Port-Channel5' → '5'."""
    m = _re.search(r"\d+$", tgt_name)
    return m.group() if m else "1"


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
        # Member ports are rendered inline when processing the LAG interface
        if iface.get("lag_member_of"):
            continue

        # Skip L3/management interfaces — they carry IP config, not switching config
        if iface.get("port_type") == "vlan":
            continue

        src = iface["name"]
        tgt = port_mapping.get(src)
        if not tgt:
            warns.append(f"Porta '{src}' sem mapeamento — ignorada")
            continue

        # LAG: render member ports first, then the LAG interface itself
        if iface.get("members"):
            lag_n = _lag_num(tgt)
            for member_src in iface["members"]:
                member_tgt = port_mapping.get(member_src)
                if not member_tgt:
                    warns.append(f"Membro '{member_src}' do LAG '{src}' sem mapeamento — ignorado")
                    continue
                cmds += [f"interface {member_tgt}", f" lag {lag_n}", "exit", ""]

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

    for l3 in ir.get("l3_interfaces", []):
        cmds += [f"interface Vlan {l3['vlan_id']}",
                 f" ip address {l3['ip']} {l3['mask']}", "exit", ""]
        warns.append(
            f"IP de gerência migrado (VLAN {l3['vlan_id']}: {l3['ip']} {l3['mask']}) "
            f"— verifique se é o IP correto para o switch de destino antes de aplicar"
        )

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
        if iface.get("lag_member_of"):
            continue

        if iface.get("port_type") == "vlan":
            continue

        src = iface["name"]
        tgt = port_mapping.get(src)
        if not tgt:
            warns.append(f"Porta '{src}' sem mapeamento — ignorada")
            continue

        # LAG: render member ports (channel-group) before the port-channel interface
        if iface.get("members"):
            lag_n = _lag_num(tgt)
            lag_mode = iface.get("lag_mode", "active")
            for member_src in iface["members"]:
                member_tgt = port_mapping.get(member_src)
                if not member_tgt:
                    warns.append(f"Membro '{member_src}' do LAG '{src}' sem mapeamento — ignorado")
                    continue
                cmds += [f"interface {member_tgt}", f" channel-group {lag_n} mode {lag_mode}", "exit", "!"]

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
        if iface.get("lag_member_of"):
            continue

        if iface.get("port_type") == "vlan":
            continue

        src = iface["name"]
        tgt = port_mapping.get(src)
        if not tgt:
            warns.append(f"Porta '{src}' sem mapeamento — ignorada")
            continue

        # LAG: render member ports (channel-group) before the Port-Channel interface
        if iface.get("members"):
            lag_n = _lag_num(tgt)
            lag_mode = iface.get("lag_mode", "active")
            for member_src in iface["members"]:
                member_tgt = port_mapping.get(member_src)
                if not member_tgt:
                    warns.append(f"Membro '{member_src}' do LAG '{src}' sem mapeamento — ignorado")
                    continue
                cmds += [f"interface {member_tgt}", f" channel-group {lag_n} mode {lag_mode}", "!", ""]

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

    for l3 in ir.get("l3_interfaces", []):
        cmds += [f"interface Vlan{l3['vlan_id']}",
                 f" ip address {l3['ip']} {l3['mask']}", "!", ""]
        warns.append(
            f"IP de gerência migrado (VLAN {l3['vlan_id']}: {l3['ip']} {l3['mask']}) "
            f"— verifique se é o IP correto para o switch de destino antes de aplicar"
        )

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
        if iface.get("lag_member_of"):
            continue

        if iface.get("port_type") == "vlan":
            continue

        src = iface["name"]
        tgt = port_mapping.get(src)
        if not tgt:
            warns.append(f"Porta '{src}' sem mapeamento — ignorada")
            continue

        # LAG: render member ports (port link-aggregation group) before Bridge-Aggregation
        if iface.get("members"):
            lag_n = _lag_num(tgt)
            for member_src in iface["members"]:
                member_tgt = port_mapping.get(member_src)
                if not member_tgt:
                    warns.append(f"Membro '{member_src}' do LAG '{src}' sem mapeamento — ignorado")
                    continue
                cmds += [f"interface {member_tgt}", f" port link-aggregation group {lag_n}", "quit", ""]

        mode   = iface.get("mode", "access")
        pvid   = iface.get("pvid")
        tagged = iface.get("tagged_vlans", [])

        cmds.append(f"interface {tgt}")
        if iface.get("description"):
            cmds.append(f" description {iface['description']}")
        # LACP mode on the Bridge-Aggregation interface
        lag_mode = iface.get("lag_mode", "")
        if lag_mode in ("active", "passive"):
            cmds.append(" link-aggregation mode dynamic")
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

    for l3 in ir.get("l3_interfaces", []):
        cmds += [f"interface Vlan-interface {l3['vlan_id']}",
                 f" ip address {l3['ip']} {l3['mask']}", "quit", ""]
        warns.append(
            f"IP de gerência migrado (VLAN {l3['vlan_id']}: {l3['ip']} {l3['mask']}) "
            f"— verifique se é o IP correto para o switch de destino antes de aplicar"
        )

    return {"commands": cmds, "warnings": warns}


# ── Juniper EX renderer ───────────────────────────────────────────────────────

def _render_juniper(ir: dict[str, Any], port_mapping: dict[str, str]) -> dict[str, Any]:
    cmds: list[str] = []
    warns: list[str] = []

    if ir.get("hostname"):
        cmds += ["system {", f"    host-name {ir['hostname']};", "}", ""]

    vlans = ir.get("vlans", {})
    if vlans:
        cmds.append("vlans {")
        for vid in sorted(vlans, key=_vlan_key):
            vname = vlans[vid].get("name") or f"VLAN{vid}"
            # Juniper VLAN names: alphanumeric, dash, underscore only
            vname = _re.sub(r"[^A-Za-z0-9_\-]", "_", vname)
            cmds += [f"    {vname} {{", f"        vlan-id {vid};", "    }"]
        cmds += ["}", ""]

    cmds.append("interfaces {")

    for iface in ir.get("interfaces", []):
        if iface.get("lag_member_of"):
            continue

        if iface.get("port_type") == "vlan":
            continue

        src = iface["name"]
        tgt = port_mapping.get(src)
        if not tgt:
            warns.append(f"Porta '{src}' sem mapeamento — ignorada")
            continue

        # LAG: render member ether-options blocks before the aggregated interface
        if iface.get("members"):
            lag_mode = iface.get("lag_mode", "active")
            for member_src in iface["members"]:
                member_tgt = port_mapping.get(member_src)
                if not member_tgt:
                    warns.append(f"Membro '{member_src}' do LAG '{src}' sem mapeamento — ignorado")
                    continue
                cmds += [
                    f"    {member_tgt} {{",
                    "        ether-options {",
                    f"            802.3ad {tgt};",
                    "        }",
                    "    }",
                ]
            # Open the aggregated interface block
            cmds.append(f"    {tgt} {{")
            if iface.get("description"):
                cmds.append(f'        description "{iface["description"]}";')
            cmds += [
                "        aggregated-ether-options {",
                "            lacp {",
                f"                {lag_mode};",
                "            }",
                "        }",
            ]
        else:
            cmds.append(f"    {tgt} {{")
            if iface.get("description"):
                cmds.append(f'        description "{iface["description"]}";')

        mode = iface.get("mode", "access")
        pvid = iface.get("pvid")
        tagged = [v for v in iface.get("tagged_vlans", []) if v != "all"]

        cmds += ["        unit 0 {", "            family ethernet-switching {",
                 f"                interface-mode {mode};"]
        if mode == "trunk":
            if tagged:
                cmds.append(f"                vlan {{ members [ {' '.join(sorted(tagged, key=_vlan_key))} ]; }}")
            if pvid:
                cmds.append(f"                native-vlan-id {pvid};")
        else:
            if pvid:
                cmds.append(f"                vlan {{ members {pvid}; }}")
        cmds += ["            }", "        }", "    }"]

    cmds.append("}")
    return {"commands": cmds, "warnings": warns}


# ── Aruba ArubaOS-Switch renderer ─────────────────────────────────────────────

def _render_aruba(ir: dict[str, Any], port_mapping: dict[str, str]) -> dict[str, Any]:
    cmds: list[str] = []
    warns: list[str] = []

    if ir.get("hostname"):
        cmds += [f'hostname "{ir["hostname"]}"', "!"]

    for vid, vinfo in sorted(ir.get("vlans", {}).items(), key=lambda kv: _vlan_key(kv[0])):
        cmds.append(f"vlan {vid}")
        if vinfo.get("name"):
            cmds.append(f'   name "{vinfo["name"]}"')
        cmds += ["!", ""]

    # trunk commands for LAG interfaces
    for iface in ir.get("interfaces", []):
        if iface.get("lag_member_of") or not iface.get("members"):
            continue
        src = iface["name"]
        tgt = port_mapping.get(src)
        if not tgt:
            warns.append(f"LAG '{src}' sem mapeamento — ignorado")
            continue
        member_tgts = []
        for ms in iface["members"]:
            mt = port_mapping.get(ms)
            if mt:
                member_tgts.append(mt)
            else:
                warns.append(f"Membro '{ms}' do LAG '{src}' sem mapeamento — ignorado")
        if member_tgts:
            mode_kw = " lacp" if iface.get("lag_mode") in ("active", "passive") else ""
            cmds += [f"trunk {','.join(member_tgts)} {tgt}{mode_kw}", ""]

    # Interface VLAN config
    for iface in ir.get("interfaces", []):
        if iface.get("lag_member_of"):
            continue

        if iface.get("port_type") == "vlan":
            continue

        src = iface["name"]
        tgt = port_mapping.get(src)
        if not tgt:
            warns.append(f"Porta '{src}' sem mapeamento — ignorada")
            continue

        mode = iface.get("mode", "access")
        pvid = iface.get("pvid")
        tagged = [v for v in iface.get("tagged_vlans", []) if v != "all"]

        cmds.append(f"interface {tgt}")
        if iface.get("description"):
            cmds.append(f'   name "{iface["description"]}"')
        if mode == "trunk":
            if tagged:
                cmds.append(f"   tagged vlan {_comma_vlans(tagged)}")
            if pvid:
                cmds.append(f"   untagged vlan {pvid}")
        else:
            if pvid:
                cmds.append(f"   untagged vlan {pvid}")
        cmds += ["!", ""]

    return {"commands": cmds, "warnings": warns}


# ── Intelbras SG renderer ─────────────────────────────────────────────────────
# Intelbras SG uses Cisco IOS-compatible syntax. Thin wrapper for future customization.

def _render_intelbras(ir: dict[str, Any], port_mapping: dict[str, str]) -> dict[str, Any]:
    return _render_cisco_ios(ir, port_mapping)


# ── Registry ──────────────────────────────────────────────────────────────────

_RENDERERS = {
    "edgeswitch": _render_edgeswitch,
    "dell_n":     _render_dell_n,
    "cisco_ios":  _render_cisco_ios,
    "cisco_nxos": _render_cisco_ios,
    "hp_comware": _render_hp_comware,
    "aruba":      _render_aruba,
    "juniper":    _render_juniper,
    "intelbras":  _render_intelbras,
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
