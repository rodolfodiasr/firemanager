"""Celery tasks for switch config migration: analyze (fetch + parse + Claude) and apply."""
import asyncio
import json
import logging
import re
from uuid import UUID

from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)

_CLAUDE_SYSTEM = """Você é especialista em migração de configurações de switches de rede.

Receberá:
1. Config bruto do switch de ORIGEM (saída do show running-config ou equivalente)
2. IR (Intermediate Representation) extraído pelo parser automático — pode estar incompleto
3. Comandos CLI gerados automaticamente para o switch de DESTINO

Sua tarefa:
- Compare o config de origem com o IR e os comandos gerados
- Preencha VLANs, modos de porta, PVIDs e LAGs que o parser não conseguiu extrair
- Corrija sintaxe incorreta para o vendor alvo
- Adicione comandos obrigatórios ausentes (ex: undo shutdown, return, save force para Comware; write memory para IOS/Dell)
- Remova duplicatas ou comandos conflitantes
- Para LAGs/port-channels: recrie manualmente com os membros corretos se conseguir identificá-los no config de origem
- Se não conseguir traduzir algo, explique em warnings

Retorne SOMENTE JSON válido, sem texto adicional:
{
  "commands_revised": ["cmd1", "cmd2", ...],
  "warnings": ["aviso 1", "aviso 2"]
}

Se os comandos já estiverem completos e corretos, retorne-os sem alteração."""

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

            # Claude review — passes full context so it can fill parser gaps
            try:
                revised, claude_warns = await _claude_review(
                    source_vendor=src_dev.vendor.value,
                    source_config=source_config,
                    ir=ir,
                    target_vendor=target_vendor,
                    commands=cmds,
                )
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


async def _claude_review(
    source_vendor: str,
    source_config: str,
    ir: dict,
    target_vendor: str,
    commands: list[str],
) -> tuple[list[str], list[str]]:
    from anthropic import AsyncAnthropic
    from app.config import settings

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    commands_text = "\n".join(c for c in commands if c.strip())
    ir_text = json.dumps(ir, ensure_ascii=False, indent=2)

    # Truncate source config to avoid exceeding context limits (keep first 6000 chars)
    source_preview = source_config[:6000]
    if len(source_config) > 6000:
        source_preview += f"\n... (truncado — {len(source_config) - 6000} chars restantes)"

    user_content = (
        f"## Config de origem ({source_vendor})\n```\n{source_preview}\n```\n\n"
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

    # Strip markdown fences in any position
    if "```" in raw:
        # Extract content between first ``` pair
        m = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
        raw = m.group(1).strip() if m else raw.replace("```json", "").replace("```", "").strip()

    # Find the JSON object boundaries in case Claude added preamble text
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        raw = raw[start:end]

    if not raw:
        log.warning("Claude review returned empty response")
        return commands, ["Revisão IA retornou resposta vazia — comandos gerados automaticamente mantidos"]

    data = json.loads(raw)
    return data.get("commands_revised", commands), data.get("warnings", [])
