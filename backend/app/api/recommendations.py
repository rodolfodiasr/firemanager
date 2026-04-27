import ipaddress
from collections import defaultdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.inspect import _SECURITY_COMMANDS
from app.connectors.base import FirewallRule
from app.connectors.factory import get_connector, get_ssh_connector
from app.database import get_db
from app.models.device import Device
from app.models.user import User

router = APIRouter()

_INTERNAL_ZONES = {"LAN", "DMZ", "WLAN", "MGMT", "VOIP", "TRUSTED"}

_SECURITY_LABEL_MAP = {
    "gateway anti-virus":         "gateway_antivirus",
    "anti-spyware":               "anti_spyware",
    "intrusion prevention (ips)": "intrusion_prevention",
    "app control":                "app_control",
    "geo-ip filter":              "geo_ip",
    "botnet filter":              "botnet",
    "dpi-ssl":                    "dpi_ssl",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ip_contains(broader: str, narrower: str) -> bool:
    try:
        b = ipaddress.ip_network(broader, strict=False)
        n = ipaddress.ip_network(narrower, strict=False)
        return n.subnet_of(b)
    except (ValueError, TypeError):
        return False


def _field_shadows(a_val: str, b_val: str) -> bool:
    if a_val.lower() == "any":
        return True
    if a_val == b_val:
        return True
    return _ip_contains(a_val, b_val)


def _zone_pair_matches(a: FirewallRule, b: FirewallRule) -> bool:
    az_src = (a.src_zone or "").upper()
    bz_src = (b.src_zone or "").upper()
    az_dst = (a.dst_zone or "").upper()
    bz_dst = (b.dst_zone or "").upper()
    if az_src and bz_src and az_src != bz_src:
        return False
    if az_dst and bz_dst and az_dst != bz_dst:
        return False
    return True


def _rule_to_dict(rule: FirewallRule, pos_map: dict[str, int]) -> dict:
    return {
        "pos":      pos_map.get(rule.rule_id),
        "rule_id":  rule.rule_id,
        "name":     rule.name,
        "src_zone": rule.src_zone,
        "dst_zone": rule.dst_zone,
        "src":      rule.src,
        "dst":      rule.dst,
        "service":  rule.service,
        "action":   rule.action,
        "enabled":  rule.enabled,
        "hit_count": rule.hit_count,
    }


def _names(affected: list[dict]) -> str:
    return ", ".join(r["name"] for r in affected)


# ── Checks ────────────────────────────────────────────────────────────────────

def _check_group_opportunities(rules: list[FirewallRule], pos_map: dict[str, int]) -> list[dict]:
    groups: dict[tuple, list[FirewallRule]] = defaultdict(list)
    for r in rules:
        if not r.enabled or r.action.lower() != "allow":
            continue
        key = ((r.src_zone or "").upper(), (r.dst_zone or "").upper(), r.dst, r.service)
        groups[key].append(r)

    results = []
    for (src_zone, dst_zone, dst, service), grp in groups.items():
        srcs = [r.src for r in grp if r.src.lower() != "any"]
        if len(srcs) < 2:
            continue
        affected = [_rule_to_dict(r, pos_map) for r in grp]
        safe_dst  = dst.replace(" ", "_").upper()
        group_name = f"GRP_{safe_dst}_ORIGENS"
        route = f"{src_zone}→{dst_zone}" if src_zone and dst_zone else "mesma zona"
        results.append({
            "id":       f"group_src_{dst}_{service}",
            "severity": "medium",
            "title":    f"{len(grp)} regras com mesmo destino podem ser agrupadas",
            "description": (
                f'Destino "{dst}", serviço "{service}" ({route}). '
                f"Origens diferentes: {', '.join(srcs)}. "
                "Criar um address group consolida em uma única regra."
            ),
            "affected_rules": affected,
            "agent_seed": (
                f'Quero criar um grupo de endereços chamado "{group_name}" '
                f"com os objetos {', '.join(srcs)} e consolidar as regras "
                f"{_names(affected)} em uma única regra — "
            ),
            "manual_hint": (
                f"# 1. Criar grupo de endereços\n"
                f"address-object group {group_name}\n"
                + "".join(f"  member {s}\n" for s in srcs)
                + f"\n# 2. Criar regra consolidada\n"
                f"access-rule {src_zone} {dst_zone} {group_name} {dst} {service} allow\n"
                + "".join(f"\n# 3. Remover regra duplicada: {r['name']}" for r in affected)
            ),
        })
    return results


def _check_any_source_internal(rules: list[FirewallRule], pos_map: dict[str, int]) -> list[dict]:
    matched = [
        r for r in rules
        if r.enabled
        and r.action.lower() == "allow"
        and r.src.lower() == "any"
        and any((r.dst_zone or "").upper().startswith(z) for z in _INTERNAL_ZONES)
    ]
    if not matched:
        return []
    affected = [_rule_to_dict(r, pos_map) for r in matched]
    return [{
        "id":       "any_src_internal",
        "severity": "high",
        "title":    f"{len(matched)} regra(s) permitem qualquer origem para zonas internas",
        "description": (
            'Origem "Any" permite que qualquer IP alcance zonas internas (LAN, DMZ, WLAN). '
            "Restrinja ao menor conjunto de endereços necessário."
        ),
        "affected_rules": affected,
        "agent_seed": (
            f"Quero revisar as regras {_names(affected)} que usam origem Any para zonas internas. "
            "Ajude-me a restringir a origem ao mínimo necessário — "
        ),
        "manual_hint": (
            "# Substituir origem Any por objeto específico:\n"
            "access-rule <zona_orig> <zona_dest> <objeto_especifico> <destino> <serviço> allow\n\n"
            "# Remover regra antiga:\n"
            "no access-rule <uuid_regra>"
        ),
    }]


def _check_any_service_wan(rules: list[FirewallRule], pos_map: dict[str, int]) -> list[dict]:
    matched = [
        r for r in rules
        if r.enabled
        and r.action.lower() == "allow"
        and r.service.lower() == "any"
        and ("WAN" in (r.dst_zone or "").upper() or not r.dst_zone)
    ]
    if not matched:
        return []
    affected = [_rule_to_dict(r, pos_map) for r in matched]
    return [{
        "id":       "any_service_wan",
        "severity": "high",
        "title":    f"{len(matched)} regra(s) permitem qualquer serviço para WAN",
        "description": (
            'Serviço "Any" para WAN expõe todos os protocolos e portas. '
            "Restrinja ao conjunto mínimo de serviços necessários."
        ),
        "affected_rules": affected,
        "agent_seed": (
            f"Quero revisar as regras {_names(affected)} que usam serviço Any para WAN. "
            "Ajude-me a especificar apenas os serviços necessários — "
        ),
        "manual_hint": (
            "# Criar objeto de serviço específico:\n"
            "service-object TCP <nome> <porta_inicio> <porta_fim>\n\n"
            "# Substituir na regra:\n"
            "access-rule <zona_orig> WAN <origem> <destino> <servico_especifico> allow"
        ),
    }]


def _check_shadow_rules(rules: list[FirewallRule], pos_map: dict[str, int]) -> list[dict]:
    active = [r for r in rules if r.enabled]
    shadows: list[dict] = []
    seen: set[str] = set()
    by_map: dict[str, str] = {}

    for j, later in enumerate(active):
        for earlier in active[:j]:
            if not _zone_pair_matches(earlier, later):
                continue
            if (
                _field_shadows(earlier.src, later.src)
                and _field_shadows(earlier.dst, later.dst)
                and _field_shadows(earlier.service, later.service)
            ):
                if later.name not in seen:
                    seen.add(later.name)
                    shadows.append({"shadowed": later, "by": earlier})
                    by_map[later.name] = earlier.name

    if not shadows:
        return []

    detail = "\n".join(
        f'  • "{s["shadowed"].name}" → encoberta por "{s["by"].name}"' for s in shadows
    )
    shadowed_rules = [s["shadowed"] for s in shadows]
    affected = [_rule_to_dict(r, pos_map) for r in shadowed_rules]
    # Annotate each affected rule with which rule shadows it
    for a in affected:
        a["shadowed_by"] = by_map.get(a["name"])

    return [{
        "id":       "shadow_rules",
        "severity": "high",
        "title":    f"{len(shadows)} regra(s) inatingível(is) — shadow rules",
        "description": (
            "As regras abaixo nunca serão avaliadas porque uma regra anterior mais genérica "
            "já captura o mesmo tráfego. Revise a ordem ou remova as redundantes.\n\n"
            + detail
        ),
        "affected_rules": affected,
        "agent_seed": (
            f"Tenho shadow rules (regras inatingíveis): {_names(affected)}. "
            "Ajude-me a reordenar ou remover as regras redundantes — "
        ),
        "manual_hint": (
            "# Mover regra específica para ANTES da regra geral:\n"
            "# GUI: Security > Access Rules > arrastar regra acima da geral\n\n"
            "# Remover shadow rule (se realmente redundante):\n"
            "no access-rule <uuid_regra_shadow>\n"
            "commit"
        ),
    }]


def _check_dpi_ssl(rules: list[FirewallRule], pos_map: dict[str, int]) -> list[dict]:
    matched = []
    for r in rules:
        if not r.enabled or r.action.lower() != "allow":
            continue
        if "WAN" not in (r.src_zone or "").upper() and "WAN" not in (r.dst_zone or "").upper():
            continue
        raw_action = r.raw.get("action", {})
        if not isinstance(raw_action, dict):
            continue
        if raw_action.get("dpi_ssl_client") is False or raw_action.get("dpi_ssl_server") is False:
            matched.append(r)
    if not matched:
        return []
    affected = [_rule_to_dict(r, pos_map) for r in matched]
    return [{
        "id":       "dpi_ssl_disabled",
        "severity": "high",
        "title":    f"{len(matched)} regra(s) cruzam a WAN sem inspeção DPI-SSL",
        "description": (
            "DPI-SSL desativado permite tráfego HTTPS sem inspeção de conteúdo, "
            "possibilitando exfiltração e malware em túneis TLS."
        ),
        "affected_rules": affected,
        "agent_seed": (
            f"Quero ativar a inspeção DPI-SSL nas regras {_names(affected)} que cruzam a WAN — "
        ),
        "manual_hint": (
            "# GUI: Security > Access Rules > editar regra > aba Advanced\n"
            "# Ativar: DPI SSL (Client) e DPI SSL (Server)\n\n"
            "# Via API REST (PUT /api/sonicos/access-rules/ipv4/uuid/<id>):\n"
            '{\n'
            '  "access_rules": [{\n'
            '    "ipv4": {\n'
            '      "action": { "dpi_ssl_client": true, "dpi_ssl_server": true }\n'
            '    }\n'
            '  }]\n'
            '}'
        ),
    }]


def _check_disabled_rules(rules: list[FirewallRule], pos_map: dict[str, int]) -> list[dict]:
    disabled = [r for r in rules if not r.enabled]
    if not disabled:
        return []

    zero_hit = sum(1 for r in disabled if r.hit_count == 0)
    has_hit  = sum(1 for r in disabled if r.hit_count and r.hit_count > 0)
    unknown  = sum(1 for r in disabled if r.hit_count is None)

    notes = []
    if zero_hit:
        notes.append(f"{zero_hit} com zero hits — nunca usadas")
    if has_hit:
        notes.append(f"{has_hit} com hits registrados — avaliar necessidade")
    if unknown:
        notes.append(f"{unknown} sem dados de hits")

    affected = [_rule_to_dict(r, pos_map) for r in disabled]
    return [{
        "id":       "disabled_rules",
        "severity": "low",
        "title":    f"{len(disabled)} regra(s) desativada(s) — candidatas à remoção",
        "description": (
            "Regras desativadas não afetam o tráfego mas ocupam espaço na política. "
            + (" · ".join(notes) if notes else "Revise se ainda são necessárias.")
        ),
        "affected_rules": affected,
        "agent_seed": (
            f"Quero revisar e possivelmente remover as regras desativadas: {_names(affected)} — "
        ),
        "manual_hint": (
            "# Listar regras desativadas:\n"
            "show access-rules ipv4\n\n"
            "# Remover regra desativada:\n"
            "no access-rule <uuid_da_regra>\n"
            "commit"
        ),
    }]


def _check_wan_lan_no_inspection(
    rules: list[FirewallRule], pos_map: dict[str, int], security_enabled: dict[str, bool]
) -> list[dict]:
    if not security_enabled:
        return []
    key_services = ["gateway_antivirus", "anti_spyware", "intrusion_prevention"]
    disabled_svcs = [k for k in key_services if security_enabled.get(k) is False]
    if not disabled_svcs:
        return []

    matched = [
        r for r in rules
        if r.enabled
        and r.action.lower() == "allow"
        and (r.src_zone or "").upper() == "WAN"
        and any((r.dst_zone or "").upper().startswith(z) for z in _INTERNAL_ZONES)
    ]
    if not matched:
        return []

    label_map = {
        "gateway_antivirus":   "Gateway Anti-Virus",
        "anti_spyware":        "Anti-Spyware",
        "intrusion_prevention":"Intrusion Prevention (IPS)",
    }
    off_labels = [label_map.get(k, k) for k in disabled_svcs]
    affected = [_rule_to_dict(r, pos_map) for r in matched]
    return [{
        "id":       "wan_lan_no_inspection",
        "severity": "high",
        "title":    f"{len(matched)} regra(s) WAN→LAN com serviços de segurança desativados",
        "description": (
            f"Serviços desativados globalmente: {', '.join(off_labels)}. "
            "Todo tráfego WAN→LAN passa sem inspeção."
        ),
        "affected_rules": affected,
        "agent_seed": (
            f"Quero ativar {', '.join(off_labels)} que estão desativados e que protegem "
            f"as regras WAN→LAN: {_names(affected)} — "
        ),
        "manual_hint": (
            "# Ativar serviços de segurança via SSH:\n"
            + "".join(f"security-service {k.replace('_', '-')} enable\n" for k in disabled_svcs)
            + "commit"
        ),
    }]


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/{device_id}/recommendations")
async def get_recommendations(
    device_id: UUID,
    _: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> dict:
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado.")

    try:
        connector = get_connector(device)
        rules = await connector.list_rules()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao buscar regras: {exc}")

    # Position map: rule_id → 1-based index in device policy order
    pos_map = {r.rule_id: i + 1 for i, r in enumerate(rules)}

    # Enrich rules with hit counts — best-effort
    stats_fetched = False
    try:
        rule_stats = await connector.get_rule_statistics()
        if rule_stats:
            stats_fetched = True
            for rule in rules:
                if rule.rule_id in rule_stats:
                    rule.hit_count = rule_stats[rule.rule_id]
                else:
                    for rid, count in rule_stats.items():
                        if rid == rule.name:
                            rule.hit_count = count
                            break
    except Exception:
        pass

    # Security status — non-fatal via SSH
    security_enabled: dict[str, bool] = {}
    try:
        ssh = get_ssh_connector(device)
        ssh_result = await ssh.execute_show_commands(_SECURITY_COMMANDS)
        if ssh_result.success:
            from app.services.operation_service import _parse_security_status
            for item in _parse_security_status(_SECURITY_COMMANDS, ssh_result.output):
                key = _SECURITY_LABEL_MAP.get(item["service"].lower())
                if key and item["enabled"] is not None:
                    security_enabled[key] = item["enabled"]
    except Exception:
        pass

    checks: list[dict] = []
    checks.extend(_check_any_source_internal(rules, pos_map))
    checks.extend(_check_any_service_wan(rules, pos_map))
    checks.extend(_check_shadow_rules(rules, pos_map))
    checks.extend(_check_dpi_ssl(rules, pos_map))
    checks.extend(_check_wan_lan_no_inspection(rules, pos_map, security_enabled))
    checks.extend(_check_group_opportunities(rules, pos_map))
    checks.extend(_check_disabled_rules(rules, pos_map))

    _order = {"high": 0, "medium": 1, "low": 2}
    checks.sort(key=lambda c: _order.get(c["severity"], 9))

    return {
        "total":            len(checks),
        "rules_analyzed":   len(rules),
        "security_fetched": bool(security_enabled),
        "stats_fetched":    stats_fetched,
        "checks":           checks,
    }
