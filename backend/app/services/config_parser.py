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
            "members":      [str],         # physical port names in this LAG ([] for non-LAG)
            "lag_member_of": str | None,   # LAG interface name if this is a member port
            "lag_mode":     str | None,    # "active"|"passive"|"on" (LACP mode from source)
        }, ...
    ],
    "warnings":   [str],
}
"""
from __future__ import annotations

import re
from typing import Any


# ── LAG helpers ──────────────────────────────────────────────────────────────

_LAG_IFACE_RE = re.compile(
    r"^(lag|port-channel|port\s+channel|bridge-aggregation|aggregation|ae)\s*\d+$",
    re.I,
)


def _is_lag_iface(name: str) -> bool:
    """True if the interface name represents a LAG/port-channel/bridge-aggregation."""
    return bool(_LAG_IFACE_RE.match(name.strip()))


def _normalize_lag_key(name: str) -> str:
    """Normalize LAG name for index lookup — collapse spaces, lowercase.

    Handles mismatches like 'Port-Channel1' vs 'port-channel 1'
    or 'Bridge-Aggregation1' vs 'bridge-aggregation 1'.
    """
    return re.sub(r"\s+", "", name.lower())


def _build_lag_members(interfaces: list[dict]) -> None:
    """
    Post-process interface list to link member ports to their LAG.

    Reads temporary _lag_member_of / _lag_mode keys set during parsing, removes
    them, and populates the stable IR fields:
      - iface["lag_member_of"] = "lag 1" / "port-channel 1" / …
      - lag_iface["members"].append(port_name)
      - lag_iface["lag_mode"] = "active" / "passive" / "on"
    """
    # Index LAG interfaces by normalized key (no spaces, lowercase)
    lag_by_key: dict[str, dict] = {}
    for iface in interfaces:
        iface.setdefault("members", [])
        iface.setdefault("lag_member_of", None)
        if _is_lag_iface(iface["name"]):
            lag_by_key[_normalize_lag_key(iface["name"])] = iface

    for iface in interfaces:
        lag_ref = iface.pop("_lag_member_of", None)
        lag_mode = iface.pop("_lag_mode", None)
        if not lag_ref:
            # Juniper (and others) may set lag_mode on the LAG interface itself
            if lag_mode:
                iface["lag_mode"] = lag_mode
            continue
        iface["lag_member_of"] = lag_ref
        if lag_mode:
            iface["lag_mode"] = lag_mode
        # Normalize lookup: "port-channel 1" → "port-channel1" matches "Port-Channel1"
        lag_iface = lag_by_key.get(_normalize_lag_key(lag_ref))
        if lag_iface:
            if iface["name"] not in lag_iface["members"]:
                lag_iface["members"].append(iface["name"])
            if lag_mode and "lag_mode" not in lag_iface:
                lag_iface["lag_mode"] = lag_mode


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

        # Interface block — capture full name (handles "interface lag 1", "interface vlan 10", etc.)
        ifm = re.match(r"^interface\s+(.+)", line, re.I)
        if ifm:
            if cur_iface:
                ir["interfaces"].append(_finalize_iface(cur_iface))
            cur_iface = {
                "name": ifm.group(1).strip(), "mode": "access",
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

                # EdgeSwitch LAG membership: "lag 1" alone on a line inside a physical port block
                m_lag = re.match(r"^lag\s+(\d+)$", ils, re.I)
                if m_lag:
                    cur_iface["_lag_member_of"] = f"lag {m_lag.group(1)}"
                # IOS-style switchport
                elif re.match(r"switchport mode (\S+)", ils, re.I):
                    cur_iface["mode"] = re.match(r"switchport mode (\S+)", ils, re.I).group(1).lower()
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

    _build_lag_members(ir["interfaces"])
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

        # Interface block — full name capture
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

                # LAG membership: "channel-group 1 mode active" / "channel-group 1"
                m_lag = re.match(r"channel-group\s+(\d+)(?:\s+mode\s+(\S+))?", ils, re.I)
                if m_lag:
                    cur_iface["_lag_member_of"] = f"port-channel {m_lag.group(1)}"
                    cur_iface["_lag_mode"] = (m_lag.group(2) or "on").lower()
                elif re.match(r"switchport mode (\S+)", ils, re.I):
                    cur_iface["mode"] = re.match(r"switchport mode (\S+)", ils, re.I).group(1).lower()
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
    _build_lag_members(ir["interfaces"])
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

                # LAG membership: "port link-aggregation group 1"
                m_lag = re.match(r"port link-aggregation group\s+(\d+)", ils, re.I)
                if m_lag:
                    cur_iface["_lag_member_of"] = f"bridge-aggregation {m_lag.group(1)}"
                elif re.match(r"port link-type (\S+)", ils, re.I):
                    mode = re.match(r"port link-type (\S+)", ils, re.I).group(1).lower()
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
    _build_lag_members(ir["interfaces"])
    return ir


# ── Juniper EX parser ─────────────────────────────────────────────────────────

def _parse_juniper(config: str) -> dict[str, Any]:
    """Parse Juniper EX 'show configuration' hierarchical { } format."""
    ir: dict[str, Any] = {
        "hostname": None, "stp_mode": None,
        "vlans": {}, "interfaces": [], "warnings": [],
    }
    vlan_name_to_id: dict[str, str] = {}

    def _get_or_create(name: str) -> dict:
        for iface in ir["interfaces"]:
            if iface["name"] == name:
                return iface
        entry: dict = {
            "name": name, "mode": "access",
            "pvid": None, "tagged_vlans": [], "description": None,
            "members": [], "lag_member_of": None,
        }
        ir["interfaces"].append(entry)
        return entry

    path: list[str] = []

    for raw in config.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("/*"):
            continue
        # Strip inline Juniper comments (## ...)
        line = re.sub(r"\s+##.*$", "", line).strip()
        if not line:
            continue

        if line.endswith("{"):
            path.append(line[:-1].strip())
            continue
        if line == "}":
            if path:
                path.pop()
            continue
        if not line.endswith(";"):
            continue

        leaf = line[:-1].strip()
        depth = len(path)

        # system { host-name X; }
        if depth >= 1 and path[0] == "system":
            if leaf.startswith("host-name "):
                ir["hostname"] = leaf.split(None, 1)[1].strip().strip('"')

        # vlans { NAME { vlan-id X; } }
        elif depth >= 2 and path[0] == "vlans":
            vname = path[1]
            if leaf.startswith("vlan-id "):
                vid = leaf.split(None, 1)[1].strip()
                ir["vlans"].setdefault(vid, {"name": None})
                ir["vlans"][vid]["name"] = vname
                vlan_name_to_id[vname.lower()] = vid

        # interfaces { IFACE { ... } }
        elif depth >= 2 and path[0] == "interfaces":
            iface_name = path[1]

            # Top-level description
            if depth == 2 and leaf.startswith("description "):
                _get_or_create(iface_name)["description"] = leaf.split(None, 1)[1].strip().strip('"')

            # LAG member: ether-options { 802.3ad aeX; }
            elif depth == 3 and path[2] == "ether-options" and leaf.startswith("802.3ad "):
                _get_or_create(iface_name)["_lag_member_of"] = leaf.split(None, 1)[1].strip()

            # LACP mode: aggregated-ether-options { lacp { active; } }
            elif (depth == 4 and path[2] == "aggregated-ether-options"
                  and path[3] == "lacp" and leaf in ("active", "passive")):
                _get_or_create(iface_name)["_lag_mode"] = leaf

            # unit 0 > family ethernet-switching
            elif (depth == 4 and path[2].startswith("unit")
                  and path[3] == "family ethernet-switching"):
                entry = _get_or_create(iface_name)
                if leaf.startswith("interface-mode "):
                    mode = leaf.split(None, 1)[1].strip()
                    entry["mode"] = mode if mode in ("trunk", "access") else "access"
                elif leaf.startswith("native-vlan-id "):
                    entry["pvid"] = leaf.split(None, 1)[1].strip()
                elif leaf.startswith("description "):
                    entry["description"] = leaf.split(None, 1)[1].strip().strip('"')

            # unit 0 > family ethernet-switching > vlan { members ...; }
            elif (depth == 5 and path[2].startswith("unit")
                  and path[3] == "family ethernet-switching"
                  and path[4] == "vlan" and leaf.startswith("members ")):
                entry = _get_or_create(iface_name)
                raw_m = leaf.split(None, 1)[1].strip().strip("[]").strip()
                for token in raw_m.split():
                    vid = token if token.isdigit() else vlan_name_to_id.get(token.lower(), token)
                    if vid.isdigit() and vid not in entry["tagged_vlans"]:
                        entry["tagged_vlans"].append(vid)

    # Access ports: move single tagged VLAN to pvid
    for iface in ir["interfaces"]:
        if iface["mode"] == "access" and iface["tagged_vlans"] and iface["pvid"] is None:
            iface["pvid"] = iface["tagged_vlans"][0]
            iface["tagged_vlans"] = []

    _build_lag_members(ir["interfaces"])
    return ir


# ── Aruba ArubaOS-Switch parser ───────────────────────────────────────────────

def _parse_aruba(config: str) -> dict[str, Any]:
    """Parse ArubaOS-Switch (ProCurve) VLAN-centric config format."""
    ir: dict[str, Any] = {
        "hostname": None, "stp_mode": None,
        "vlans": {}, "interfaces": [], "warnings": [],
    }
    port_vlan_tagged: dict[str, list[str]] = {}
    port_vlan_untagged: dict[str, list[str]] = {}
    trunk_defs: dict[str, dict] = {}    # "trk1" → {"members":[], "mode": "active"}
    descriptions: dict[str, str] = {}

    def _aruba_ports(spec: str) -> list[str]:
        ports: list[str] = []
        for part in spec.replace(" ", "").split(","):
            if "-" in part:
                lo, hi = part.split("-", 1)
                if lo.isdigit() and hi.isdigit():
                    ports.extend(str(p) for p in range(int(lo), int(hi) + 1))
                else:
                    ports.append(part)
            elif part:
                ports.append(part)
        return ports

    lines = config.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            i += 1
            continue

        if line.lower().startswith("hostname "):
            ir["hostname"] = line.split(None, 1)[1].strip().strip('"')
            i += 1
            continue

        m = re.match(r"spanning-tree\s+(\S+)", line, re.I)
        if m:
            ir["stp_mode"] = m.group(1).lower()
            i += 1
            continue

        # trunk PORT_LIST TRKID [lacp|trunk]
        m = re.match(r"^trunk\s+([\w,\-]+)\s+(trk\d+)(?:\s+(\S+))?", line, re.I)
        if m:
            members = _aruba_ports(m.group(1))
            trk_id = m.group(2).lower()
            mode_raw = (m.group(3) or "").lower()
            trunk_defs[trk_id] = {
                "members": members,
                "mode": "active" if mode_raw == "lacp" else "on",
            }
            i += 1
            continue

        # VLAN block
        vm = re.match(r"^vlan\s+(\d+)\s*$", line, re.I)
        if vm:
            vid = vm.group(1)
            ir["vlans"].setdefault(vid, {"name": None})
            i += 1
            while i < len(lines):
                vl = lines[i].strip()
                if not vl or vl == "!":
                    i += 1
                    break
                if lines[i] and not lines[i][0:1].isspace():
                    break
                nm = re.match(r'name\s+"?(.+?)"?\s*$', vl, re.I)
                if nm:
                    ir["vlans"][vid]["name"] = nm.group(1).strip().strip('"')
                tm = re.match(r"tagged\s+([\w,\-]+)", vl, re.I)
                if tm:
                    for port in _aruba_ports(tm.group(1)):
                        port_vlan_tagged.setdefault(port.lower(), []).append(vid)
                um = re.match(r"untagged\s+([\w,\-]+)", vl, re.I)
                if um:
                    for port in _aruba_ports(um.group(1)):
                        port_vlan_untagged.setdefault(port.lower(), []).append(vid)
                i += 1
            continue

        # Interface block (descriptions)
        ifm = re.match(r"^interface\s+(.+)", line, re.I)
        if ifm:
            iname = ifm.group(1).strip().lower()
            i += 1
            while i < len(lines):
                il = lines[i].strip()
                if not il or il == "!":
                    i += 1
                    break
                if lines[i] and not lines[i][0:1].isspace():
                    break
                nm = re.match(r'name\s+"?(.+?)"?\s*$', il, re.I)
                if nm:
                    descriptions[iname] = nm.group(1).strip().strip('"')
                i += 1
            continue

        i += 1

    # LAG member port names — excluded from standalone interface list
    lag_members: set[str] = {m.lower() for td in trunk_defs.values() for m in td["members"]}

    # Regular ports from VLAN data
    all_ports = (set(port_vlan_tagged) | set(port_vlan_untagged)) - lag_members - set(trunk_defs)

    def _port_key(p: str) -> tuple:
        return (0, int(p), "") if p.isdigit() else (1, 0, p)

    for port in sorted(all_ports, key=_port_key):
        vt = sorted(set(port_vlan_tagged.get(port, [])), key=lambda v: int(v) if v.isdigit() else 9999)
        vu = port_vlan_untagged.get(port, [])
        ir["interfaces"].append({
            "name": port, "mode": "trunk" if vt else "access",
            "pvid": vu[0] if vu else None, "tagged_vlans": vt,
            "description": descriptions.get(port), "members": [], "lag_member_of": None,
        })

    # LAG interfaces + member entries
    for trk_id, trk_info in sorted(trunk_defs.items()):
        vt = sorted(set(port_vlan_tagged.get(trk_id, [])), key=lambda v: int(v) if v.isdigit() else 9999)
        vu = port_vlan_untagged.get(trk_id, [])
        ir["interfaces"].append({
            "name": trk_id, "mode": "trunk" if vt else "access",
            "pvid": vu[0] if vu else None, "tagged_vlans": vt,
            "description": descriptions.get(trk_id),
            "members": trk_info["members"], "lag_member_of": None,
            "lag_mode": trk_info["mode"],
        })
        for member in trk_info["members"]:
            ir["interfaces"].append({
                "name": member, "mode": "access", "pvid": None, "tagged_vlans": [],
                "description": descriptions.get(member.lower()),
                "members": [], "lag_member_of": trk_id, "lag_mode": trk_info["mode"],
            })

    return ir


# ── Intelbras SG parser ───────────────────────────────────────────────────────
# Intelbras SG series uses Cisco IOS-compatible syntax — reuse _parse_ios_style.
_parse_intelbras = _parse_ios_style


# ── L3 interface extraction ───────────────────────────────────────────────────

def _cidr_to_mask(prefix: int) -> str:
    """Convert CIDR prefix length to dotted-decimal netmask (e.g. 24 → '255.255.255.0')."""
    bits = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
    return ".".join(str((bits >> (8 * i)) & 0xFF) for i in [3, 2, 1, 0])


def _extract_l3_interfaces(config: str) -> list[dict]:
    """Extract VLAN L3 interface IP addresses from any vendor raw config.

    Handles:
      EdgeSwitch / IOS:  interface vlan 100  →  ip address 10.0.0.1/24
      HP Comware:        interface Vlan-interface 100  →  ip address 10.0.0.1 255.255.255.0
    Returns list of {"vlan_id": str, "ip": str, "mask": str}.
    """
    result: list[dict] = []
    seen: set[str] = set()
    lines = config.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        vlan_m = re.match(
            r"^interface\s+(?:vlan[-\s]?interface\s*|vlan\s*)(\d+)",
            line, re.IGNORECASE,
        )
        if vlan_m:
            vid = vlan_m.group(1)
            i += 1
            while i < len(lines):
                il = lines[i]
                ils = il.strip()
                if ils.lower() in ("quit", "exit", "!") or (ils and not il[:1].isspace()):
                    break
                ip_m = re.match(
                    r"ip\s+address\s+([\d.]+)(?:/(\d+)|[ ]+([\d.]+))",
                    ils, re.IGNORECASE,
                )
                if ip_m:
                    ip = ip_m.group(1)
                    mask = _cidr_to_mask(int(ip_m.group(2))) if ip_m.group(2) else ip_m.group(3)
                    key = f"{vid}:{ip}"
                    if key not in seen:
                        seen.add(key)
                        result.append({"vlan_id": vid, "ip": ip, "mask": mask})
                i += 1
            continue
        i += 1
    return result


# ── Port type inference ───────────────────────────────────────────────────────

def _infer_port_types(vendor: str, interfaces: list[dict]) -> None:
    """Stamp port_type on each interface: 'ethernet' | 'fiber' | 'lag' | 'vlan'."""
    for iface in interfaces:
        name = iface["name"]
        n = name.lower().strip()

        if _is_lag_iface(name):
            iface["port_type"] = "lag"
            continue

        # Juniper ae (aggregated ethernet) is a LAG
        if re.match(r"^ae\d", n):
            iface["port_type"] = "lag"
            continue

        # VLAN / loopback / management — non-switching interfaces
        if re.match(r"^(vlan|loopback|loop\s*back|mgmt|management|irb|null|me)\d*\b", n):
            iface["port_type"] = "vlan"
            continue

        if vendor in ("cisco_ios", "cisco_nxos", "dell_n", "intelbras"):
            if re.match(r"^(tengigabit|te\s*\d|hundredgige|fortygig|25gig)", n):
                iface["port_type"] = "fiber"
            else:
                iface["port_type"] = "ethernet"

        elif vendor == "hp_comware":
            if re.match(r"^ten-gigabitethernet|^xgigabitethernet|^40g", n):
                iface["port_type"] = "fiber"
            else:
                iface["port_type"] = "ethernet"

        elif vendor == "juniper":
            if re.match(r"^(xe|et|xle|fte)-", n):
                iface["port_type"] = "fiber"
            else:
                iface["port_type"] = "ethernet"

        elif vendor == "aruba":
            iface["port_type"] = "ethernet"

        elif vendor == "edgeswitch":
            # Physical ports have no type hint in name — revised below
            iface["port_type"] = "ethernet"

        else:
            iface["port_type"] = "ethernet"

    # EdgeSwitch: last 2 sequential 0/X physical ports are SFP fiber
    if vendor == "edgeswitch":
        physical = [
            i for i in interfaces
            if re.match(r"^\d+/\d+$", i["name"]) and i.get("port_type") == "ethernet"
        ]
        try:
            physical_sorted = sorted(physical, key=lambda i: int(i["name"].split("/")[-1]))
            if len(physical_sorted) >= 3:
                for iface in physical_sorted[-2:]:
                    iface["port_type"] = "fiber"
        except (ValueError, IndexError):
            pass


# ── Registry ──────────────────────────────────────────────────────────────────

_PARSERS = {
    "edgeswitch": _parse_edgeswitch,
    "dell_n":     _parse_ios_style,
    "cisco_ios":  _parse_ios_style,
    "cisco_nxos": _parse_ios_style,
    "hp_comware": _parse_hp_comware,
    "aruba":      _parse_aruba,
    "juniper":    _parse_juniper,
    "intelbras":  _parse_intelbras,
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
        ir = parser(config_text)
        _infer_port_types(vendor, ir.get("interfaces", []))
        ir["l3_interfaces"] = _extract_l3_interfaces(config_text)
        return ir
    except Exception as exc:
        return {
            "hostname": None, "stp_mode": None, "vlans": {}, "interfaces": [],
            "warnings": [f"Erro no parser ({vendor}): {exc}"],
        }
