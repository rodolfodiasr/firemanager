"""Fase 18 — Network Connectivity Analysis service.

Collects routing tables, BGP/OSPF peer state, and SD-WAN status from
firewall and switch devices, then detects anomalies and generates an
AI summary via Claude.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

# Administrative Distance por protocolo (menor = maior prioridade)
_AD: dict[str, int] = {
    "connected": 0,
    "static":    1,
    "eigrp":     90,
    "ospf":      110,
    "isis":      115,
    "rip":       120,
    "bgp":       200,
    "sdwan":     5,    # SD-WAN policy tem precedência sobre tudo exceto connected
    "unknown":   999,
}

log = logging.getLogger(__name__)

# ── Vendor routing commands ────────────────────────────────────────────────────

_CLI_ROUTE_CMDS: dict[str, list[str]] = {
    "cisco_ios":   ["show ip route", "show ip bgp summary", "show ip ospf neighbor"],
    "cisco_nxos":  ["show ip route", "show ip bgp summary", "show ip ospf neighbor"],
    "dell":        ["show ip route", "show ip bgp summary", "show ip ospf neighbor"],
    "dell_n":      ["show ip route", "show ip bgp summary", "show ip ospf neighbor"],
    "aruba":       ["show ip route", "show ip bgp summary", "show ip ospf neighbor"],
    "ubiquiti":    ["show ip route", "show ip bgp summary"],
    "edgeswitch":  ["show ip route"],
    "hp_comware":  ["display ip routing-table", "display bgp peer", "display ospf peer"],
    "juniper":     ["show route", "show bgp summary", "show ospf neighbor"],
}

_CLAUDE_SYSTEM = """Você é especialista em análise de redes e segurança de infraestrutura.

Receberá:
1. Tabela de roteamento de um dispositivo (firewall ou switch)
2. Status de peers BGP e vizinhos OSPF (quando disponível)
3. Lista de anomalias detectadas automaticamente

Sua tarefa:
- Explique o estado geral da conectividade em linguagem clara para um analista N2/N3
- Para cada anomalia, explique o impacto prático e a causa mais provável
- Forneça recomendações de correção priorizadas (Alta → Média → Baixa)
- Se detectar riscos de segurança (rotas inesperadas, peers não autorizados), destaque

Retorne SOMENTE JSON válido, sem markdown ou texto adicional:
{
  "summary": "parágrafo de análise geral",
  "recommendations": ["recomendação 1", "recomendação 2", ...]
}"""


# ── Route parsers (CLI output → normalized list) ──────────────────────────────

def _mask_to_plen(mask: object) -> int:
    if isinstance(mask, int):
        return mask
    s = str(mask)
    if "/" in s:
        return int(s.split("/")[-1])
    if "." in s:
        try:
            return sum(bin(int(o)).count("1") for o in s.split("."))
        except ValueError:
            pass
    return 0


def _parse_cisco_routes(output: str) -> list[dict]:
    routes: list[dict] = []
    proto_map = {"C": "connected", "S": "static", "O": "ospf", "B": "bgp",
                 "R": "rip", "i": "isis", "E": "eigrp", "L": "local"}
    pattern = re.compile(
        r"^([CSOBREL\*][\* ]?)\s+([\d.]+(?:/\d+)?)\s+(?:\[\d+/\d+\]\s+via\s+([\d.]+))?",
        re.MULTILINE,
    )
    for m in pattern.finditer(output):
        proto_code = m.group(1).strip().lstrip("*").strip()
        prefix = m.group(2)
        nexthop = m.group(3) or "0.0.0.0"
        dest, _, plen = prefix.partition("/")
        routes.append({
            "destination": dest,
            "prefix_len": int(plen) if plen else 32,
            "next_hop": nexthop,
            "protocol": proto_map.get(proto_code, "unknown"),
            "active": True,
        })
    return routes


def _parse_juniper_routes(output: str) -> list[dict]:
    routes: list[dict] = []
    proto_map = {"Direct": "connected", "Static": "static", "OSPF": "ospf", "BGP": "bgp"}
    pattern = re.compile(r"([\d.]+/\d+)\s+.*?via\s+([\d.]+)", re.DOTALL)
    for m in pattern.finditer(output):
        prefix = m.group(1)
        nexthop = m.group(2)
        dest, _, plen = prefix.partition("/")
        routes.append({
            "destination": dest,
            "prefix_len": int(plen) if plen else 32,
            "next_hop": nexthop,
            "protocol": "unknown",
            "active": True,
        })
    return routes


def _parse_comware_routes(output: str) -> list[dict]:
    routes: list[dict] = []
    pattern = re.compile(r"([\d.]+)\s+([\d.]+)\s+\d+\s+\d+\s+([\w]+)\s+([\d.]+)")
    for m in pattern.finditer(output):
        dest = m.group(1)
        mask = m.group(2)
        proto = m.group(3).lower()
        nexthop = m.group(4)
        plen = sum(bin(int(x)).count("1") for x in mask.split(".")) if "." in mask else 32
        routes.append({
            "destination": dest,
            "prefix_len": plen,
            "next_hop": nexthop,
            "protocol": proto,
            "active": True,
        })
    return routes


def _parse_bgp_summary(vendor: str, output: str) -> list[dict]:
    peers: list[dict] = []
    if vendor in ("cisco_ios", "cisco_nxos", "dell", "dell_n", "aruba"):
        for line in output.splitlines():
            m = re.match(r"^\s*([\d.]+)\s+\d+\s+(\d+)\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+(\w+)", line)
            if m:
                peers.append({"peer_ip": m.group(1), "asn": m.group(2), "state": m.group(3)})
    elif vendor == "juniper":
        for line in output.splitlines():
            m = re.match(r"^\s*([\d.]+)\s+(\d+)\s+\d+\s+(\w+)", line)
            if m:
                peers.append({"peer_ip": m.group(1), "asn": m.group(2), "state": m.group(3)})
    elif vendor == "hp_comware":
        for line in output.splitlines():
            m = re.match(r"\s*([\d.]+)\s+(\d+)\s+\S+\s+\S+\s+\S+\s+(\w+)", line)
            if m:
                peers.append({"peer_ip": m.group(1), "asn": m.group(2), "state": m.group(3)})
    return peers


def _parse_ospf_neighbors(vendor: str, output: str) -> list[dict]:
    neighbors: list[dict] = []
    if vendor in ("cisco_ios", "cisco_nxos", "dell", "dell_n", "aruba"):
        for line in output.splitlines():
            m = re.match(r"^\s*([\d.]+)\s+\d+\s+(\w+/?\w*)\s+\S+\s+([\w.]+)", line)
            if m:
                neighbors.append({"neighbor_id": m.group(1), "state": m.group(2), "interface": m.group(3)})
    elif vendor == "juniper":
        for line in output.splitlines():
            m = re.match(r"^\s*([\d.]+)\s+\d+\s+(\w+)\s+\S+\s+([\w.-]+)", line)
            if m:
                neighbors.append({"neighbor_id": m.group(1), "state": m.group(2), "interface": m.group(3)})
    elif vendor == "hp_comware":
        for line in output.splitlines():
            m = re.match(r"\s*([\d.]+)\s+\S+\s+(\w+)\s+([\w\d/]+)", line)
            if m:
                neighbors.append({"neighbor_id": m.group(1), "state": m.group(2), "interface": m.group(3)})
    return neighbors


# ── Fortinet routes via REST ───────────────────────────────────────────────────

async def _fetch_fortinet_routes(device) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    from app.utils.crypto import decrypt_credentials

    creds = decrypt_credentials(device.encrypted_credentials)
    vdom = creds.get("vdom") or "root"
    base = f"{'https' if device.use_ssl else 'http'}://{device.host}:{device.port}"
    token = creds.get("token") or ""
    headers = {"Authorization": f"Bearer {token}"}

    import httpx
    verify = device.verify_ssl if device.verify_ssl is not None else False
    routes, bgp_peers, ospf_neighbors, sdwan_services = [], [], [], []

    async with httpx.AsyncClient(verify=verify, timeout=30) as client:
        try:
            r = await client.get(f"{base}/api/v2/monitor/router/ipv4?vdom={vdom}", headers=headers)
            if r.status_code == 200:
                for entry in r.json().get("results", []):
                    routes.append({
                        "destination": entry.get("ip", ""),
                        "prefix_len": _mask_to_plen(entry.get("mask", 0)),
                        "next_hop": entry.get("gateway", "0.0.0.0"),
                        "interface": entry.get("interface", ""),
                        "protocol": entry.get("type", "static").lower(),
                        "active": True,
                    })
        except Exception as e:
            log.debug("Fortinet route fetch error: %s", e)

        try:
            r = await client.get(f"{base}/api/v2/monitor/router/bgp-neighbors?vdom={vdom}", headers=headers)
            if r.status_code == 200:
                for peer in r.json().get("results", []):
                    bgp_peers.append({
                        "peer_ip": peer.get("ip", ""),
                        "asn": str(peer.get("remote_as", "")),
                        "state": peer.get("state", "unknown"),
                        "uptime": peer.get("up_time", None),
                        "prefixes_received": peer.get("received_prefixes", 0),
                    })
        except Exception as e:
            log.debug("Fortinet BGP fetch error: %s", e)

        try:
            r = await client.get(f"{base}/api/v2/monitor/router/ospf-neighbors?vdom={vdom}", headers=headers)
            if r.status_code == 200:
                for nb in r.json().get("results", []):
                    ospf_neighbors.append({
                        "neighbor_id": nb.get("neighbor_id", ""),
                        "state": nb.get("state", "unknown"),
                        "interface": nb.get("local_if", None),
                        "address": nb.get("ip", None),
                    })
        except Exception as e:
            log.debug("Fortinet OSPF fetch error: %s", e)

        # SD-WAN services — cada service define destinos e membros WAN
        try:
            r = await client.get(f"{base}/api/v2/cmdb/system/sdwan?vdom={vdom}", headers=headers)
            if r.status_code == 200:
                results = r.json().get("results", [])
                cfg = results[0] if results else {}
                members_info = {
                    str(m.get("seq-num", "")): m.get("interface", "")
                    for m in cfg.get("members", [])
                }
                for svc in cfg.get("service", []):
                    dsts = []
                    for d in svc.get("dst", []):
                        subnet = d.get("subnet", "")
                        if subnet and subnet != "0.0.0.0 0.0.0.0":
                            parts = subnet.split()
                            if len(parts) == 2:
                                dsts.append(f"{parts[0]}/{_mask_to_plen(parts[1])}")
                            else:
                                dsts.append(subnet)
                    member_ifaces = [members_info.get(str(m.get("seq-num", "")), str(m.get("seq-num", "")))
                                     for m in svc.get("members", [])]
                    sdwan_services.append({
                        "name": svc.get("name", ""),
                        "mode": svc.get("mode", ""),
                        "destinations": dsts,
                        "members": member_ifaces,
                        "status": "active",
                    })
        except Exception as e:
            log.debug("Fortinet SD-WAN fetch error: %s", e)

    return routes, bgp_peers, ospf_neighbors, sdwan_services


async def _fetch_sonicwall_routes(device) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    from app.utils.crypto import decrypt_credentials
    import httpx

    creds = decrypt_credentials(device.encrypted_credentials)
    base = f"{'https' if device.use_ssl else 'http'}://{device.host}:{device.port}"
    verify = device.verify_ssl if device.verify_ssl is not None else False
    username = creds.get("username", "")
    password = creds.get("password", "")
    routes, bgp_peers, ospf_neighbors, sdwan_services = [], [], [], []

    async with httpx.AsyncClient(
        base_url=base,
        verify=verify,
        timeout=30,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    ) as client:
        try:
            # Digest Auth + override=True (matches existing SonicWall connector pattern)
            auth_r = await client.post(
                "/api/sonicos/auth",
                json={"override": True},
                auth=httpx.DigestAuth(username, password),
            )
            if not auth_r.is_success:
                raise ValueError(f"SonicWall auth falhou: HTTP {auth_r.status_code} — {auth_r.text[:200]}")

            # Build address object name → CIDR lookup
            addr_map: dict[str, tuple[str, int]] = {}  # name → (network_ip, prefix_len)
            try:
                r = await client.get("/api/sonicos/address-objects/ipv4")
                if r.status_code == 200:
                    for entry in r.json().get("address_objects", []):
                        obj = entry.get("ipv4", entry) if isinstance(entry, dict) else {}
                        name = obj.get("name", "")
                        if not name:
                            continue
                        if "host" in obj:
                            addr_map[name] = (obj["host"].get("ip", ""), 32)
                        elif "network" in obj:
                            n = obj["network"]
                            plen = _mask_to_plen(n.get("mask", "0.0.0.0"))
                            try:
                                net = ipaddress.ip_network(f"{n.get('subnet','')}/{plen}", strict=False)
                                addr_map[name] = (str(net.network_address), net.prefixlen)
                            except ValueError:
                                pass
            except Exception as e:
                log.debug("SonicWall address objects error: %s", e)

            # Connected routes from interface IPs
            try:
                r = await client.get("/api/sonicos/interfaces/ipv4")
                if r.status_code == 200:
                    for entry in r.json().get("interfaces", []):
                        iface = entry.get("ipv4", entry) if isinstance(entry, dict) else {}
                        iface_name = iface.get("name", "")
                        # SonicOS stores IP under ip_assignment.mode.static or directly under ip/mask
                        ip_assign = iface.get("ip_assignment", {})
                        mode = ip_assign.get("mode", {})
                        static = mode.get("static", {}) if isinstance(mode, dict) else {}
                        addr = static.get("ip", "") or iface.get("ip", "")
                        mask = static.get("mask", "") or iface.get("mask", "")
                        if addr and addr not in ("0.0.0.0", ""):
                            try:
                                plen = _mask_to_plen(mask) if mask else 32
                                net = ipaddress.ip_network(f"{addr}/{plen}", strict=False)
                                routes.append({
                                    "destination": str(net.network_address),
                                    "prefix_len": net.prefixlen,
                                    "next_hop": "0.0.0.0",
                                    "interface": iface_name,
                                    "protocol": "connected",
                                    "active": True,
                                })
                            except ValueError:
                                pass
            except Exception as e:
                log.debug("SonicWall interfaces error: %s", e)

            # Route policies (static routes)
            try:
                r = await client.get("/api/sonicos/route-policies/ipv4")
                if r.status_code == 200:
                    for item in r.json().get("route_policies", []):
                        rp = item.get("ipv4", item) if isinstance(item, dict) else item

                        # Resolve destination
                        dst_field = rp.get("destination", {})
                        dst_name = dst_field.get("name") or dst_field.get("group") or ""
                        if dst_name in addr_map:
                            dest_ip, plen = addr_map[dst_name]
                        else:
                            # If destination is "Any" or unresolved, treat as default route
                            dest_ip, plen = ("0.0.0.0", 0) if not dst_name or dst_name.lower() in ("any", "") else ("0.0.0.0", 0)

                        # Gateway
                        gw = rp.get("gateway", {})
                        if isinstance(gw, dict):
                            nexthop = "0.0.0.0" if gw.get("default") else gw.get("ip", "0.0.0.0")
                        else:
                            nexthop = str(gw) if gw else "0.0.0.0"

                        routes.append({
                            "destination": dest_ip,
                            "prefix_len": plen,
                            "next_hop": nexthop,
                            "interface": rp.get("interface", ""),
                            "protocol": "static",
                            "active": not rp.get("disable_on_interface_down", False),
                        })
            except Exception as e:
                log.debug("SonicWall route policies error: %s", e)

            # Logout
            try:
                await client.delete("/api/sonicos/auth")
            except Exception:
                pass

        except Exception as e:
            log.debug("SonicWall route fetch error: %s", e)
            raise ValueError(f"SonicWall REST: {e}") from e

    return routes, bgp_peers, ospf_neighbors, sdwan_services


async def _fetch_mikrotik_routes(device) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    from app.utils.crypto import decrypt_credentials

    creds = decrypt_credentials(device.encrypted_credentials)
    base = f"{'https' if device.use_ssl else 'http'}://{device.host}:{device.port}"
    auth = (creds.get("username", ""), creds.get("password", ""))
    verify = device.verify_ssl if device.verify_ssl is not None else False

    import httpx
    routes, bgp_peers, ospf_neighbors, sdwan_services = [], [], [], []

    async with httpx.AsyncClient(verify=verify, timeout=30, auth=auth) as client:
        try:
            r = await client.get(f"{base}/rest/ip/route")
            if r.status_code == 200:
                for entry in r.json():
                    dst = entry.get("dst-address", "0.0.0.0/0")
                    dest, _, plen = dst.partition("/")
                    routes.append({
                        "destination": dest,
                        "prefix_len": int(plen) if plen else 32,
                        "next_hop": entry.get("gateway", "0.0.0.0"),
                        "interface": entry.get("interface", None),
                        "protocol": "static" if entry.get("static") else "connected",
                        "active": entry.get("active", False),
                    })
        except Exception as e:
            log.debug("MikroTik route fetch error: %s", e)

        try:
            r = await client.get(f"{base}/rest/routing/bgp/peer")
            if r.status_code == 200:
                for peer in r.json():
                    bgp_peers.append({
                        "peer_ip": peer.get("address", ""),
                        "asn": str(peer.get("remote-as", "")),
                        "state": peer.get("state", "unknown"),
                    })
        except Exception as e:
            log.debug("MikroTik BGP fetch error: %s", e)

    return routes, bgp_peers, ospf_neighbors, sdwan_services


# ── CLI-based data collection ──────────────────────────────────────────────────

async def _fetch_cli_routes(device) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    from app.connectors.factory import get_ssh_connector

    vendor = device.vendor.value
    cmds = _CLI_ROUTE_CMDS.get(vendor, ["show ip route"])

    connector = get_ssh_connector(device)
    try:
        result = await asyncio.wait_for(
            connector.execute_show_commands(cmds),
            timeout=60,
        )
    except asyncio.TimeoutError:
        raise ValueError(f"Timeout ao coletar rotas via SSH ({vendor})")

    if not result.success:
        raise ValueError(f"Falha SSH: {result.error}")

    output = result.output or ""

    # Split multi-command output (Netmiko separates by command)
    sections = re.split(r"(?:show ip route|show route|display ip routing-table|display bgp peer|display ospf peer|show ip bgp summary|show bgp summary|show ip ospf neighbor|show ospf neighbor)\s*\n", output, flags=re.IGNORECASE)

    route_output = sections[0] if sections else output
    bgp_output   = sections[1] if len(sections) > 1 else ""
    ospf_output  = sections[2] if len(sections) > 2 else ""

    if vendor in ("hp_comware",):
        routes = _parse_comware_routes(route_output)
    elif vendor == "juniper":
        routes = _parse_juniper_routes(route_output)
    else:
        routes = _parse_cisco_routes(route_output)

    bgp_peers       = _parse_bgp_summary(vendor, bgp_output)
    ospf_neighbors  = _parse_ospf_neighbors(vendor, ospf_output)

    return routes, bgp_peers, ospf_neighbors, []


# ── Anomaly detection ─────────────────────────────────────────────────────────

def _detect_cidr_overlaps(routes: list[dict]) -> list[dict]:
    anomalies: list[dict] = []
    nets: list[tuple[ipaddress.IPv4Network, dict]] = []

    for r in routes:
        if r.get("protocol") == "connected":
            continue
        try:
            net = ipaddress.ip_network(f"{r['destination']}/{r.get('prefix_len', 32)}", strict=False)
            nets.append((net, r))
        except ValueError:
            continue

    checked: set[tuple[int, int]] = set()
    for i, (net_a, route_a) in enumerate(nets):
        for j, (net_b, route_b) in enumerate(nets):
            if i >= j or (i, j) in checked:
                continue
            checked.add((i, j))
            if net_a == net_b:
                continue
            # One contains the other
            if net_a.supernet_of(net_b) or net_b.supernet_of(net_a):
                parent, pr = (net_a, route_a) if net_a.supernet_of(net_b) else (net_b, route_b)
                child,  cr = (net_b, route_b) if net_a.supernet_of(net_b) else (net_a, route_a)
                if pr.get("next_hop") != cr.get("next_hop"):
                    winner_proto = cr.get("protocol", "unknown")  # more specific always wins
                    anomalies.append({
                        "type": "cidr_overlap",
                        "severity": "medium",
                        "description": (
                            f"Prefixo {child} está contido em {parent}, mas com gateway diferente "
                            f"({cr.get('next_hop')} vs {pr.get('next_hop')}). "
                            f"Tráfego para {child} seguirá via {cr.get('next_hop')} "
                            f"(rota mais específica via {winner_proto} tem prioridade)."
                        ),
                        "details": {
                            "parent_prefix": str(parent),
                            "parent_gateway": pr.get("next_hop"),
                            "parent_protocol": pr.get("protocol"),
                            "child_prefix": str(child),
                            "child_gateway": cr.get("next_hop"),
                            "child_protocol": cr.get("protocol"),
                        },
                    })
    return anomalies


def _detect_multi_protocol_conflicts(routes: list[dict]) -> list[dict]:
    anomalies: list[dict] = []
    prefix_map: dict[str, list[dict]] = {}

    for r in routes:
        key = f"{r.get('destination')}/{r.get('prefix_len', 0)}"
        prefix_map.setdefault(key, []).append(r)

    for prefix, route_list in prefix_map.items():
        protocols = {r.get("protocol", "unknown") for r in route_list}
        gateways  = {r.get("next_hop", "") for r in route_list}

        if len(protocols) < 2 or len(gateways) < 2:
            continue

        sorted_routes = sorted(route_list, key=lambda r: _AD.get(r.get("protocol", "unknown"), 999))
        winner = sorted_routes[0]
        loser_protos = [r.get("protocol") for r in sorted_routes[1:]]

        anomalies.append({
            "type": "multi_protocol_conflict",
            "severity": "high",
            "description": (
                f"Prefixo {prefix} aprendido simultaneamente via {', '.join(protocols)}. "
                f"Rota ativa: {winner.get('protocol')} → {winner.get('next_hop')} "
                f"(AD={_AD.get(winner.get('protocol','unknown'), 999)}). "
                f"Dormindo: {', '.join(loser_protos)}. Confirme se a redundância é intencional."
            ),
            "details": {
                "prefix": prefix,
                "active": {"protocol": winner.get("protocol"), "gateway": winner.get("next_hop"),
                           "ad": _AD.get(winner.get("protocol", "unknown"), 999)},
                "standby": [{"protocol": r.get("protocol"), "gateway": r.get("next_hop"),
                             "ad": _AD.get(r.get("protocol", "unknown"), 999)}
                            for r in sorted_routes[1:]],
            },
        })
    return anomalies


def _detect_sdwan_conflicts(routes: list[dict], sdwan_services: list[dict]) -> list[dict]:
    anomalies: list[dict] = []

    for svc in sdwan_services:
        for dst_str in svc.get("destinations", []):
            if not dst_str:
                continue
            try:
                sdwan_net = ipaddress.ip_network(dst_str, strict=False)
            except ValueError:
                continue

            conflicts: list[dict] = []
            for r in routes:
                if r.get("protocol") == "connected":
                    continue
                try:
                    route_net = ipaddress.ip_network(
                        f"{r['destination']}/{r.get('prefix_len', 32)}", strict=False
                    )
                except ValueError:
                    continue
                if sdwan_net.overlaps(route_net):
                    conflicts.append(r)

            if conflicts:
                protos = list({r.get("protocol", "unknown") for r in conflicts})
                anomalies.append({
                    "type": "sdwan_routing_conflict",
                    "severity": "high",
                    "description": (
                        f"SD-WAN policy '{svc.get('name')}' ({svc.get('mode', '')}) cobre {dst_str} "
                        f"que também existe na tabela de roteamento via {', '.join(protos)}. "
                        f"A policy SD-WAN tem precedência (AD=5) — verifique se o failover para a rota "
                        f"estática/OSPF ocorre corretamente quando o SD-WAN detectar falha."
                    ),
                    "details": {
                        "sdwan_service": svc.get("name"),
                        "sdwan_mode": svc.get("mode"),
                        "sdwan_members": svc.get("members", []),
                        "sdwan_destination": dst_str,
                        "conflicting_routes": conflicts,
                    },
                })
    return anomalies


def detect_anomalies(
    routes: list[dict],
    bgp_peers: list[dict],
    ospf_neighbors: list[dict],
    sdwan_services: list[dict] | None = None,
) -> list[dict]:
    anomalies: list[dict] = []

    # No default route
    has_default = any(r.get("destination") in ("0.0.0.0", "") and r.get("prefix_len", 1) == 0 for r in routes)
    if not has_default and routes:
        anomalies.append({
            "type": "no_default_route",
            "severity": "high",
            "description": "Nenhuma rota padrão (0.0.0.0/0) encontrada. O dispositivo pode não conseguir rotear tráfego desconhecido.",
        })

    # Static vs dynamic conflict (same prefix via two protocols)
    prefix_protos: dict[str, list[str]] = {}
    for r in routes:
        key = f"{r.get('destination')}/{r.get('prefix_len', 0)}"
        prefix_protos.setdefault(key, []).append(r.get("protocol", ""))

    for prefix, protos in prefix_protos.items():
        unique = set(protos)
        if "static" in unique and len(unique - {"static", "connected"}) > 0:
            anomalies.append({
                "type": "static_dynamic_conflict",
                "severity": "medium",
                "description": f"Prefixo {prefix} possui rota estática e dinâmica simultâneas ({', '.join(unique)}). Pode causar comportamento imprevisível.",
                "details": {"prefix": prefix, "protocols": list(unique)},
            })

    # Redundant routes without failover (multiple next-hops, same protocol, but no standby)
    prefix_nexthops: dict[str, list[str]] = {}
    for r in routes:
        key = f"{r.get('destination')}/{r.get('prefix_len', 0)}"
        prefix_nexthops.setdefault(key, []).append(r.get("next_hop", ""))

    for prefix, hops in prefix_nexthops.items():
        if len(hops) > 1 and len(set(hops)) > 1:
            anomalies.append({
                "type": "redundant_no_failover",
                "severity": "low",
                "description": f"Prefixo {prefix} possui múltiplos next-hops ({', '.join(set(hops))}). Verifique se o failover está configurado corretamente.",
                "details": {"prefix": prefix, "next_hops": list(set(hops))},
            })

    # BGP peers not established
    for peer in bgp_peers:
        state = peer.get("state", "").lower()
        if state and state not in ("established", "active_established"):
            anomalies.append({
                "type": "bgp_not_established",
                "severity": "high",
                "description": f"Peer BGP {peer.get('peer_ip')} (AS {peer.get('asn', 'N/A')}) não está estabelecido (estado: {state}).",
                "details": {"peer": peer},
            })

    # OSPF neighbors not FULL
    for nb in ospf_neighbors:
        state = nb.get("state", "").lower()
        if state and "full" not in state:
            anomalies.append({
                "type": "ospf_not_full",
                "severity": "high",
                "description": f"Vizinho OSPF {nb.get('neighbor_id')} não está em estado FULL (estado: {state}). A convergência de rotas pode estar comprometida.",
                "details": {"neighbor": nb},
            })

    # CIDR overlap: rota mais específica com gateway diferente da genérica
    anomalies.extend(_detect_cidr_overlaps(routes))

    # Multi-protocol: mesmo prefixo aprendido via estático + OSPF + BGP simultaneamente
    anomalies.extend(_detect_multi_protocol_conflicts(routes))

    # SD-WAN policy cobrindo mesma rede que rota estática/OSPF
    if sdwan_services:
        anomalies.extend(_detect_sdwan_conflicts(routes, sdwan_services))

    return anomalies


# ── Claude AI analysis ────────────────────────────────────────────────────────

async def _claude_analysis(
    device_name: str,
    vendor: str,
    routes: list[dict],
    bgp_peers: list[dict],
    ospf_neighbors: list[dict],
    sdwan_services: list[dict],
    anomalies: list[dict],
) -> tuple[str, list[str]]:
    import anthropic

    client = anthropic.AsyncAnthropic()

    payload = {
        "device": device_name,
        "vendor": vendor,
        "route_count": len(routes),
        "routes_sample": routes[:20],
        "bgp_peers": bgp_peers,
        "ospf_neighbors": ospf_neighbors,
        "sdwan_services": sdwan_services,
        "anomalies": anomalies,
        "administrative_distances": _AD,
    }

    msg = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_CLAUDE_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )

    text = msg.content[0].text if msg.content else "{}"
    data = json.loads(text)
    return data.get("summary", ""), data.get("recommendations", [])


# ── Main analysis runner (called in background) ───────────────────────────────

async def run_analysis(analysis_id: str) -> None:
    import app.models  # noqa: F401 — ensure all models are registered
    from app.database import AsyncSessionLocal
    from app.models.connectivity import ConnectivityAnalysis, ConnectivityStatus
    from app.models.device import Device, VendorEnum
    from app.connectors.factory import CLI_VENDORS

    async with AsyncSessionLocal() as db:
        record = await db.get(ConnectivityAnalysis, UUID(analysis_id))
        if not record:
            return

        try:
            device = await db.get(Device, record.device_id)
            if not device:
                raise ValueError("Dispositivo não encontrado")

            record.status = ConnectivityStatus.running
            await db.commit()

            vendor = device.vendor

            if vendor == VendorEnum.fortinet:
                routes, bgp_peers, ospf_neighbors, sdwan_services = await _fetch_fortinet_routes(device)
            elif vendor == VendorEnum.sonicwall:
                routes, bgp_peers, ospf_neighbors, sdwan_services = await _fetch_sonicwall_routes(device)
            elif vendor == VendorEnum.mikrotik:
                routes, bgp_peers, ospf_neighbors, sdwan_services = await _fetch_mikrotik_routes(device)
            elif vendor in CLI_VENDORS:
                routes, bgp_peers, ospf_neighbors, sdwan_services = await _fetch_cli_routes(device)
            else:
                raise ValueError(f"Vendor '{vendor.value}' não suportado para análise de conectividade ainda.")

            anomalies = detect_anomalies(routes, bgp_peers, ospf_neighbors, sdwan_services)

            ai_summary, ai_recs = "", []
            try:
                ai_summary, ai_recs = await _claude_analysis(
                    device_name=device.name,
                    vendor=vendor.value,
                    routes=routes,
                    bgp_peers=bgp_peers,
                    ospf_neighbors=ospf_neighbors,
                    sdwan_services=sdwan_services,
                    anomalies=anomalies,
                )
            except Exception as exc:
                log.warning("Claude analysis failed for connectivity %s: %s", analysis_id, exc)
                ai_summary = "Análise IA indisponível."
                ai_recs = []

            record.routes          = routes
            record.bgp_peers       = bgp_peers
            record.ospf_neighbors  = ospf_neighbors
            record.sdwan_services  = sdwan_services
            record.anomalies       = anomalies
            record.ai_summary      = ai_summary
            record.ai_recommendations = ai_recs
            record.status          = ConnectivityStatus.completed
            record.completed_at    = datetime.now(timezone.utc)

        except Exception as exc:
            log.exception("Connectivity analysis %s failed: %s", analysis_id, exc)
            record.status = ConnectivityStatus.failed
            record.error  = str(exc)
            record.completed_at = datetime.now(timezone.utc)

        await db.commit()
