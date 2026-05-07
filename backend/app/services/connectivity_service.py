"""Fase 18 — Network Connectivity Analysis service.

Collects routing tables, BGP/OSPF peer state, and SD-WAN status from
firewall and switch devices, then detects anomalies and generates an
AI summary via Claude.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

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

async def _fetch_fortinet_routes(device) -> tuple[list[dict], list[dict], list[dict]]:
    from app.connectors.factory import get_connector
    from app.utils.crypto import decrypt_credentials

    creds = decrypt_credentials(device.encrypted_credentials)
    vdom = creds.get("vdom") or "root"
    base = f"{'https' if device.use_ssl else 'http'}://{device.host}:{device.port}"
    token = creds.get("token") or ""
    headers = {"Authorization": f"Bearer {token}"}

    import httpx
    verify = device.verify_ssl if device.verify_ssl is not None else False
    routes, bgp_peers, ospf_neighbors = [], [], []

    async with httpx.AsyncClient(verify=verify, timeout=30) as client:
        try:
            r = await client.get(f"{base}/api/v2/monitor/router/ipv4?vdom={vdom}", headers=headers)
            if r.status_code == 200:
                data = r.json()
                for entry in data.get("results", []):
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

    return routes, bgp_peers, ospf_neighbors


async def _fetch_sonicwall_routes(device) -> tuple[list[dict], list[dict], list[dict]]:
    from app.utils.crypto import decrypt_credentials
    import httpx

    creds = decrypt_credentials(device.encrypted_credentials)
    base = f"{'https' if device.use_ssl else 'http'}://{device.host}:{device.port}"
    verify = device.verify_ssl if device.verify_ssl is not None else False
    username = creds.get("username", "")
    password = creds.get("password", "")
    routes, bgp_peers, ospf_neighbors = [], [], []

    async with httpx.AsyncClient(verify=verify, timeout=30) as client:
        try:
            # Authenticate (Digest)
            auth_r = await client.post(
                f"{base}/api/sonicos/auth",
                auth=httpx.DigestAuth(username, password),
            )
            if auth_r.status_code not in (200, 201):
                raise ValueError(f"SonicWall auth falhou: HTTP {auth_r.status_code}")

            cookies = auth_r.cookies

            # Static / connected routes
            r = await client.get(f"{base}/api/sonicos/route/ipv4", cookies=cookies)
            if r.status_code == 200:
                data = r.json()
                for entry in data.get("route_ipv4", {}).get("route", []):
                    dst = entry.get("destination", {})
                    ip   = dst.get("ip", "0.0.0.0")
                    mask = dst.get("mask", "0.0.0.0")
                    plen = _mask_to_plen(mask)
                    gw   = entry.get("gateway", "0.0.0.0")
                    routes.append({
                        "destination": ip,
                        "prefix_len": plen,
                        "next_hop": gw,
                        "interface": entry.get("interface", None),
                        "protocol": entry.get("type", "static").lower(),
                        "active": True,
                    })

            # Logout
            await client.delete(f"{base}/api/sonicos/auth", cookies=cookies)

        except Exception as e:
            log.debug("SonicWall route fetch error: %s", e)
            raise ValueError(f"SonicWall REST: {e}") from e

    return routes, bgp_peers, ospf_neighbors


async def _fetch_mikrotik_routes(device) -> tuple[list[dict], list[dict], list[dict]]:
    from app.utils.crypto import decrypt_credentials

    creds = decrypt_credentials(device.encrypted_credentials)
    base = f"{'https' if device.use_ssl else 'http'}://{device.host}:{device.port}"
    auth = (creds.get("username", ""), creds.get("password", ""))
    verify = device.verify_ssl if device.verify_ssl is not None else False

    import httpx
    routes, bgp_peers, ospf_neighbors = [], [], []

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

    return routes, bgp_peers, ospf_neighbors


# ── CLI-based data collection ──────────────────────────────────────────────────

async def _fetch_cli_routes(device) -> tuple[list[dict], list[dict], list[dict]]:
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

    return routes, bgp_peers, ospf_neighbors


# ── Anomaly detection ─────────────────────────────────────────────────────────

def detect_anomalies(
    routes: list[dict],
    bgp_peers: list[dict],
    ospf_neighbors: list[dict],
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

    return anomalies


# ── Claude AI analysis ────────────────────────────────────────────────────────

async def _claude_analysis(
    device_name: str,
    vendor: str,
    routes: list[dict],
    bgp_peers: list[dict],
    ospf_neighbors: list[dict],
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
        "anomalies": anomalies,
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
                routes, bgp_peers, ospf_neighbors = await _fetch_fortinet_routes(device)
            elif vendor == VendorEnum.sonicwall:
                routes, bgp_peers, ospf_neighbors = await _fetch_sonicwall_routes(device)
            elif vendor == VendorEnum.mikrotik:
                routes, bgp_peers, ospf_neighbors = await _fetch_mikrotik_routes(device)
            elif vendor in CLI_VENDORS:
                routes, bgp_peers, ospf_neighbors = await _fetch_cli_routes(device)
            else:
                raise ValueError(f"Vendor '{vendor.value}' não suportado para análise de conectividade ainda.")

            anomalies = detect_anomalies(routes, bgp_peers, ospf_neighbors)

            ai_summary, ai_recs = "", []
            try:
                ai_summary, ai_recs = await _claude_analysis(
                    device_name=device.name,
                    vendor=vendor.value,
                    routes=routes,
                    bgp_peers=bgp_peers,
                    ospf_neighbors=ospf_neighbors,
                    anomalies=anomalies,
                )
            except Exception as exc:
                log.warning("Claude analysis failed for connectivity %s: %s", analysis_id, exc)
                ai_summary = "Análise IA indisponível."
                ai_recs = []

            record.routes          = routes
            record.bgp_peers       = bgp_peers
            record.ospf_neighbors  = ospf_neighbors
            record.sdwan_services  = []
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
