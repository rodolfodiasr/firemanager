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


# ── SonicOS CLI parsers ───────────────────────────────────────────────────────

def _parse_sonicwall_routes(output: str) -> list[dict]:
    """Parse SonicOS 'show route' output into normalized route dicts."""
    routes: list[dict] = []
    # SonicOS route table lines: Destination/Mask  Gateway  Pref  Metric  Interface  Type
    # e.g.: 0.0.0.0/0   200.1.1.1   1   0   X1   Static
    #        10.0.0.0/8  0.0.0.0     0   0   X0   Connected
    pattern = re.compile(
        r"([\d.]+)/([\d.]+)\s+"          # dest / mask-or-plen
        r"([\d.]+)\s+"                    # gateway
        r"\d+\s+\d+\s+"                  # pref + metric
        r"(\S+)\s+"                       # interface
        r"(\w+)"                          # type
    )
    proto_map = {
        "static": "static", "connected": "connected", "ospf": "ospf",
        "bgp": "bgp", "rip": "rip", "eigrp": "eigrp",
    }
    for m in pattern.finditer(output):
        dest, mask_or_plen, gw, iface, rtype = m.groups()
        plen = _mask_to_plen(mask_or_plen)
        try:
            net = ipaddress.ip_network(f"{dest}/{plen}", strict=False)
            dest = str(net.network_address)
        except ValueError:
            pass
        routes.append({
            "destination": dest,
            "prefix_len": plen,
            "next_hop": gw if gw != "0.0.0.0" else "0.0.0.0",
            "interface": iface,
            "protocol": proto_map.get(rtype.lower(), "unknown"),
            "active": True,
        })
    return routes


def _parse_sonicwall_ospf(output: str) -> list[dict]:
    """Parse SonicOS 'show ospf neighbor' output."""
    neighbors: list[dict] = []
    # e.g.: 0.0.0.0  10.0.0.2  10.0.0.2  Full  00:10:00  X2
    pattern = re.compile(
        r"[\d.]+\s+"           # area
        r"([\d.]+)\s+"         # router-id
        r"([\d.]+)\s+"         # address
        r"(\w+)\s+"            # state
        r"\S+\s+"              # uptime
        r"(\S+)"               # interface
    )
    for m in pattern.finditer(output):
        router_id, address, state, iface = m.groups()
        neighbors.append({
            "neighbor_id": router_id,
            "state": state,
            "interface": iface,
            "address": address,
        })
    return neighbors


def _parse_sonicwall_sdwan(output: str) -> list[dict]:
    """Parse SonicOS 'show sdwan-groups' or 'show wan-failover' output.

    SonicOS SD-WAN groups list active/standby WAN members. We return a
    minimal service descriptor so the UI can display WAN group membership.
    """
    services: list[dict] = []
    # Group header: e.g. "SD-WAN Group: WAN_Group_1  Mode: Load Balance"
    grp_pattern = re.compile(r"(?:SD-WAN Group|WAN Group)[:\s]+(\S+).*?Mode[:\s]+([^\n]+)", re.IGNORECASE)
    # Member line: e.g. "  Interface: X1  Status: Active"
    member_pattern = re.compile(r"Interface[:\s]+(\S+)\s+Status[:\s]+(\S+)", re.IGNORECASE)

    for grp_match in grp_pattern.finditer(output):
        name = grp_match.group(1).strip()
        mode = grp_match.group(2).strip()
        # Collect members that follow this group header
        start = grp_match.end()
        next_grp = grp_pattern.search(output, start)
        segment = output[start:next_grp.start() if next_grp else len(output)]
        members = [m.group(1) for m in member_pattern.finditer(segment)]
        services.append({
            "name": name,
            "mode": mode,
            "destinations": [],  # SonicWall WAN groups apply globally
            "members": members,
            "status": "active",
        })

    # Fallback: wan-failover style — "Primary: X1  Backup: X2  Status: Primary Active"
    if not services:
        prim = re.search(r"Primary[:\s]+(\S+)", output, re.IGNORECASE)
        backup = re.search(r"Backup[:\s]+(\S+)", output, re.IGNORECASE)
        status = re.search(r"Status[:\s]+([^\n]+)", output, re.IGNORECASE)
        if prim:
            members = [prim.group(1)]
            if backup:
                members.append(backup.group(1))
            services.append({
                "name": "WAN Failover",
                "mode": "failover",
                "destinations": [],
                "members": members,
                "status": (status.group(1).strip() if status else "unknown"),
            })

    return services


async def _fetch_sonicwall_routes(device) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    from app.connectors.factory import get_ssh_connector
    from app.utils.crypto import decrypt_credentials
    import httpx

    routes: list[dict] = []
    bgp_peers: list[dict] = []
    ospf_neighbors: list[dict] = []
    sdwan_services: list[dict] = []
    ssh_routes_ok = False

    # ── FASE 1: SSH (deve terminar antes de abrir sessão REST) ────────────────
    # SonicWall permite apenas uma sessão de gerenciamento por vez.
    # Idêntico ao padrão usado em bookstack_service._collect_live_data.
    try:
        ssh = get_ssh_connector(device)
        ssh_result = await asyncio.wait_for(
            ssh.execute_show_commands_full([
                "show route",
                "show ospf neighbor",
                "show sdwan-groups",
            ]),
            timeout=90,
        )
        if ssh_result.success and ssh_result.output:
            output = ssh_result.output
            log.warning("SonicWall SSH raw output (first 800): %r", output[:800])
            # After splitting on command echoes, sections are:
            # [0] = preamble/banner (before first command echo)
            # [1] = route output (after "show route" echo)
            # [2] = ospf output (after "show ospf neighbor" echo)
            # [3] = sdwan output (after "show sdwan-groups" echo)
            sections = re.split(r"(?:show route|show ospf neighbor|show sdwan-groups)\s*\r?\n", output, flags=re.IGNORECASE)
            route_out = sections[1] if len(sections) > 1 else output
            ospf_out  = sections[2] if len(sections) > 2 else ""
            sdwan_out = sections[3] if len(sections) > 3 else ""

            log.warning("SonicWall SSH sections count=%d route_out (first 500): %r", len(sections), route_out[:500])
            parsed = _parse_sonicwall_routes(route_out)
            if parsed:
                routes = parsed
                ssh_routes_ok = True
            else:
                log.warning("SonicWall SSH: show route parsed 0 routes from %d chars — regex may not match Gen6 format", len(route_out))

            ospf_neighbors = _parse_sonicwall_ospf(ospf_out)
            sdwan_services = _parse_sonicwall_sdwan(sdwan_out)

            log.info("SonicWall SSH routes=%d ospf=%d sdwan=%d",
                     len(routes), len(ospf_neighbors), len(sdwan_services))
        else:
            log.warning("SonicWall SSH show commands failed for %s: success=%s error=%s",
                        device.name, ssh_result.success, ssh_result.error)
    except Exception as exc:
        log.warning("SonicWall SSH phase exception for %s: %s", device.name, exc)

    # ── FASE 2: REST (SSH já fechou — seguro abrir nova sessão) ───────────────
    creds = decrypt_credentials(device.encrypted_credentials)
    base = f"{'https' if device.use_ssl else 'http'}://{device.host}:{device.port}"
    verify = device.verify_ssl if device.verify_ssl is not None else False
    username = creds.get("username", "")
    password = creds.get("password", "")

    # Gen6 rejects {"override": True} body — same logic as SonicWallConnector._session()
    _os_raw = creds.get("os_version") or "7"
    try:
        _os_version = int(str(_os_raw)[0])
    except (ValueError, TypeError, IndexError):
        _os_version = 7
    _auth_kwargs: dict = {} if _os_version <= 6 else {"json": {"override": True}}

    async with httpx.AsyncClient(
        base_url=base,
        verify=verify,
        timeout=30,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    ) as client:
        try:
            auth_r = await client.post(
                "/api/sonicos/auth",
                **_auth_kwargs,
                auth=httpx.DigestAuth(username, password),
            )
            if not auth_r.is_success:
                raise ValueError(f"SonicWall auth falhou: HTTP {auth_r.status_code} — {auth_r.text[:200]}")

            # Address objects → mapa nome→CIDR para resolver destinos de route policies
            addr_map: dict[str, tuple[str, int]] = {}
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
                log.debug("SonicWall address-objects error: %s", e)

            # Se SSH não trouxe rotas, usa REST (interfaces + route policies)
            if not ssh_routes_ok:
                try:
                    r = await client.get("/api/sonicos/interfaces/ipv4")
                    if r.status_code == 200:
                        for entry in r.json().get("interfaces", []):
                            iface = entry.get("ipv4", entry) if isinstance(entry, dict) else {}
                            iface_name = iface.get("name", "")
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

                try:
                    r = await client.get("/api/sonicos/route-policies/ipv4")
                    if r.status_code == 200:
                        for item in r.json().get("route_policies", []):
                            rp = item.get("ipv4", item) if isinstance(item, dict) else item
                            dst_field = rp.get("destination", {})
                            dst_name = dst_field.get("name") or dst_field.get("group") or ""
                            if dst_name in addr_map:
                                dest_ip, plen = addr_map[dst_name]
                            else:
                                dest_ip, plen = "0.0.0.0", 0
                            gw = rp.get("gateway", {})
                            nexthop = "0.0.0.0" if (isinstance(gw, dict) and gw.get("default")) else (gw.get("ip", "0.0.0.0") if isinstance(gw, dict) else str(gw or "0.0.0.0"))
                            routes.append({
                                "destination": dest_ip,
                                "prefix_len": plen,
                                "next_hop": nexthop,
                                "interface": rp.get("interface", ""),
                                "protocol": "static",
                                "active": not rp.get("disable_on_interface_down", False),
                            })
                except Exception as e:
                    log.debug("SonicWall route-policies error: %s", e)

            try:
                await client.delete("/api/sonicos/auth")
            except Exception:
                pass

        except Exception as exc:
            log.warning("SonicWall REST phase error (device %s): %s", device.name, exc)
            if not ssh_routes_ok and not routes:
                raise ValueError(f"SonicWall: SSH e REST falharam — {exc}") from exc

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


# ── Pair anomaly detection (cross-device) ────────────────────────────────────

def _has_covering_route(target_prefix: str, route_map: dict[str, dict]) -> bool:
    """Return True if any route in route_map covers target_prefix (exact or supernet match)."""
    try:
        target = ipaddress.ip_network(target_prefix, strict=False)
    except ValueError:
        return False
    for key in route_map:
        try:
            net = ipaddress.ip_network(key, strict=False)
            if net == target or net.supernet_of(target):
                return True
        except ValueError:
            continue
    return False


def _detect_pair_anomalies(
    routes_a: list[dict],
    routes_b: list[dict],
    name_a: str,
    name_b: str,
) -> list[dict]:
    anomalies: list[dict] = []

    map_a = {f"{r['destination']}/{r.get('prefix_len', 0)}": r for r in routes_a}
    map_b = {f"{r['destination']}/{r.get('prefix_len', 0)}": r for r in routes_b}

    connected_a = [f"{r['destination']}/{r.get('prefix_len', 0)}" for r in routes_a if r.get("protocol") == "connected"]
    connected_b = [f"{r['destination']}/{r.get('prefix_len', 0)}" for r in routes_b if r.get("protocol") == "connected"]

    # Rota de retorno faltando: rede local de A sem rota em B, e vice-versa
    for prefix in connected_a:
        if prefix in ("0.0.0.0/0", "0.0.0.0/32"):
            continue
        if not _has_covering_route(prefix, map_b):
            anomalies.append({
                "type": "missing_return_route",
                "severity": "high",
                "description": (
                    f"Rede local {prefix} de {name_a} não possui rota correspondente em {name_b}. "
                    f"Tráfego de retorno de {name_b} para {name_a} pode falhar."
                ),
                "details": {"missing_in": name_b, "prefix": prefix, "source": name_a},
                "_scope": "pair",
            })

    for prefix in connected_b:
        if prefix in ("0.0.0.0/0", "0.0.0.0/32"):
            continue
        if not _has_covering_route(prefix, map_a):
            anomalies.append({
                "type": "missing_return_route",
                "severity": "high",
                "description": (
                    f"Rede local {prefix} de {name_b} não possui rota correspondente em {name_a}. "
                    f"Tráfego de retorno de {name_a} para {name_b} pode falhar."
                ),
                "details": {"missing_in": name_a, "prefix": prefix, "source": name_b},
                "_scope": "pair",
            })

    # Roteamento assimétrico: mesmo prefixo, gateways diferentes nos dois lados
    common = set(map_a.keys()) & set(map_b.keys())
    for prefix in common:
        ra = map_a[prefix]
        rb = map_b[prefix]
        gw_a = ra.get("next_hop", "")
        gw_b = rb.get("next_hop", "")
        if (gw_a and gw_b and gw_a != gw_b
                and gw_a != "0.0.0.0" and gw_b != "0.0.0.0"):
            anomalies.append({
                "type": "asymmetric_routing",
                "severity": "medium",
                "description": (
                    f"Prefixo {prefix} usa gateways diferentes nos dois firewalls: "
                    f"{name_a} → {gw_a} ({ra.get('protocol', '?')}) vs "
                    f"{name_b} → {gw_b} ({rb.get('protocol', '?')}). "
                    f"Roteamento assimétrico pode causar problemas com stateful inspection e VPN."
                ),
                "details": {
                    "prefix": prefix,
                    name_a: {"gateway": gw_a, "protocol": ra.get("protocol")},
                    name_b: {"gateway": gw_b, "protocol": rb.get("protocol")},
                },
                "_scope": "pair",
            })

    # Subnet inalcançável: rede local de A sem nenhuma rota em B (nem default)
    has_default_b = any(r.get("destination") in ("0.0.0.0", "") and r.get("prefix_len", 1) == 0 for r in routes_b)
    has_default_a = any(r.get("destination") in ("0.0.0.0", "") and r.get("prefix_len", 1) == 0 for r in routes_a)

    if not has_default_b:
        for prefix in connected_a:
            if prefix in ("0.0.0.0/0", "0.0.0.0/32"):
                continue
            if not _has_covering_route(prefix, map_b):
                anomalies.append({
                    "type": "unreachable_subnet",
                    "severity": "high",
                    "description": (
                        f"Subrede {prefix} de {name_a} é inalcançável a partir de {name_b}: "
                        f"não existe rota específica nem rota padrão. "
                        f"Conectividade ponto-a-ponto comprometida."
                    ),
                    "details": {"subnet": prefix, "unreachable_from": name_b},
                    "_scope": "pair",
                })

    if not has_default_a:
        for prefix in connected_b:
            if prefix in ("0.0.0.0/0", "0.0.0.0/32"):
                continue
            if not _has_covering_route(prefix, map_a):
                anomalies.append({
                    "type": "unreachable_subnet",
                    "severity": "high",
                    "description": (
                        f"Subrede {prefix} de {name_b} é inalcançável a partir de {name_a}: "
                        f"não existe rota específica nem rota padrão. "
                        f"Conectividade ponto-a-ponto comprometida."
                    ),
                    "details": {"subnet": prefix, "unreachable_from": name_a},
                    "_scope": "pair",
                })

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
    # pair mode extras (optional)
    device_b_name: str | None = None,
    device_b_vendor: str | None = None,
    routes_b: list[dict] | None = None,
) -> tuple[str, list[str]]:
    import anthropic

    client = anthropic.AsyncAnthropic()

    payload: dict = {
        "device_a": device_name,
        "vendor_a": vendor,
        "route_count_a": len(routes),
        "routes_sample_a": routes[:20],
        "bgp_peers": bgp_peers,
        "ospf_neighbors": ospf_neighbors,
        "sdwan_services": sdwan_services,
        "anomalies": anomalies,
        "administrative_distances": _AD,
    }
    if device_b_name:
        payload["device_b"] = device_b_name
        payload["vendor_b"] = device_b_vendor
        payload["route_count_b"] = len(routes_b or [])
        payload["routes_sample_b"] = (routes_b or [])[:20]
        payload["analysis_mode"] = "pair"

    msg = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_CLAUDE_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )

    text = msg.content[0].text if msg.content else "{}"
    data = json.loads(text)
    return data.get("summary", ""), data.get("recommendations", [])


# ── Helpers de coleta por vendor ──────────────────────────────────────────────

async def _collect_device_data(device) -> tuple[list, list, list, list]:
    from app.models.device import VendorEnum
    from app.connectors.factory import CLI_VENDORS

    vendor = device.vendor
    if vendor == VendorEnum.fortinet:
        return await _fetch_fortinet_routes(device)
    elif vendor == VendorEnum.sonicwall:
        return await _fetch_sonicwall_routes(device)
    elif vendor == VendorEnum.mikrotik:
        return await _fetch_mikrotik_routes(device)
    elif vendor in CLI_VENDORS:
        return await _fetch_cli_routes(device)
    else:
        raise ValueError(f"Vendor '{vendor.value}' não suportado para análise de conectividade.")


# ── Main analysis runner (called in background) ───────────────────────────────

async def run_analysis(analysis_id: str) -> None:
    import app.models  # noqa: F401 — ensure all models are registered
    from app.database import AsyncSessionLocal
    from app.models.connectivity import ConnectivityAnalysis, ConnectivityStatus
    from app.models.device import Device

    async with AsyncSessionLocal() as db:
        record = await db.get(ConnectivityAnalysis, UUID(analysis_id))
        if not record:
            return

        try:
            device_a = await db.get(Device, record.device_id)
            if not device_a:
                raise ValueError("Dispositivo A não encontrado")

            record.status = ConnectivityStatus.running
            await db.commit()

            # ── Coleta dispositivo A ──────────────────────────────────────────
            routes_a, bgp_a, ospf_a, sdwan_a = await _collect_device_data(device_a)
            anomalies = detect_anomalies(routes_a, bgp_a, ospf_a, sdwan_a)

            record.routes         = routes_a
            record.bgp_peers      = bgp_a
            record.ospf_neighbors = ospf_a
            record.sdwan_services = sdwan_a

            # ── Coleta dispositivo B (modo pair) ──────────────────────────────
            routes_b: list = []
            device_b_error: str | None = None
            device_b: Device | None = None
            if record.mode == "pair" and record.device_b_id:
                device_b = await db.get(Device, record.device_b_id)
                if not device_b:
                    device_b_error = "Dispositivo B não encontrado"
                else:
                    try:
                        routes_b, bgp_b, ospf_b, sdwan_b = await _collect_device_data(device_b)
                        anomalies_b = detect_anomalies(routes_b, bgp_b, ospf_b, sdwan_b)

                        # Tag anomalias com o dispositivo de origem
                        for a in anomalies:
                            a.setdefault("_device", device_a.name)
                        for a in anomalies_b:
                            a.setdefault("_device", device_b.name)

                        pair_anomalies = _detect_pair_anomalies(
                            routes_a, routes_b, device_a.name, device_b.name
                        )

                        anomalies = anomalies + anomalies_b + pair_anomalies

                        record.device_b_routes          = routes_b
                        record.device_b_bgp_peers       = bgp_b
                        record.device_b_ospf_neighbors  = ospf_b
                        record.device_b_sdwan_services  = sdwan_b
                    except Exception as exc_b:
                        device_b_error = f"Falha ao coletar dados do dispositivo B ({device_b.name}): {exc_b}"
                        log.warning("Pair analysis %s — device B failed: %s", analysis_id, exc_b)

            # ── Análise IA ────────────────────────────────────────────────────
            ai_summary, ai_recs = "", []
            try:
                ai_summary, ai_recs = await _claude_analysis(
                    device_name=device_a.name,
                    vendor=device_a.vendor.value,
                    routes=routes_a,
                    bgp_peers=bgp_a,
                    ospf_neighbors=ospf_a,
                    sdwan_services=sdwan_a,
                    anomalies=anomalies,
                    device_b_name=device_b.name if device_b else None,
                    device_b_vendor=device_b.vendor.value if device_b else None,
                    routes_b=routes_b if routes_b else None,
                )
            except Exception as exc:
                log.warning("Claude analysis failed for connectivity %s: %s", analysis_id, exc)
                ai_summary = "Análise IA indisponível."
                ai_recs = []

            record.anomalies          = anomalies
            record.ai_summary         = ai_summary
            record.ai_recommendations = ai_recs
            record.status             = ConnectivityStatus.completed
            record.error              = device_b_error
            record.completed_at       = datetime.now(timezone.utc)

        except Exception as exc:
            log.exception("Connectivity analysis %s failed: %s", analysis_id, exc)
            record.status = ConnectivityStatus.failed
            record.error  = str(exc)
            record.completed_at = datetime.now(timezone.utc)

        await db.commit()
