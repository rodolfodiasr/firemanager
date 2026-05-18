"""Celery tasks for firewall rule migration: analyze (fetch + parse + Claude) and apply."""
import asyncio
import json
import logging
import re
from uuid import UUID

from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)

_CLAUDE_SYSTEM = """Você é especialista em migração de regras de firewall entre diferentes fabricantes.

Receberá:
1. Vendor de origem e vendor de destino
2. IR (Intermediate Representation) extraído automaticamente — pode estar incompleto
3. Comandos CLI gerados automaticamente para o firewall de destino

Sua tarefa:
- Revise os objetos de endereço, grupos, serviços, políticas e NAT gerados
- Corrija sintaxe incorreta para o vendor destino
- Preencha lacunas que o parser automático não conseguiu extrair
- Garanta ordem correta (objetos devem ser criados antes de serem referenciados)
- Adicione comandos de salvamento obrigatórios (write memory, save, commit)
- Remova duplicatas ou referências a objetos inexistentes
- Marque regras problemáticas com warnings
- Se não conseguir traduzir algo, explique em warnings

Retorne SOMENTE JSON válido, sem texto adicional:
{
  "commands_revised": ["cmd1", "cmd2", ...],
  "warnings": ["aviso 1", "aviso 2"]
}

Se os comandos já estiverem completos e corretos, retorne-os sem alteração."""

_SHOW_RULES_CMD = {
    "fortinet":  "show full-configuration",
    "sonicwall": None,   # REST-based — fetched via connector
    "sophos":    None,   # REST-based — fetched via connector
}

_REST_VENDORS = {"sonicwall", "sophos"}


@celery_app.task(
    name="app.workers.firewall_migration_worker.analyze_firewall_migration",
    bind=True, soft_time_limit=300, time_limit=360,
)
def analyze_firewall_migration(self, migration_id: str) -> dict:
    return asyncio.run(_async_analyze(migration_id))


@celery_app.task(
    name="app.workers.firewall_migration_worker.apply_firewall_migration",
    bind=True, soft_time_limit=300, time_limit=360,
)
def apply_firewall_migration(self, migration_id: str) -> dict:
    return asyncio.run(_async_apply(migration_id))


async def _async_analyze(migration_id: str) -> dict:
    import app.models  # noqa: F401
    from app.database import AsyncSessionLocal
    from app.models.firewall_migration import FirewallMigration, FirewallMigrationStatus
    from app.models.device import Device
    from app.services.firewall_parser import parse_firewall_rules
    from app.services.firewall_renderer import render_firewall_rules

    async with AsyncSessionLocal() as db:
        row = await db.get(FirewallMigration, UUID(migration_id))
        if not row:
            return {"error": "Migration not found"}

        try:
            src_dev = await db.get(Device, row.source_device_id)
            if not src_dev:
                raise ValueError("Dispositivo de origem não encontrado")

            source_vendor = row.source_vendor
            raw_rules = ""

            if source_vendor in _REST_VENDORS:
                raw_rules = await _fetch_rules_rest(src_dev)
            else:
                show_cmd = _SHOW_RULES_CMD.get(source_vendor, "show full-configuration")
                from app.connectors.factory import get_ssh_connector
                connector = get_ssh_connector(src_dev)
                result = await connector.execute_show_commands([show_cmd])
                if not result.success:
                    raise ValueError(f"Falha ao buscar config: {result.error}")
                raw_rules = result.output

            row.source_rules_raw = raw_rules if isinstance(raw_rules, str) else json.dumps(raw_rules, ensure_ascii=False)

            ir = parse_firewall_rules(source_vendor, raw_rules if isinstance(raw_rules, str) else json.dumps(raw_rules))
            row.migration_plan = ir

            target_vendor = row.target_vendor
            rendered = render_firewall_rules(ir, target_vendor)
            cmds = rendered["commands"]
            warns = list(ir.get("warnings", [])) + rendered["warnings"]

            try:
                revised, claude_warns = await _claude_review(
                    source_vendor=source_vendor,
                    target_vendor=target_vendor,
                    ir=ir,
                    commands=cmds,
                )
                cmds = revised
                warns.extend(claude_warns)
            except Exception as exc:
                log.warning("Claude review failed for fw migration %s: %s", migration_id, exc)
                warns.append(f"Revisão IA indisponível — usando comandos gerados automaticamente ({exc})")

            row.commands_preview = "\n".join(cmds)
            row.warnings = warns
            row.status = FirewallMigrationStatus.ready
            await db.commit()
            return {"ok": True, "migration_id": migration_id}

        except Exception as exc:
            log.exception("analyze_firewall_migration failed: %s", exc)
            row.status = FirewallMigrationStatus.failed
            row.error_message = str(exc)
            await db.commit()
            return {"error": str(exc)}


async def _fetch_rules_rest(device) -> str:
    """Fetch firewall rules from REST-based vendors and return as JSON string."""
    from app.connectors.factory import get_connector
    connector = get_connector(device)
    vendor = device.vendor.value

    data: dict = {}

    if vendor == "sonicwall":
        for endpoint, key in [
            ("/api/sonicos/address-objects/ipv4", "address_objects"),
            ("/api/sonicos/address-groups/ipv4",  "address_groups"),
            ("/api/sonicos/service-objects",       "service_objects"),
            ("/api/sonicos/service-groups",        "service_groups"),
            ("/api/sonicos/access-rules/ipv4",     "access_rules"),
            ("/api/sonicos/nat-policies/ipv4",     "nat_policies"),
        ]:
            try:
                resp = await connector._get(endpoint)
                if isinstance(resp, dict):
                    # Normalize — SonicWall wraps list in outer key
                    for k, v in resp.items():
                        if isinstance(v, list):
                            data[key] = v
                            break
                    else:
                        data[key] = []
                else:
                    data[key] = resp or []
            except Exception as exc:
                log.warning("SonicWall fetch %s failed: %s", endpoint, exc)
                data.setdefault(key, [])

    elif vendor == "sophos":
        for obj_type in ["IPHost", "IPHostGroup", "Services", "ServiceGroup", "FirewallRule", "NATRule", "StaticRoute"]:
            try:
                resp = await connector._get(f"/webconsole/APIController?reqxml=<Get><{obj_type}></{obj_type}></Get>")
                if isinstance(resp, dict):
                    data[obj_type] = resp.get(obj_type, resp.get("Response", {}).get(obj_type, []))
                    if isinstance(data[obj_type], dict):
                        data[obj_type] = [data[obj_type]]
            except Exception as exc:
                log.warning("Sophos fetch %s failed: %s", obj_type, exc)
                data.setdefault(obj_type, [])

    return json.dumps(data, ensure_ascii=False)


async def _async_apply(migration_id: str) -> dict:
    import app.models  # noqa: F401
    from app.database import AsyncSessionLocal
    from app.models.firewall_migration import FirewallMigration, FirewallMigrationStatus
    from app.models.device import Device
    from app.connectors.factory import get_ssh_connector, get_connector, CLI_VENDORS

    async with AsyncSessionLocal() as db:
        row = await db.get(FirewallMigration, UUID(migration_id))
        if not row:
            return {"error": "Migration not found"}

        try:
            if not row.commands_preview:
                raise ValueError("Nenhum preview de comandos — execute a análise primeiro")

            tgt_dev = await db.get(Device, row.target_device_id)
            if not tgt_dev:
                raise ValueError("Dispositivo de destino não encontrado")

            if tgt_dev.vendor not in CLI_VENDORS and row.target_vendor not in ("fortinet", "sonicwall", "sophos"):
                raise ValueError(f"Apply automático não suportado para vendor REST '{row.target_vendor}' — aplique manualmente")

            row.status = FirewallMigrationStatus.applying
            await db.commit()

            commands = [
                c for c in row.commands_preview.splitlines()
                if c.strip() and not c.strip().startswith("!")
            ]

            if tgt_dev.vendor.value in CLI_VENDORS:
                connector = get_ssh_connector(tgt_dev)
                result = await connector.execute_commands(commands)
                success = result.success
                output = result.output[:2000]
                error = result.error if not result.success else None
            else:
                # REST vendors — not auto-applicable in Phase 1
                success = False
                output = ""
                error = "Apply automático via REST não suportado nesta versão — aplique os comandos manualmente no dispositivo de destino"

            if success:
                row.status = FirewallMigrationStatus.completed
            else:
                row.status = FirewallMigrationStatus.failed
                row.error_message = error

            await db.commit()
            return {"ok": success, "output": output}

        except Exception as exc:
            log.exception("apply_firewall_migration failed: %s", exc)
            row.status = FirewallMigrationStatus.failed
            row.error_message = str(exc)
            await db.commit()
            return {"error": str(exc)}


async def _claude_review(
    source_vendor: str,
    target_vendor: str,
    ir: dict,
    commands: list[str],
) -> tuple[list[str], list[str]]:
    from anthropic import AsyncAnthropic
    from app.config import settings

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    ir_text = json.dumps(ir, ensure_ascii=False, indent=2)[:8000]
    commands_text = "\n".join(c for c in commands if c.strip())[:4000]

    user_content = (
        f"## Migração: {source_vendor} → {target_vendor}\n\n"
        f"## IR extraído pelo parser\n```json\n{ir_text}\n```\n\n"
        f"## Comandos gerados para o destino ({target_vendor})\n```\n{commands_text}\n```"
    )

    msg = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=_CLAUDE_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = msg.content[0].text.strip()

    if "```" in raw:
        m = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
        raw = m.group(1).strip() if m else raw.replace("```json", "").replace("```", "").strip()

    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        raw = raw[start:end]

    if not raw:
        return commands, ["Revisão IA retornou resposta vazia — comandos mantidos"]

    data = json.loads(raw)
    return data.get("commands_revised", commands), data.get("warnings", [])
