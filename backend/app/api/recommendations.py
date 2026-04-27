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
    "gateway anti-virus":        "gateway_antivirus",
    "anti-spyware":              "anti_spyware",
    "intrusion prevention (ips)":"intrusion_prevention",
    "app control":               "app_control",
    "geo-ip filter":             "geo_ip",
    "botnet filter":             "botnet",
    "dpi-ssl":                   "dpi_ssl",
}


# ── IP overlap helpers ────────────────────────────────────────────────────────

def _ip_contains(broader: str, narrower: str) -> bool:
    try:
        b = ipaddress.ip_network(broader, strict=False)
        n = ipaddress.ip_network(narrower, strict=False)
        return n.subnet_of(b)
    except (ValueError, TypeError):
        return False


def _field_shadows(a_val: str, b_val: str) -> bool:
    av = a_val.lower()
    if av == "any":
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


# ── Individual checks ─────────────────────────────────────────────────────────

def _check_group_opportunities(rules: list[FirewallRule]) -> list[dict]:
    groups: dict[tuple, list[FirewallRule]] = defaultdict(list)
    for r in rules:
        if not r.enabled or r.action.lower() != "allow":
            continue
        key = (
            (r.src_zone or "").upper(),
            (r.dst_zone or "").upper(),
            r.dst,
            r.service,
        )
        groups[key].append(r)

    results = []
    for (src_zone, dst_zone, dst, service), grp in groups.items():
        srcs = [r.src for r in grp if r.src.lower() != "any"]
        if len(srcs) < 2:
            continue
        names = [r.name for r in grp]
        safe_dst = dst.replace(" ", "_").upper()
        group_name = f"GRP_{safe_dst}_ORIGENS"
        route = f"{src_zone}→{dst_zone}" if src_zone and dst_zone else "mesma zona"
        results.append({
            "id": f"group_src_{dst}_{service}",
            "severity": "medium",
            "title": f"{len(grp)} regras com mesmo destino podem ser agrupadas",
            "description": (
                f'As regras abaixo têm destino "{dst}", serviço "{service}" ({route}) '
                f"e origens diferentes: {', '.join(srcs)}. "
                "Consolidar em um grupo de endereços reduz duplicação e simplifica auditorias."
            ),
            "affected_rules": names,
            "agent_seed": (
                f'Quero criar um grupo de endereços chamado "{group_name}" '
                f"com os objetos {', '.join(srcs)} e consolidar as regras "
                f"{', '.join(names)} em uma única regra — "
            ),
            "manual_hint": (
                f"# 1. Criar grupo de endereços\n"
                f"address-object group {group_name}\n"
                + "".join(f"  member {s}\n" for s in srcs)
                + f"\n# 2. Criar regra consolidada\n"
                f"access-rule {src_zone} {dst_zone} {group_name} {dst} {service} allow\n"
                + "".join(f"\n# 3. Remover regra duplicada: {n}" for n in names)
            ),
        })
    return results


def _check_any_source_internal(rules: list[FirewallRule]) -> list[dict]:
    issues = []
    for r in rules:
        if not r.enabled or r.action.lower() != "allow":
            continue
        if r.src.lower() != "any":
            continue
        dst_zone = (r.dst_zone or "").upper()
        if any(dst_zone.startswith(z) for z in _INTERNAL_ZONES):
            issues.append(r.name)
    if not issues:
        return []
    return [{
        "id": "any_src_internal",
        "severity": "high",
        "title": f"{len(issues)} regra(s) permitem qualquer origem para zonas internas",
        "description": (
            'Regras com origem "Any" permitem que qualquer endereço IP alcance zonas internas '
            "(LAN, DMZ, WLAN). Restrinja a origem ao menor conjunto de endereços necessário."
        ),
        "affected_rules": issues,
        "agent_seed": (
            f"Quero revisar as regras {', '.join(issues)} que usam origem Any para zonas internas. "
            "Ajude-me a restringir a origem ao mínimo necessário — "
        ),
        "manual_hint": (
            "# Substituir origem Any por objeto específico:\n"
            "access-rule <zona_orig> <zona_dest> <objeto_especifico> <destino> <serviço> allow\n\n"
            "# Remover regra antiga:\n"
            "no access-rule <uuid_regra>"
        ),
    }]


def _check_any_service_wan(rules: list[FirewallRule]) -> list[dict]:
    issues = []
    for r in rules:
        if not r.enabled or r.action.lower() != "allow":
            continue
        if r.service.lower() != "any":
            continue
        dst_zone = (r.dst_zone or "").upper()
        if "WAN" in dst_zone or not dst_zone:
            issues.append(r.name)
    if not issues:
        return []
    return [{
        "id": "any_service_wan",
        "severity": "high",
        "title": f"{len(issues)} regra(s) permitem qualquer serviço para WAN",
        "description": (
            'Regras com serviço "Any" saindo para a WAN expõem todos os protocolos e portas. '
            "Restrinja ao conjunto mínimo de portas necessárias para cada fluxo."
        ),
        "affected_rules": issues,
        "agent_seed": (
            f"Quero revisar as regras {', '.join(issues)} que usam serviço Any para WAN. "
            "Ajude-me a especificar apenas os serviços necessários — "
        ),
        "manual_hint": (
            "# Criar objeto de serviço específico:\n"
            "service-object TCP <nome> <porta_inicio> <porta_fim>\n\n"
            "# Substituir na regra:\n"
            "access-rule <zona_orig> WAN <origem> <destino> <servico_especifico> allow"
        ),
    }]


def _check_shadow_rules(rules: list[FirewallRule]) -> list[dict]:
    active = [r for r in rules if r.enabled]
    shadows: list[dict] = []
    seen: set[str] = set()

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
                    shadows.append({"shadowed": later.name, "by": earlier.name})

    if not shadows:
        return []

    detail = "\n".join(
        f'  • "{s["shadowed"]}" → encoberta por "{s["by"]}"' for s in shadows
    )
    shadowed_names = [s["shadowed"] for s in shadows]
    return [{
        "id": "shadow_rules",
        "severity": "high",
        "title": f"{len(shadows)} regra(s) inatingível(is) — shadow rules",
        "description": (
            "As regras abaixo nunca serão avaliadas porque uma regra anterior mais genérica "
            "já captura o mesmo tráfego. Revise a ordem ou remova as redundantes.\n\n"
            + detail
        ),
        "affected_rules": shadowed_names,
        "agent_seed": (
            f"Tenho shadow rules (regras inatingíveis): {', '.join(shadowed_names)}. "
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


def _check_dpi_ssl(rules: list[FirewallRule]) -> list[dict]:
    issues = []
    for r in rules:
        if not r.enabled or r.action.lower() != "allow":
            continue
        src_zone = (r.src_zone or "").upper()
        dst_zone = (r.dst_zone or "").upper()
        if "WAN" not in src_zone and "WAN" not in dst_zone:
            continue
        raw_action = r.raw.get("action", {})
        if not isinstance(raw_action, dict):
            continue
        client = raw_action.get("dpi_ssl_client", None)
        server = raw_action.get("dpi_ssl_server", None)
        # Only flag if fields exist and are explicitly False
        if client is False or server is False:
            issues.append(r.name)
    if not issues:
        return []
    return [{
        "id": "dpi_ssl_disabled",
        "severity": "high",
        "title": f"{len(issues)} regra(s) cruzam a WAN sem inspeção DPI-SSL",
        "description": (
            "Regras WAN com DPI-SSL desativado permitem tráfego HTTPS sem inspeção de conteúdo, "
            "possibilitando exfiltração de dados e malware em túneis TLS. "
            "Ative DPI-SSL Client e/ou Server nessas regras."
        ),
        "affected_rules": issues,
        "agent_seed": (
            f"Quero ativar a inspeção DPI-SSL nas regras {', '.join(issues)} que cruzam a WAN — "
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


def _check_disabled_rules(rules: list[FirewallRule]) -> list[dict]:
    disabled = [r.name for r in rules if not r.enabled]
    if not disabled:
        return []
    return [{
        "id": "disabled_rules",
        "severity": "low",
        "title": f"{len(disabled)} regra(s) desativada(s) — candidatas à remoção",
        "description": (
            "Regras desativadas não afetam o tráfego mas ocupam espaço na política e podem "
            "causar confusão durante auditorias. Revise se ainda são necessárias."
        ),
        "affected_rules": disabled,
        "agent_seed": (
            f"Quero revisar e possivelmente remover as regras desativadas: {', '.join(disabled)} — "
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
    rules: list[FirewallRule], security_enabled: dict[str, bool]
) -> list[dict]:
    if not security_enabled:
        return []
    key_services = ["gateway_antivirus", "anti_spyware", "intrusion_prevention"]
    disabled = [k for k in key_services if security_enabled.get(k) is False]
    if not disabled:
        return []

    wan_to_lan = [
        r.name for r in rules
        if r.enabled
        and r.action.lower() == "allow"
        and (r.src_zone or "").upper() == "WAN"
        and any((r.dst_zone or "").upper().startswith(z) for z in _INTERNAL_ZONES)
    ]
    if not wan_to_lan:
        return []

    label_map = {
        "gateway_antivirus": "Gateway Anti-Virus",
        "anti_spyware": "Anti-Spyware",
        "intrusion_prevention": "Intrusion Prevention (IPS)",
    }
    off_labels = [label_map.get(k, k) for k in disabled]
    return [{
        "id": "wan_lan_no_inspection",
        "severity": "high",
        "title": f"{len(wan_to_lan)} regra(s) WAN→LAN com serviços de segurança desativados",
        "description": (
            f"As regras abaixo permitem tráfego da WAN para zonas internas, mas os seguintes "
            f"serviços estão desativados globalmente: {', '.join(off_labels)}. "
            "Todo tráfego entrante passa sem inspeção."
        ),
        "affected_rules": wan_to_lan,
        "agent_seed": (
            f"Quero ativar {', '.join(off_labels)} que estão desativados e que protegem "
            f"as regras WAN→LAN: {', '.join(wan_to_lan)} — "
        ),
        "manual_hint": (
            "# Ativar serviços de segurança via SSH:\n"
            + "".join(f"security-service {k.replace('_', '-')} enable\n" for k in disabled)
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

    # Security status — non-fatal, best-effort via SSH
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
    checks.extend(_check_any_source_internal(rules))
    checks.extend(_check_any_service_wan(rules))
    checks.extend(_check_shadow_rules(rules))
    checks.extend(_check_dpi_ssl(rules))
    checks.extend(_check_wan_lan_no_inspection(rules, security_enabled))
    checks.extend(_check_group_opportunities(rules))
    checks.extend(_check_disabled_rules(rules))

    _order = {"high": 0, "medium": 1, "low": 2}
    checks.sort(key=lambda c: _order.get(c["severity"], 9))

    return {
        "total": len(checks),
        "rules_analyzed": len(rules),
        "security_fetched": bool(security_enabled),
        "checks": checks,
    }
