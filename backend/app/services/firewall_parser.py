"""
Firewall rule parser — converts raw config/JSON to normalized IR for Fase 16 migration.

Supported vendors:
    fortinet   FortiOS (from 'show full-configuration' SSH output)
    sonicwall  SonicOS (from REST API JSON export)
    sophos     Sophos XG/XGS (from REST API JSON export)

IR structure:
{
    "hostname": str | None,
    "address_objects": [
        {
            "name":    str,
            "type":    "host" | "network" | "fqdn" | "range" | "group",
            "value":   str,       # CIDR, IP, FQDN, or "start-end" for range
            "members": [str],     # for group type
            "comment": str,
        }
    ],
    "service_objects": [
        {
            "name":      str,
            "type":      "service" | "group",
            "protocol":  "tcp" | "udp" | "icmp" | "any",
            "dst_ports": [str],   # e.g. ["80", "443", "8080-8090"]
            "members":   [str],   # for group type
            "comment":   str,
        }
    ],
    "policies": [
        {
            "id":            str,
            "name":          str,
            "action":        "accept" | "deny" | "drop",
            "src_zones":     [str],
            "dst_zones":     [str],
            "src_addresses": [str],
            "dst_addresses": [str],
            "services":      [str],
            "nat":           bool,
            "log":           bool,
            "enabled":       bool,
            "comment":       str,
        }
    ],
    "nat_rules": [
        {
            "name":            str,
            "type":            "snat" | "dnat" | "masquerade",
            "src_addresses":   [str],
            "dst_addresses":   [str],
            "services":        [str],
            "translated_src":  str | None,
            "translated_dst":  str | None,
            "translated_port": str | None,
            "enabled":         bool,
            "comment":         str,
        }
    ],
    "static_routes": [
        {
            "network":   str,       # CIDR
            "gateway":   str,
            "interface": str | None,
            "metric":    int,
            "enabled":   bool,
        }
    ],
    "warnings": [str],
}
"""
from __future__ import annotations

import ipaddress
import json
import re
from typing import Any


# ── Helpers ───────────────────────────────────────────────────────────────────

def _empty_ir() -> dict[str, Any]:
    return {
        "hostname": None,
        "address_objects": [],
        "service_objects": [],
        "policies": [],
        "nat_rules": [],
        "static_routes": [],
        "warnings": [],
    }


def _ip_mask_to_cidr(ip: str, mask: str) -> str:
    try:
        net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
        return str(net)
    except Exception:
        return f"{ip}/{mask}"


def _parse_multi_quoted(val: str) -> list[str]:
    """Extract space-separated double-quoted tokens: '"a" "b"' → ['a', 'b']."""
    items = re.findall(r'"([^"]+)"', val)
    return items if items else [v for v in val.split() if v]


# ── Fortinet FortiOS parser ───────────────────────────────────────────────────

def _parse_fortinet(config: str) -> dict[str, Any]:
    """Parse FortiOS 'show full-configuration' CLI text."""
    ir = _empty_ir()

    # Stack-based parser for config/edit/set/next/end blocks
    section_stack: list[str] = []
    current_entry: dict[str, str] = {}
    current_section: str = ""

    def _flush(section: str, entry: dict) -> None:
        if not entry:
            return
        name = entry.get("_name", "")

        if section == "system global":
            if "hostname" in entry:
                ir["hostname"] = entry["hostname"]

        elif section == "firewall address":
            obj = _fortinet_addr(name, entry)
            ir["address_objects"].append(obj)

        elif section == "firewall addrgrp":
            members = _parse_multi_quoted(entry.get("member", ""))
            ir["address_objects"].append({
                "name": name, "type": "group", "value": "",
                "members": members, "comment": entry.get("comment", ""),
            })

        elif section == "firewall service custom":
            svc = _fortinet_service(name, entry)
            ir["service_objects"].append(svc)

        elif section == "firewall service group":
            members = _parse_multi_quoted(entry.get("member", ""))
            ir["service_objects"].append({
                "name": name, "type": "group", "protocol": "any",
                "dst_ports": [], "members": members, "comment": entry.get("comment", ""),
            })

        elif section == "firewall policy":
            ir["policies"].append(_fortinet_policy(name, entry))

        elif section == "firewall vip":
            ir["nat_rules"].append(_fortinet_vip(name, entry))

        elif section == "firewall ippool":
            pass  # referenced by policy nat_pool; no direct IR entry needed

        elif section == "router static":
            ir["static_routes"].append(_fortinet_route(entry))

    for raw in config.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("config "):
            section_stack.append(line[7:].strip())
            current_section = " ".join(section_stack)
            continue

        if line == "end":
            _flush(current_section, current_entry)
            current_entry = {}
            if section_stack:
                section_stack.pop()
            current_section = " ".join(section_stack)
            continue

        if line.startswith("edit "):
            _flush(current_section, current_entry)
            current_entry = {"_name": line[5:].strip().strip('"')}
            continue

        if line == "next":
            _flush(current_section, current_entry)
            current_entry = {}
            continue

        if line.startswith("set "):
            parts = line[4:].split(None, 1)
            if parts:
                key = parts[0]
                val = parts[1] if len(parts) > 1 else ""
                # Strip surrounding quotes for single-quoted values
                if val.startswith('"') and val.endswith('"') and val.count('"') == 2:
                    val = val[1:-1]
                current_entry[key] = val

    return ir


def _fortinet_addr(name: str, entry: dict) -> dict:
    addr_type = entry.get("type", "ipmask")
    obj: dict[str, Any] = {
        "name": name, "type": "network", "value": "", "members": [],
        "comment": entry.get("comment", ""),
    }
    if addr_type == "fqdn":
        obj["type"] = "fqdn"
        obj["value"] = entry.get("fqdn", "")
    elif addr_type == "iprange":
        obj["type"] = "range"
        obj["value"] = f"{entry.get('start-ip','')}-{entry.get('end-ip','')}"
    else:
        subnet = entry.get("subnet", "").split()
        if len(subnet) == 2:
            cidr = _ip_mask_to_cidr(subnet[0], subnet[1])
            try:
                net = ipaddress.IPv4Network(cidr, strict=False)
                obj["type"] = "host" if net.prefixlen == 32 else "network"
            except Exception:
                pass
            obj["value"] = cidr
        else:
            obj["value"] = entry.get("subnet", "")
    return obj


def _fortinet_service(name: str, entry: dict) -> dict:
    proto_map = {"6": "tcp", "17": "udp", "1": "icmp", "0": "any"}
    proto_raw = entry.get("protocol", "TCP/UDP/SCTP").upper()
    if proto_raw in ("TCP/UDP/SCTP", "TCP"):
        proto = "tcp"
    elif proto_raw == "UDP":
        proto = "udp"
    elif proto_raw == "ICMP":
        proto = "icmp"
    else:
        proto = proto_map.get(proto_raw, "any")

    dst_ports: list[str] = []
    for key in ("tcp-portrange", "udp-portrange"):
        if key in entry:
            # format: "80 443 8080-8090"
            dst_ports.extend(entry[key].split())

    return {
        "name": name, "type": "service", "protocol": proto,
        "dst_ports": dst_ports, "members": [],
        "comment": entry.get("comment", ""),
    }


def _fortinet_policy(name: str, entry: dict) -> dict:
    action_map = {"accept": "accept", "deny": "deny", "drop": "drop"}
    return {
        "id": name,
        "name": entry.get("name", ""),
        "action": action_map.get(entry.get("action", "deny"), "deny"),
        "src_zones":     _parse_multi_quoted(entry.get("srcintf", "")),
        "dst_zones":     _parse_multi_quoted(entry.get("dstintf", "")),
        "src_addresses": _parse_multi_quoted(entry.get("srcaddr", "")),
        "dst_addresses": _parse_multi_quoted(entry.get("dstaddr", "")),
        "services":      _parse_multi_quoted(entry.get("service", "")),
        "nat":     entry.get("nat", "disable") == "enable",
        "log":     entry.get("logtraffic", "disable") not in ("disable", ""),
        "enabled": entry.get("status", "enable") == "enable",
        "comment": entry.get("comments", ""),
    }


def _fortinet_vip(name: str, entry: dict) -> dict:
    return {
        "name": name, "type": "dnat",
        "src_addresses": ["all"],
        "dst_addresses": [entry.get("extip", "")],
        "services": [f"port:{entry['extport']}"] if entry.get("extport") else [],
        "translated_src": None,
        "translated_dst": entry.get("mappedip", ""),
        "translated_port": entry.get("mappedport", None),
        "enabled": True,
        "comment": entry.get("comment", ""),
    }


def _fortinet_route(entry: dict) -> dict:
    dst = entry.get("dst", "0.0.0.0 0.0.0.0")
    parts = dst.split()
    if len(parts) == 2:
        network = _ip_mask_to_cidr(parts[0], parts[1])
    else:
        network = dst
    return {
        "network": network,
        "gateway": entry.get("gateway", ""),
        "interface": entry.get("device", ""),
        "metric": int(entry.get("distance", "0") or "0"),
        "enabled": True,
    }


# ── SonicWall SonicOS parser (from REST JSON export) ─────────────────────────

def _parse_sonicwall(raw_json: str) -> dict[str, Any]:
    """Parse SonicWall REST API JSON export into normalized IR.

    The raw_json should be a dict with keys like 'address_objects',
    'address_groups', 'service_objects', 'service_groups',
    'access_rules', 'nat_policies', 'routing'.
    """
    ir = _empty_ir()

    try:
        data = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
    except Exception as exc:
        ir["warnings"].append(f"SonicWall: falha ao decodificar JSON de origem: {exc}")
        return ir

    # Address objects
    for ao in data.get("address_objects", []):
        obj = _sw_addr_obj(ao)
        if obj:
            ir["address_objects"].append(obj)

    # Address groups
    for ag in data.get("address_groups", []):
        name = ag.get("name", "")
        members = [m.get("name", "") for m in ag.get("address_objects", [])]
        ir["address_objects"].append({
            "name": name, "type": "group", "value": "",
            "members": members, "comment": "",
        })

    # Service objects
    for so in data.get("service_objects", []):
        obj = _sw_svc_obj(so)
        if obj:
            ir["service_objects"].append(obj)

    # Service groups
    for sg in data.get("service_groups", []):
        name = sg.get("name", "")
        members = [m.get("name", "") for m in sg.get("service_objects", [])]
        ir["service_objects"].append({
            "name": name, "type": "group", "protocol": "any",
            "dst_ports": [], "members": members, "comment": "",
        })

    # Access rules (policies)
    for rule in data.get("access_rules", []):
        # SonicOS 7 wraps in {"ipv4": {...}}, v6 is direct
        inner = rule.get("ipv4", rule)
        ir["policies"].append(_sw_policy(inner))

    # NAT policies
    for nat in data.get("nat_policies", []):
        inner = nat.get("ipv4", nat)
        ir["nat_rules"].append(_sw_nat(inner))

    # Static routes
    for route in data.get("routing", {}).get("static_routes", []):
        inner = route.get("ipv4", route)
        dst = inner.get("destination", {})
        ir["static_routes"].append({
            "network": dst.get("host", {}).get("ip", dst.get("network", {}).get("subnet", "")) + ("/" + str(dst.get("network", {}).get("mask", "32")) if "network" in dst else "/32"),
            "gateway": inner.get("gateway", {}).get("ip", ""),
            "interface": inner.get("interface", ""),
            "metric": int(inner.get("metric", 1)),
            "enabled": True,
        })

    return ir


def _sw_addr_obj(ao: dict) -> dict | None:
    name = ao.get("name", "")
    if not name:
        return None
    if "host" in ao:
        return {"name": name, "type": "host", "value": ao["host"].get("ip", ""), "members": [], "comment": ""}
    if "network" in ao:
        net = ao["network"]
        cidr = f"{net.get('subnet','')}/{net.get('mask','32')}"
        return {"name": name, "type": "network", "value": cidr, "members": [], "comment": ""}
    if "range" in ao:
        r = ao["range"]
        return {"name": name, "type": "range", "value": f"{r.get('begin','')}-{r.get('end','')}", "members": [], "comment": ""}
    if "fqdn" in ao:
        return {"name": name, "type": "fqdn", "value": ao["fqdn"].get("domain", ""), "members": [], "comment": ""}
    return {"name": name, "type": "host", "value": "", "members": [], "comment": ""}


def _sw_svc_obj(so: dict) -> dict | None:
    name = so.get("name", "")
    if not name:
        return None
    proto_map = {6: "tcp", 17: "udp", 1: "icmp"}
    proto_num = so.get("protocol", 6)
    proto = proto_map.get(proto_num, "any")
    port_begin = so.get("port_begin", "")
    port_end = so.get("port_end", "")
    if port_begin and port_end and port_begin != port_end:
        dst_ports = [f"{port_begin}-{port_end}"]
    elif port_begin:
        dst_ports = [str(port_begin)]
    else:
        dst_ports = []
    return {"name": name, "type": "service", "protocol": proto, "dst_ports": dst_ports, "members": [], "comment": ""}


def _sw_policy(rule: dict) -> dict:
    action_map = {"allow": "accept", "permit": "accept", "deny": "deny", "discard": "drop"}
    return {
        "id": str(rule.get("rule_id", rule.get("id", ""))),
        "name": rule.get("name", ""),
        "action": action_map.get(rule.get("action", "deny"), "deny"),
        "src_zones":     [rule.get("source", {}).get("zone", "any")],
        "dst_zones":     [rule.get("destination", {}).get("zone", "any")],
        "src_addresses": [rule.get("source", {}).get("address", {}).get("name", "any")],
        "dst_addresses": [rule.get("destination", {}).get("address", {}).get("name", "any")],
        "services":      [rule.get("service", {}).get("name", "any")],
        "nat": False,
        "log": rule.get("log", False),
        "enabled": rule.get("enabled", True),
        "comment": rule.get("comment", ""),
    }


def _sw_nat(nat: dict) -> dict:
    nat_type = "dnat" if nat.get("inbound", False) else "snat"
    return {
        "name": nat.get("comment", ""),
        "type": nat_type,
        "src_addresses": [nat.get("original_source", {}).get("name", "any")],
        "dst_addresses": [nat.get("original_destination", {}).get("name", "any")],
        "services":      [nat.get("original_service", {}).get("name", "any")],
        "translated_src": nat.get("translated_source", {}).get("name"),
        "translated_dst": nat.get("translated_destination", {}).get("name"),
        "translated_port": nat.get("translated_service", {}).get("name"),
        "enabled": nat.get("enabled", True),
        "comment": nat.get("comment", ""),
    }


# ── Sophos XG/XGS parser (from REST API JSON export) ─────────────────────────

def _parse_sophos(raw_json: str) -> dict[str, Any]:
    """Parse Sophos XG REST API export into normalized IR.

    Expects a JSON object with keys like 'IPHost', 'IPHostGroup',
    'Services', 'ServiceGroup', 'FirewallRule', 'NATRule', 'StaticRoute'.
    """
    ir = _empty_ir()

    try:
        data = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
    except Exception as exc:
        ir["warnings"].append(f"Sophos: falha ao decodificar JSON de origem: {exc}")
        return ir

    # IP Hosts
    for host in data.get("IPHost", []):
        obj = _sophos_host(host)
        if obj:
            ir["address_objects"].append(obj)

    # IP Host Groups
    for grp in data.get("IPHostGroup", []):
        name = grp.get("Name", "")
        members = grp.get("HostList", {}).get("Host", [])
        if isinstance(members, str):
            members = [members]
        ir["address_objects"].append({
            "name": name, "type": "group", "value": "",
            "members": members, "comment": "",
        })

    # Services
    for svc in data.get("Services", []):
        obj = _sophos_service(svc)
        if obj:
            ir["service_objects"].append(obj)

    # Service Groups
    for sg in data.get("ServiceGroup", []):
        name = sg.get("Name", "")
        members = sg.get("ServiceList", {}).get("Service", [])
        if isinstance(members, str):
            members = [members]
        ir["service_objects"].append({
            "name": name, "type": "group", "protocol": "any",
            "dst_ports": [], "members": members, "comment": "",
        })

    # Firewall rules
    for i, rule in enumerate(data.get("FirewallRule", []), start=1):
        ir["policies"].append(_sophos_policy(i, rule))

    # NAT rules
    for nat in data.get("NATRule", []):
        ir["nat_rules"].append(_sophos_nat(nat))

    # Static routes
    for route in data.get("StaticRoute", []):
        ir["static_routes"].append({
            "network": route.get("DestinationIPFamily", "") + "/" + str(route.get("Subnet", "0")),
            "gateway": route.get("Gateway", ""),
            "interface": route.get("Interface", ""),
            "metric": int(route.get("Distance", 0)),
            "enabled": True,
        })

    return ir


def _sophos_host(host: dict) -> dict | None:
    name = host.get("Name", "")
    if not name:
        return None
    host_type = host.get("HostType", "IP")
    if host_type in ("IP", "IPAddress"):
        ip = host.get("IPAddress", "")
        subnet = host.get("Subnet", "255.255.255.255")
        cidr = _ip_mask_to_cidr(ip, subnet)
        try:
            net = ipaddress.IPv4Network(cidr, strict=False)
            t = "host" if net.prefixlen == 32 else "network"
        except Exception:
            t = "network"
        return {"name": name, "type": t, "value": cidr, "members": [], "comment": ""}
    if host_type in ("Network", "Subnet"):
        ip = host.get("IPAddress", "")
        subnet = host.get("Subnet", "255.255.255.0")
        return {"name": name, "type": "network", "value": _ip_mask_to_cidr(ip, subnet), "members": [], "comment": ""}
    if host_type == "IPRange":
        return {"name": name, "type": "range",
                "value": f"{host.get('StartIPAddress','')}-{host.get('EndIPAddress','')}",
                "members": [], "comment": ""}
    if host_type == "FQDN":
        return {"name": name, "type": "fqdn", "value": host.get("FQDN", ""), "members": [], "comment": ""}
    return {"name": name, "type": "host", "value": host.get("IPAddress", ""), "members": [], "comment": ""}


def _sophos_service(svc: dict) -> dict | None:
    name = svc.get("Name", "")
    if not name:
        return None
    proto_map = {"TCP": "tcp", "UDP": "udp", "ICMP": "icmp", "TCPorUDP": "tcp"}
    details = svc.get("ServiceDetails", {}).get("ServiceDetail", {})
    if isinstance(details, list):
        details = details[0] if details else {}
    proto = proto_map.get(details.get("Protocol", "TCP"), "tcp")
    dst_port = details.get("DestinationPort", "")
    dst_ports = [dst_port] if dst_port else []
    return {"name": name, "type": "service", "protocol": proto, "dst_ports": dst_ports, "members": [], "comment": ""}


def _sophos_policy(idx: int, rule: dict) -> dict:
    action_map = {"accept": "accept", "Accept": "accept", "drop": "drop", "Drop": "drop",
                  "reject": "deny", "Reject": "deny"}
    src = rule.get("SourceNetworks", {}).get("Network", [])
    dst = rule.get("DestinationNetworks", {}).get("Network", [])
    svcs = rule.get("Services", {}).get("Service", [])
    if isinstance(src, str): src = [src]
    if isinstance(dst, str): dst = [dst]
    if isinstance(svcs, str): svcs = [svcs]
    return {
        "id": str(rule.get("RuleID", idx)),
        "name": rule.get("Name", ""),
        "action": action_map.get(rule.get("Action", "drop"), "drop"),
        "src_zones":     [rule.get("SourceZones", {}).get("Zone", "any")] if isinstance(rule.get("SourceZones", {}).get("Zone"), str) else rule.get("SourceZones", {}).get("Zone", ["any"]),
        "dst_zones":     [rule.get("DestinationZones", {}).get("Zone", "any")] if isinstance(rule.get("DestinationZones", {}).get("Zone"), str) else rule.get("DestinationZones", {}).get("Zone", ["any"]),
        "src_addresses": src or ["any"],
        "dst_addresses": dst or ["any"],
        "services":      svcs or ["any"],
        "nat": False,
        "log": rule.get("LogTraffic", "disable") not in ("disable", "Disable", False),
        "enabled": rule.get("Status", "enable") not in ("disable", "Disable", False),
        "comment": rule.get("Description", ""),
    }


def _sophos_nat(nat: dict) -> dict:
    nat_type_map = {"DNAT": "dnat", "SNAT": "snat", "Masquerade": "masquerade"}
    return {
        "name": nat.get("RuleName", ""),
        "type": nat_type_map.get(nat.get("NATType", "SNAT"), "snat"),
        "src_addresses": [nat.get("OriginalSource", {}).get("IPHost", "any")] if isinstance(nat.get("OriginalSource"), dict) else ["any"],
        "dst_addresses": [nat.get("OriginalDestination", {}).get("IPHost", "any")] if isinstance(nat.get("OriginalDestination"), dict) else ["any"],
        "services":      [nat.get("OriginalService", "any")],
        "translated_src":  nat.get("TranslatedSource", {}).get("IPHost") if isinstance(nat.get("TranslatedSource"), dict) else None,
        "translated_dst":  nat.get("TranslatedDestination", {}).get("IPHost") if isinstance(nat.get("TranslatedDestination"), dict) else None,
        "translated_port": None,
        "enabled": True,
        "comment": nat.get("Description", ""),
    }


# ── Registry ──────────────────────────────────────────────────────────────────

_PARSERS: dict[str, Any] = {
    "fortinet":  _parse_fortinet,
    "sonicwall": _parse_sonicwall,
    "sophos":    _parse_sophos,
}


def parse_firewall_rules(vendor: str, raw: str) -> dict[str, Any]:
    """Parse raw firewall config/JSON for vendor into normalized IR. Never raises."""
    parser = _PARSERS.get(vendor)
    if parser is None:
        return {**_empty_ir(), "warnings": [f"Vendor '{vendor}' não tem parser de regras implementado"]}
    try:
        return parser(raw)
    except Exception as exc:
        return {**_empty_ir(), "warnings": [f"Erro no parser ({vendor}): {exc}"]}
