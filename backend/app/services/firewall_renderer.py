"""
Firewall rule renderer — converts normalized IR to CLI commands for the target vendor.

Supported vendors:
    fortinet   FortiOS CLI
    sonicwall  SonicOS CLI (SSH-compatible commands)
    sophos     Sophos XG CLI / REST-equivalent commands

Returns: {"commands": [str], "warnings": [str]}
"""
from __future__ import annotations

from typing import Any


# ── Helpers ───────────────────────────────────────────────────────────────────

def _q(s: str) -> str:
    """Wrap string in double quotes."""
    return f'"{s}"'


def _result(cmds: list[str], warns: list[str]) -> dict[str, Any]:
    return {"commands": cmds, "warnings": warns}


# ── Fortinet FortiOS renderer ─────────────────────────────────────────────────

def _render_fortinet(ir: dict[str, Any]) -> dict[str, Any]:
    cmds: list[str] = []
    warns: list[str] = []

    if ir.get("hostname"):
        cmds += ["config system global", f"    set hostname {_q(ir['hostname'])}", "end", ""]

    # Address objects
    addr_objs = [a for a in ir.get("address_objects", []) if a.get("type") != "group"]
    addr_grps = [a for a in ir.get("address_objects", []) if a.get("type") == "group"]

    if addr_objs:
        cmds.append("config firewall address")
        for obj in addr_objs:
            cmds.append(f"    edit {_q(obj['name'])}")
            t = obj.get("type", "network")
            val = obj.get("value", "")
            if t == "fqdn":
                cmds += ["        set type fqdn", f"        set fqdn {_q(val)}"]
            elif t == "range":
                parts = val.split("-", 1)
                cmds += ["        set type iprange",
                         f"        set start-ip {parts[0]}",
                         f"        set end-ip {parts[1] if len(parts) > 1 else parts[0]}"]
            elif t == "host":
                cmds += ["        set type ipmask", f"        set subnet {val.replace('/', ' ')} 255.255.255.255" if "/" not in val else f"        set subnet {val.split('/')[0]} 255.255.255.255"]
            else:
                # network — convert CIDR to IP mask
                if "/" in val:
                    import ipaddress
                    try:
                        net = ipaddress.IPv4Network(val, strict=False)
                        cmds += ["        set type ipmask",
                                 f"        set subnet {net.network_address} {net.netmask}"]
                    except Exception:
                        cmds += ["        set type ipmask", f"        set subnet {val}"]
                else:
                    cmds += ["        set type ipmask", f"        set subnet {val}"]
            if obj.get("comment"):
                cmds.append(f"        set comment {_q(obj['comment'])}")
            cmds.append("    next")
        cmds += ["end", ""]

    if addr_grps:
        cmds.append("config firewall addrgrp")
        for grp in addr_grps:
            cmds.append(f"    edit {_q(grp['name'])}")
            members_str = " ".join(_q(m) for m in grp.get("members", []))
            cmds.append(f"        set member {members_str}")
            cmds.append("    next")
        cmds += ["end", ""]

    # Service objects
    svc_objs = [s for s in ir.get("service_objects", []) if s.get("type") != "group"]
    svc_grps = [s for s in ir.get("service_objects", []) if s.get("type") == "group"]

    if svc_objs:
        cmds.append("config firewall service custom")
        for svc in svc_objs:
            cmds.append(f"    edit {_q(svc['name'])}")
            proto = svc.get("protocol", "any").upper()
            if proto in ("TCP", "UDP"):
                cmds.append(f"        set protocol TCP/UDP/SCTP")
                if svc.get("dst_ports"):
                    cmds.append(f"        set {proto.lower()}-portrange {' '.join(svc['dst_ports'])}")
            elif proto == "ICMP":
                cmds.append("        set protocol ICMP")
            if svc.get("comment"):
                cmds.append(f"        set comment {_q(svc['comment'])}")
            cmds.append("    next")
        cmds += ["end", ""]

    if svc_grps:
        cmds.append("config firewall service group")
        for grp in svc_grps:
            cmds.append(f"    edit {_q(grp['name'])}")
            members_str = " ".join(_q(m) for m in grp.get("members", []))
            cmds.append(f"        set member {members_str}")
            cmds.append("    next")
        cmds += ["end", ""]

    # Policies
    if ir.get("policies"):
        cmds.append("config firewall policy")
        for pol in ir["policies"]:
            cmds.append(f"    edit {pol['id']}")
            if pol.get("name"):
                cmds.append(f"        set name {_q(pol['name'])}")
            cmds.append(f"        set srcintf {' '.join(_q(z) for z in pol.get('src_zones', ['any']))}")
            cmds.append(f"        set dstintf {' '.join(_q(z) for z in pol.get('dst_zones', ['any']))}")
            cmds.append(f"        set srcaddr {' '.join(_q(a) for a in pol.get('src_addresses', ['all']))}")
            cmds.append(f"        set dstaddr {' '.join(_q(a) for a in pol.get('dst_addresses', ['all']))}")
            cmds.append(f"        set action {pol.get('action', 'deny')}")
            cmds.append(f"        set service {' '.join(_q(s) for s in pol.get('services', ['ALL']))}")
            cmds.append("        set schedule \"always\"")
            if pol.get("nat"):
                cmds.append("        set nat enable")
            if pol.get("log"):
                cmds.append("        set logtraffic all")
            if not pol.get("enabled", True):
                cmds.append("        set status disable")
            if pol.get("comment"):
                cmds.append(f"        set comments {_q(pol['comment'])}")
            cmds.append("    next")
        cmds += ["end", ""]

    # NAT rules (VIPs for DNAT)
    dnat_rules = [n for n in ir.get("nat_rules", []) if n.get("type") == "dnat"]
    if dnat_rules:
        cmds.append("config firewall vip")
        for nat in dnat_rules:
            cmds.append(f"    edit {_q(nat['name'] or 'vip-unnamed')}")
            ext_ip = nat.get("dst_addresses", [""])[0]
            cmds.append(f"        set extip {ext_ip}")
            cmds.append(f"        set extintf any")
            cmds.append(f"        set mappedip {_q(nat.get('translated_dst', ''))}")
            if nat.get("translated_port"):
                cmds.append(f"        set mappedport {nat['translated_port']}")
            cmds.append("    next")
        cmds += ["end", ""]

    # Static routes
    if ir.get("static_routes"):
        cmds.append("config router static")
        for i, route in enumerate(ir["static_routes"], start=1):
            cmds.append(f"    edit {i}")
            import ipaddress as _ip
            net_str = route.get("network", "0.0.0.0/0")
            try:
                net = _ip.IPv4Network(net_str, strict=False)
                cmds.append(f"        set dst {net.network_address} {net.netmask}")
            except Exception:
                cmds.append(f"        set dst {net_str}")
            cmds.append(f"        set gateway {route.get('gateway', '')}")
            if route.get("interface"):
                cmds.append(f"        set device {_q(route['interface'])}")
            if route.get("metric"):
                cmds.append(f"        set distance {route['metric']}")
            cmds.append("    next")
        cmds += ["end", ""]

    return _result(cmds, warns)


# ── SonicWall SonicOS renderer ────────────────────────────────────────────────

def _render_sonicwall(ir: dict[str, Any]) -> dict[str, Any]:
    cmds: list[str] = []
    warns: list[str] = []

    if ir.get("hostname"):
        cmds += [f"config system hostname {_q(ir['hostname'])}", ""]

    # Address objects
    for obj in ir.get("address_objects", []):
        name = obj["name"]
        t = obj.get("type", "network")
        val = obj.get("value", "")
        if t == "group":
            cmds.append(f"address-object group {_q(name)}")
            for m in obj.get("members", []):
                cmds.append(f"  address-object {_q(m)}")
            cmds += ["exit", ""]
        elif t == "host":
            cmds += [f"address-object ipv4 {_q(name)} host {val}", ""]
        elif t == "network":
            if "/" in val:
                import ipaddress
                try:
                    net = ipaddress.IPv4Network(val, strict=False)
                    cmds += [f"address-object ipv4 {_q(name)} subnet {net.network_address}/{net.prefixlen}", ""]
                except Exception:
                    cmds += [f"address-object ipv4 {_q(name)} subnet {val}", ""]
            else:
                cmds += [f"address-object ipv4 {_q(name)} host {val}", ""]
        elif t == "range":
            parts = val.split("-", 1)
            cmds += [f"address-object ipv4 {_q(name)} range {parts[0]} {parts[1] if len(parts) > 1 else parts[0]}", ""]
        elif t == "fqdn":
            cmds += [f"address-object fqdn {_q(name)} {_q(val)}", ""]
        else:
            warns.append(f"Objeto de endereço '{name}' com tipo desconhecido '{t}' — ignorado")

    # Service objects
    for svc in ir.get("service_objects", []):
        name = svc["name"]
        if svc.get("type") == "group":
            cmds.append(f"service-object group {_q(name)}")
            for m in svc.get("members", []):
                cmds.append(f"  service-object {_q(m)}")
            cmds += ["exit", ""]
        else:
            proto = svc.get("protocol", "tcp").upper()
            ports = svc.get("dst_ports", [])
            port_str = ports[0] if ports else "0"
            cmds += [f"service-object {_q(name)} {proto} {port_str}", ""]

    # Policies (access rules)
    for pol in ir.get("policies", []):
        src_zone = pol.get("src_zones", ["any"])[0]
        dst_zone = pol.get("dst_zones", ["any"])[0]
        src_addr = pol.get("src_addresses", ["any"])[0]
        dst_addr = pol.get("dst_addresses", ["any"])[0]
        svc = pol.get("services", ["any"])[0]
        action_map = {"accept": "allow", "deny": "deny", "drop": "discard"}
        action = action_map.get(pol.get("action", "deny"), "deny")
        cmds += [
            f"access-rule ipv4 {_q(src_zone)} {_q(dst_zone)} {action}",
            f"  source address {_q(src_addr)}",
            f"  destination address {_q(dst_addr)}",
            f"  service {_q(svc)}",
        ]
        if pol.get("comment"):
            cmds.append(f"  comment {_q(pol['comment'])}")
        cmds += ["exit", ""]

    # NAT policies
    for nat in ir.get("nat_rules", []):
        src_addr = nat.get("src_addresses", ["any"])[0]
        dst_addr = nat.get("dst_addresses", ["any"])[0]
        svc = nat.get("services", ["any"])[0]
        if nat.get("type") == "dnat":
            cmds += [
                f"nat-policy",
                f"  original-source {_q(src_addr)}",
                f"  original-destination {_q(dst_addr)}",
                f"  original-service {_q(svc)}",
                f"  translated-destination {_q(nat.get('translated_dst',''))}",
                "exit", "",
            ]
        else:
            cmds += [
                f"nat-policy",
                f"  original-source {_q(src_addr)}",
                f"  translated-source {_q(nat.get('translated_src',''))}",
                "exit", "",
            ]

    # Static routes
    for route in ir.get("static_routes", []):
        cmds += [f"ip route {route.get('network','')} {route.get('gateway','')} {route.get('metric',1)}", ""]

    return _result(cmds, warns)


# ── Sophos XG/XGS renderer ───────────────────────────────────────────────────

def _render_sophos(ir: dict[str, Any]) -> dict[str, Any]:
    cmds: list[str] = []
    warns: list[str] = []

    cmds.append("! Sophos XG — comandos CLI equivalentes (revisar antes de aplicar)")
    cmds.append("")

    if ir.get("hostname"):
        cmds += [f"set hostname {_q(ir['hostname'])}", ""]

    # Hosts / Networks
    for obj in ir.get("address_objects", []):
        name = obj["name"]
        t = obj.get("type", "network")
        val = obj.get("value", "")
        if t == "group":
            cmds.append(f"object host-group {_q(name)}")
            for m in obj.get("members", []):
                cmds.append(f"  member {_q(m)}")
            cmds += ["exit", ""]
        elif t == "host":
            cmds += [f"object host {_q(name)} ip-address {val}", ""]
        elif t == "network":
            if "/" in val:
                import ipaddress
                try:
                    net = ipaddress.IPv4Network(val, strict=False)
                    cmds += [f"object network {_q(name)} subnet {net.network_address} {net.netmask}", ""]
                except Exception:
                    cmds += [f"object network {_q(name)} subnet {val}", ""]
            else:
                cmds += [f"object host {_q(name)} ip-address {val}", ""]
        elif t == "range":
            parts = val.split("-", 1)
            cmds += [f"object host {_q(name)} ip-range {parts[0]} {parts[1] if len(parts) > 1 else parts[0]}", ""]
        elif t == "fqdn":
            cmds += [f"object host {_q(name)} fqdn {_q(val)}", ""]

    # Services
    for svc in ir.get("service_objects", []):
        name = svc["name"]
        if svc.get("type") == "group":
            cmds.append(f"object service-group {_q(name)}")
            for m in svc.get("members", []):
                cmds.append(f"  member {_q(m)}")
            cmds += ["exit", ""]
        else:
            proto = svc.get("protocol", "tcp").upper()
            ports = svc.get("dst_ports", ["any"])
            cmds += [f"object service {_q(name)} protocol {proto} dst-port {' '.join(ports)}", ""]

    # Firewall rules
    for pol in ir.get("policies", []):
        action_map = {"accept": "accept", "deny": "drop", "drop": "drop"}
        action = action_map.get(pol.get("action", "drop"), "drop")
        src_zone = (pol.get("src_zones") or ["any"])[0]
        dst_zone = (pol.get("dst_zones") or ["any"])[0]
        cmds += [
            f"firewall-rule {_q(pol.get('name') or pol['id'])}",
            f"  action {action}",
            f"  source-zone {_q(src_zone)}",
            f"  dest-zone {_q(dst_zone)}",
            f"  source-network {_q((pol.get('src_addresses') or ['any'])[0])}",
            f"  dest-network {_q((pol.get('dst_addresses') or ['any'])[0])}",
            f"  service {_q((pol.get('services') or ['any'])[0])}",
        ]
        if pol.get("log"):
            cmds.append("  log enable")
        if not pol.get("enabled", True):
            cmds.append("  status disable")
        cmds += ["exit", ""]

    # NAT rules
    for nat in ir.get("nat_rules", []):
        nat_type = nat.get("type", "snat")
        cmds += [
            f"nat-rule {_q(nat.get('name','nat-rule'))}",
            f"  nat-type {nat_type.upper()}",
            f"  original-source {_q((nat.get('src_addresses') or ['any'])[0])}",
            f"  original-dest {_q((nat.get('dst_addresses') or ['any'])[0])}",
        ]
        if nat.get("translated_src"):
            cmds.append(f"  translated-source {_q(nat['translated_src'])}")
        if nat.get("translated_dst"):
            cmds.append(f"  translated-dest {_q(nat['translated_dst'])}")
        cmds += ["exit", ""]

    # Static routes
    for route in ir.get("static_routes", []):
        cmds += [f"ip-route {route.get('network','')} gateway {route.get('gateway','')} distance {route.get('metric',1)}", ""]

    return _result(cmds, warns)


# ── Registry ──────────────────────────────────────────────────────────────────

_RENDERERS: dict[str, Any] = {
    "fortinet":  _render_fortinet,
    "sonicwall": _render_sonicwall,
    "sophos":    _render_sophos,
}


def render_firewall_rules(ir: dict[str, Any], target_vendor: str) -> dict[str, Any]:
    """Render CLI commands for target_vendor from normalized firewall IR. Never raises."""
    renderer = _RENDERERS.get(target_vendor)
    if renderer is None:
        return {"commands": [], "warnings": [f"Vendor '{target_vendor}' não tem renderer de regras implementado"]}
    try:
        return renderer(ir)
    except Exception as exc:
        return {"commands": [], "warnings": [f"Erro no renderer ({target_vendor}): {exc}"]}
