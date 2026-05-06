"""
Switch config parser — converts raw CLI config to a normalized intermediate
representation (IR) used by the migration renderer.

Supported vendors:
    edgeswitch  Ubiquiti EdgeMax 1.x / 2.x
    dell_n      Dell EMC Networking N-Series (DNOS6)
    cisco_ios   Cisco IOS / IOS-XE L2 switches
    cisco_nxos  Cisco NX-OS (L2 subset)
    hp_comware  HP / H3C Comware (V1910, V3600, V5800)
    aruba       ArubaOS-Switch (IOS-like)

IR structure:
{
    "hostname":   str | None,
    "stp_mode":   str | None,      # "rstp" | "mstp" | "pvst" | None
    "vlans":      { "10": {"name": "Management"}, ... },
    "interfaces": [
        {
            "name":         str,           # original port name from config
            "mode":         "trunk"|"access"|"hybrid",
            "pvid":         str | None,    # native / untagged VLAN id
            "tagged_vlans": [str],         # list of tagged VLAN ids
            "description":  str | None,
        }, ...
    ],
    "warnings":   [str],
}
"""
from __future__ import annotations

import re
from typing import Any


# ── VLAN range expansion ──────────────────────────────────────────────────────

def _expand_vlan_list(raw: str) -> list[str]:
    """Expand "10,20-25,30" → ["10","20","21","22","23","24","25","30"]."""
    result: list[str] = []
    for part in raw.replace(" ", "").split(","):
        if "-" in part:
            lo, hi = part.split("-", 1)
            try:
                result.extend(str(v) for v in range(int(lo), int(hi) + 1))
            except ValueError:
                result.append(part)
        elif part.isdigit():
            result.append(part)
    return result


# ── EdgeSwitch parser ─────────────────────────────────────────────────────────

_TOP_LEVEL_KW = re.compile(
    r"^(interface|vlan\s+database|vlan\s+\d|hostname|spanning-tree\s+mode|no\s+spanning-tree)\b",
    re.I,
)


def _parse_edgeswitch(config: str) -> dict[str, Any]:
    ir: dict[str, Any] = {
        "hostname": None, "stp_mode": None,
        "vlans": {}, "interfaces": [], "warnings": [],
    }
    lines = config.splitlines()
    i = 0
    cur_iface: dict | None = None

    # Membership collected from "vlan X / add port Y tagged" style blocks
    port_vlan_tagged: dict[str, list[str]] = {}
    port_vlan_untagged: dict[str, list[str]] = {}

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()

        if not line or line.startswith("!"):
            i += 1
            continue

        if line.lower().startswith("hostname "):
            ir["hostname"] = line.split(None, 1)[1].strip().strip('"').strip("'")
            i += 1
            continue

        m = re.match(r"spanning-tree mode (\S+)", line, re.I)
        if m:
            ir["stp_mode"] = m.group(1).lower()
            i += 1
            continue

        # VLAN database block (EdgeMax native)
        if line.lower() == "vlan database":
            i += 1
            while i < len(lines):
                vl = lines[i].strip()
                if vl.lower() == "exit":
                    i += 1
                    break
                vm = re.match(r"vlan\s+(\S+?)(?:\s+name\s+(.+))?$", vl, re.I)
                if vm:
                    for vid in _expand_vlan_list(vm.group(1)):
                        if vid not in ir["vlans"]:
                            ir["vlans"][vid] = {"name": None}
                        if vm.group(2):
                            ir["vlans"][vid]["name"] = vm.group(2).strip().strip('"').strip("'")
                i += 1
            continue

        # Standalone VLAN block: "vlan 10" with optional indented sub-commands
        vm = re.match(r"^vlan\s+(\d+)\s*$", line, re.I)
        if vm:
            vid = vm.group(1)
            if vid not in ir["vlans"]:
                ir["vlans"][vid] = {"name": None}
            i += 1
            while i < len(lines):
                vl = lines[i]
                vls = vl.strip()
                if not vls or vls.startswith("!"):
                    i += 1
                    continue
                if vls.lower() == "exit":
                    i += 1
                    break
                # Break on next top-level keyword (handles configs without "exit")
                if _TOP_LEVEL_KW.match(vls):
                    break

                nm = re.match(r"name\s+(.+)", vls, re.I)
                if nm:
                    ir["vlans"][vid]["name"] = nm.group(1).strip().strip('"').strip("'")

                # "add port 0/1 tagged" / "add port 0/1 untagged"
                am = re.match(r"add\s+port\s+(\S+)\s+(tagged|untagged)", vls, re.I)
                if am:
                    port = am.group(1)
                    if am.group(2).lower() == "tagged":
                        port_vlan_tagged.setdefault(port, []).append(vid)
                    else:
                        port_vlan_untagged.setdefault(port, []).append(vid)

                # "tagged 0/1 0/2 ..." or "untagged 0/1 0/2 ..."
                tm = re.match(r"(tagged|untagged)\s+([\d/,\s]+)$", vls, re.I)
                if tm:
                    tag_type = tm.group(1).lower()
                    for port in re.split(r"[\s,]+", tm.group(2).strip()):
                        if port:
                            if tag_type == "tagged":
                                port_vlan_tagged.setdefault(port, []).append(vid)
                            else:
                                port_vlan_untagged.setdefault(port, []).append(vid)

                i += 1
            continue

        # Interface block
        ifm = re.match(r"^interface\s+(\S+)", line, re.I)
        if ifm:
            if cur_iface:
                ir["interfaces"].append(_finalize_iface(cur_iface))
            cur_iface = {
                "name": ifm.group(1), "mode": "access",
                "pvid": None, "tagged_vlans": [], "description": None,
                "_participation": [],
            }
            i += 1
            while i < len(lines):
                il = lines[i]
                ils = il.strip()
                if not ils or ils.startswith("!"):
                    i += 1
                    continue
                if ils.lower() == "exit":
                    i += 1
                    break
                # Break on next top-level keyword
                if _TOP_LEVEL_KW.match(ils):
                    break

                # IOS-style switchport
                m2 = re.match(r"switchport mode (\S+)", ils, re.I)
                if m2:
                    cur_iface["mode"] = m2.group(1).lower()
                elif re.match(r"switchport access vlan (\d+)", ils, re.I):
                    cur_iface["pvid"] = re.match(r"switchport access vlan (\d+)", ils, re.I).group(1)
                elif re.match(r"switchport trunk native vlan (\d+)", ils, re.I):
                    cur_iface["pvid"] = re.match(r"switchport trunk native vlan (\d+)", ils, re.I).group(1)
                elif re.match(r"switchport trunk allowed vlan (?:add )?(.+)", ils, re.I):
                    raw_vlans = re.match(r"switchport trunk allowed vlan (?:add )?(.+)", ils, re.I).group(1)
                    cur_iface["tagged_vlans"].extend(_expand_vlan_list(raw_vlans))
                    cur_iface["mode"] = "trunk"
                # EdgeMax-native style
                elif re.match(r"vlan pvid (\d+)", ils, re.I):
                    cur_iface["pvid"] = re.match(r"vlan pvid (\d+)", ils, re.I).group(1)
                elif re.match(r"vlan tagging (.+)", ils, re.I):
                    raw_vlans = re.match(r"vlan tagging (.+)", ils, re.I).group(1)
                    cur_iface["tagged_vlans"].extend(_expand_vlan_list(raw_vlans))
                    cur_iface["mode"] = "trunk"
                elif re.match(r"vlan participation include (.+)", ils, re.I):
                    raw_vlans = re.match(r"vlan participation include (.+)", ils, re.I).group(1)
                    cur_iface["_participation"].extend(_expand_vlan_list(raw_vlans))
                elif re.match(r"description (.+)", ils, re.I):
                    cur_iface["description"] = (
                        re.match(r"description (.+)", ils, re.I).group(1).strip().strip('"').strip("'")
                    )

                i += 1
            continue

        i += 1

    if cur_iface:
        ir["interfaces"].append(_finalize_iface(cur_iface))

    # Merge VLAN block memberships (add port style) into interfaces
    if port_vlan_tagged or port_vlan_untagged:
        for iface in ir["interfaces"]:
            name = iface["name"]
            vt = port_vlan_tagged.get(name, [])
            vu = port_vlan_untagged.get(name, [])
            if vt and not iface["tagged_vlans"]:
                iface["tagged_vlans"] = sorted(set(vt), key=lambda v: int(v) if v.isdigit() else 9999)
                iface["mode"] = "trunk"
            if vu and iface["pvid"] is None:
                iface["pvid"] = sorted(vu, key=lambda v: int(v) if v.isdigit() else 9999)[0]

    return ir


def _finalize_iface(iface: dict) -> dict:
    """Infer pvid from vlan participation include if not set by an explicit vlan pvid line."""
    participation = iface.pop("_participation", [])
    if participation and not iface["pvid"] and not iface["tagged_vlans"]:
        # All participation VLANs, no tagging → access port; pvid = first member
        tagged_set: set[str] = set()
        untagged = [v for v in participation if v not in tagged_set]
        if untagged:
            iface["pvid"] = sorted(untagged, key=lambda v: int(v) if v.isdigit() else 9999)[0]
    elif participation:
        # Has tagging already set; infer pvid from participation - tagged
        tagged_set = set(iface["tagged_vlans"])
        untagged = [v for v in participation if v not in tagged_set]
        if untagged and iface["pvid"] is None:
            iface["pvid"] = sorted(untagged, key=lambda v: int(v) if v.isdigit() else 9999)[0]
    return iface


# ── IOS-style parser (Dell N, Cisco IOS, Aruba) ───────────────────────────────

def _parse_ios_style(config: str) -> dict[str, Any]:
    ir: dict[str, Any] = {
        "hostname": None, "stp_mode": None,
        "vlans": {}, "interfaces": [], "warnings": [],
    }
    lines = config.splitlines()
    i = 0
    cur_iface: dict | None = None

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()

        if line.lower().startswith("hostname "):
            ir["hostname"] = line.split(None, 1)[1].strip()
            i += 1
            continue

        m = re.match(r"spanning-tree mode (\S+)", line, re.I)
        if m:
            ir["stp_mode"] = m.group(1).lower()
            i += 1
            continue

        # VLAN block
        vm = re.match(r"^vlan\s+(\d+)\s*$", line, re.I)
        if vm:
            vid = vm.group(1)
            if vid not in ir["vlans"]:
                ir["vlans"][vid] = {"name": None}
            i += 1
            while i < len(lines):
                vl = lines[i].strip()
                if vl.lower() in ("exit", "!") or (vl and not lines[i][0:1].isspace()):
                    if vl.lower() in ("exit", "!"):
                        i += 1
                    break
                nm = re.match(r"name\s+(.+)", vl, re.I)
                if nm:
                    ir["vlans"][vid]["name"] = nm.group(1).strip()
                i += 1
            continue

        # Interface block
        ifm = re.match(r"^interface\s+(.+)", line, re.I)
        if ifm:
            if cur_iface:
                ir["interfaces"].append(cur_iface)
            cur_iface = {
                "name": ifm.group(1).strip(), "mode": "access",
                "pvid": None, "tagged_vlans": [], "description": None,
            }
            i += 1
            while i < len(lines):
                il = lines[i]
                ils = il.strip()
                if ils.lower() in ("exit", "!"):
                    i += 1
                    break
                if ils and not il[0:1].isspace():
                    break

                m2 = re.match(r"switchport mode (\S+)", ils, re.I)
                if m2:
                    cur_iface["mode"] = m2.group(1).lower()
                elif re.match(r"switchport access vlan (\d+)", ils, re.I):
                    cur_iface["pvid"] = re.match(r"switchport access vlan (\d+)", ils, re.I).group(1)
                elif re.match(r"switchport trunk native vlan (\d+)", ils, re.I):
                    cur_iface["pvid"] = re.match(r"switchport trunk native vlan (\d+)", ils, re.I).group(1)
                elif re.match(r"switchport trunk allowed vlan (?:add )?(.+)", ils, re.I):
                    raw_vlans = re.match(r"switchport trunk allowed vlan (?:add )?(.+)", ils, re.I).group(1)
                    cur_iface["tagged_vlans"].extend(_expand_vlan_list(raw_vlans))
                elif re.match(r"description (.+)", ils, re.I):
                    cur_iface["description"] = re.match(r"description (.+)", ils, re.I).group(1).strip()

                i += 1
            continue

        i += 1

    if cur_iface:
        ir["interfaces"].append(cur_iface)
    return ir


# ── HP Comware parser ─────────────────────────────────────────────────────────

def _parse_hp_comware(config: str) -> dict[str, Any]:
    ir: dict[str, Any] = {
        "hostname": None, "stp_mode": None,
        "vlans": {}, "interfaces": [], "warnings": [],
    }
    lines = config.splitlines()
    i = 0
    cur_iface: dict | None = None

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()

        if line.lower().startswith("sysname "):
            ir["hostname"] = line.split(None, 1)[1].strip()
            i += 1
            continue

        m = re.match(r"stp mode (\S+)", line, re.I)
        if m:
            ir["stp_mode"] = m.group(1).lower()
            i += 1
            continue

        vm = re.match(r"^vlan\s+(\d+)\s*$", line, re.I)
        if vm:
            vid = vm.group(1)
            if vid not in ir["vlans"]:
                ir["vlans"][vid] = {"name": None}
            i += 1
            while i < len(lines):
                vl = lines[i].strip()
                if vl.lower() == "quit" or (vl and not lines[i][0:1].isspace()):
                    if vl.lower() == "quit":
                        i += 1
                    break
                nm = re.match(r"name\s+(.+)", vl, re.I)
                if nm:
                    ir["vlans"][vid]["name"] = nm.group(1).strip()
                i += 1
            continue

        ifm = re.match(r"^interface\s+(.+)", line, re.I)
        if ifm:
            if cur_iface:
                ir["interfaces"].append(cur_iface)
            cur_iface = {
                "name": ifm.group(1).strip(), "mode": "access",
                "pvid": None, "tagged_vlans": [], "description": None,
            }
            i += 1
            while i < len(lines):
                il = lines[i]
                ils = il.strip()
                if ils.lower() == "quit" or (ils and not il[0:1].isspace()):
                    if ils.lower() == "quit":
                        i += 1
                    break

                m2 = re.match(r"port link-type (\S+)", ils, re.I)
                if m2:
                    mode = m2.group(1).lower()
                    cur_iface["mode"] = mode if mode in ("trunk", "access", "hybrid") else "access"
                elif re.match(r"port access vlan (\d+)", ils, re.I):
                    cur_iface["pvid"] = re.match(r"port access vlan (\d+)", ils, re.I).group(1)
                elif re.match(r"port trunk pvid vlan (\d+)", ils, re.I):
                    cur_iface["pvid"] = re.match(r"port trunk pvid vlan (\d+)", ils, re.I).group(1)
                elif re.match(r"port trunk permit vlan (.+)", ils, re.I):
                    raw = re.match(r"port trunk permit vlan (.+)", ils, re.I).group(1).strip()
                    if raw.lower() == "all":
                        cur_iface["tagged_vlans"] = ["all"]
                    else:
                        # HP uses space-separated VLAN IDs
                        cur_iface["tagged_vlans"].extend(
                            v for v in raw.split() if v.isdigit()
                        )
                elif re.match(r"description (.+)", ils, re.I):
                    cur_iface["description"] = re.match(r"description (.+)", ils, re.I).group(1).strip()

                i += 1
            continue

        i += 1

    if cur_iface:
        ir["interfaces"].append(cur_iface)
    return ir


# ── Registry ──────────────────────────────────────────────────────────────────

_PARSERS = {
    "edgeswitch": _parse_edgeswitch,
    "dell_n":     _parse_ios_style,
    "cisco_ios":  _parse_ios_style,
    "cisco_nxos": _parse_ios_style,
    "hp_comware": _parse_hp_comware,
    "aruba":      _parse_ios_style,
}


def parse_config(vendor: str, config_text: str) -> dict[str, Any]:
    """Parse raw switch config for vendor into normalized IR. Never raises."""
    parser = _PARSERS.get(vendor)
    if parser is None:
        return {
            "hostname": None, "stp_mode": None, "vlans": {}, "interfaces": [],
            "warnings": [f"Vendor '{vendor}' não tem parser implementado"],
        }
    try:
        return parser(config_text)
    except Exception as exc:
        return {
            "hostname": None, "stp_mode": None, "vlans": {}, "interfaces": [],
            "warnings": [f"Erro no parser ({vendor}): {exc}"],
        }
