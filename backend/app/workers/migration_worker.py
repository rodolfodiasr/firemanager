"""Celery tasks for switch config migration: analyze (fetch + parse + Claude) and apply."""
import asyncio
import json
import logging
from uuid import UUID

from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)

_CLAUDE_SYSTEM = """Você é especialista em migração de configurações de switches de rede.
Recebe comandos CLI gerados automaticamente para um switch de destino.
Revise e retorne SOMENTE JSON válido, sem texto adicional:

{
  "commands_revised": ["cmd1", "cmd2", ...],
  "warnings": ["aviso 1", "aviso 2"]
}

Regras:
- Corrija sintaxe incorreta para o vendor alvo
- Adicione comandos faltantes obrigatórios (ex: no shutdown, write memory, end)
- Remova duplicatas ou comandos conflitantes
- Se não conseguir traduzir algo, liste em warnings
- Se os comandos estiverem corretos, retorne sem alteração"""

_SHOW_CONFIG_CMD = {
    "edgeswitch": "show running-config",
    "dell_n":     "show running-config",
    "cisco_ios":  "show running-config",
    "cisco_nxos": "show running-config",
    "hp_comware": "display current-configuration",
    "aruba":      "show running-config",
    "juniper":    "show configuration",
}


@celery_app.task(
    name="app.workers.migration_worker.analyze_config_migration",
    bind=True,
    soft_time_limit=300,
    time_limit=360,
)
def analyze_config_migration(self, migration_id: str) -> dict:
    return asyncio.get_event_loop().run_until_complete(_async_analyze(migration_id))


@celery_app.task(
    name="app.workers.migration_worker.apply_config_migration",
    bind=True,
    soft_time_limit=300,
    time_limit=360,
)
def apply_config_migration(self, migration_id: str) -> dict:
    return asyncio.get_event_loop().run_until_complete(_async_apply(migration_id))


async def _async_analyze(migration_id: str) -> dict:
    import app.models  # noqa: F401  ensure ORM models registered
    from app.database import AsyncSessionLocal
    from app.models.config_migration import ConfigMigration, MigrationStatus
    from app.models.device import Device
    from app.connectors.factory import get_ssh_connector
    from app.services.config_parser import parse_config
    from app.services.config_renderer import render_config

    async with AsyncSessionLocal() as db:
        row = await db.get(ConfigMigration, UUID(migration_id))
        if not row:
            return {"error": "Migration not found"}

        try:
            src_dev = await db.get(Device, row.source_device_id)
            if not src_dev:
                raise ValueError("Dispositivo de origem não encontrado")

            connector = get_ssh_connector(src_dev)
            show_cmd = _SHOW_CONFIG_CMD.get(src_dev.vendor.value, "show running-config")
            result = await connector.execute_show_commands([show_cmd])

            if not result.success:
                raise ValueError(f"Falha ao buscar config: {result.error}")

            source_config = result.output
            row.source_config_raw = source_config

            # Parse into normalized IR
            ir = parse_config(src_dev.vendor.value, source_config)
            row.migration_plan = ir

            # Build identity port mapping as initial placeholder
            placeholder: dict[str, str] = {
                iface["name"]: iface["name"]
                for iface in ir.get("interfaces", [])
            }
            row.port_mapping = placeholder

            # Determine target vendor
            tgt_dev = await db.get(Device, row.target_device_id)
            target_vendor = tgt_dev.vendor.value if tgt_dev else row.target_vendor

            # Render initial commands with identity mapping
            rendered = render_config(ir, target_vendor, placeholder)
            cmds = rendered["commands"]
            warns = list(ir.get("warnings", [])) + rendered["warnings"]

            # Claude review
            try:
                revised, claude_warns = await _claude_review(target_vendor, cmds)
                cmds = revised
                warns.extend(claude_warns)
            except Exception as exc:
                log.warning("Claude review failed for migration %s: %s", migration_id, exc)
                warns.append(f"Revisão IA indisponível — usando comandos gerados automaticamente ({exc})")

            row.commands_preview = "\n".join(cmds)
            row.warnings = warns
            row.status = MigrationStatus.ready
            await db.commit()
            return {"ok": True, "migration_id": migration_id}

        except Exception as exc:
            log.exception("analyze_config_migration failed: %s", exc)
            row.status = MigrationStatus.failed
            row.error_message = str(exc)
            await db.commit()
            return {"error": str(exc)}


async def _async_apply(migration_id: str) -> dict:
    import app.models  # noqa: F401
    from app.database import AsyncSessionLocal
    from app.models.config_migration import ConfigMigration, MigrationStatus
    from app.models.device import Device
    from app.connectors.factory import get_ssh_connector

    async with AsyncSessionLocal() as db:
        row = await db.get(ConfigMigration, UUID(migration_id))
        if not row:
            return {"error": "Migration not found"}

        try:
            if not row.commands_preview:
                raise ValueError("Nenhum preview de comandos — execute a análise primeiro")

            tgt_dev = await db.get(Device, row.target_device_id)
            if not tgt_dev:
                raise ValueError("Dispositivo de destino não encontrado")

            row.status = MigrationStatus.applying
            await db.commit()

            connector = get_ssh_connector(tgt_dev)
            # Filter out blank lines and comment-only lines
            commands = [
                c for c in row.commands_preview.splitlines()
                if c.strip() and not c.strip().startswith("!")
            ]

            result = await connector.execute_commands(commands)

            if result.success:
                row.status = MigrationStatus.completed
            else:
                row.status = MigrationStatus.failed
                row.error_message = result.error

            await db.commit()
            return {"ok": result.success, "output": result.output[:2000]}

        except Exception as exc:
            log.exception("apply_config_migration failed: %s", exc)
            row.status = MigrationStatus.failed
            row.error_message = str(exc)
            await db.commit()
            return {"error": str(exc)}


async def _claude_review(target_vendor: str, commands: list[str]) -> tuple[list[str], list[str]]:
    from anthropic import AsyncAnthropic
    from app.config import settings

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    commands_text = "\n".join(c for c in commands if c.strip())

    msg = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=_CLAUDE_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Vendor alvo: {target_vendor}\n\nComandos gerados:\n```\n{commands_text}\n```",
        }],
    )

    raw = msg.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) >= 2 else raw
        if raw.startswith("json"):
            raw = raw[4:]

    data = json.loads(raw)
    return data.get("commands_revised", commands), data.get("warnings", [])
