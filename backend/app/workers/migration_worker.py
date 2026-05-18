"""Celery tasks for switch config migration: analyze (fetch + parse + Claude) and apply."""
import asyncio
import json
import logging
import re
from uuid import UUID

from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)

_CLAUDE_REVIEW_SYSTEM = """Você é especialista em migração de configurações de switches de rede.

Receberá:
1. Config bruto do switch de ORIGEM (saída do show running-config ou equivalente)
2. IR (Intermediate Representation) extraído pelo parser automático — pode estar incompleto
3. Comandos CLI gerados automaticamente para o switch de DESTINO

Sua tarefa:
- Compare o config de origem com o IR e os comandos gerados
- Preencha VLANs, modos de porta, PVIDs e LAGs que o parser não conseguiu extrair
- Corrija sintaxe incorreta para o vendor alvo
- Adicione comandos obrigatórios ausentes (ex: undo shutdown para Comware; write memory para IOS/Dell)
- Remova duplicatas ou comandos conflitantes
- Para LAGs/port-channels: recrie manualmente com os membros corretos se conseguir identificá-los no config de origem
- Inclua hostname/sysname do switch de origem traduzido para a sintaxe do vendor alvo
- Se o switch de origem tiver IP de gerência (ex: em Vlan-interface ou interface vlan), inclua o
  comando equivalente no vendor alvo E adicione um warning: "IP de gerência migrado do switch de
  origem — revise e altere para o IP correto do switch de destino antes de aplicar"
- NÃO inclua configurações de SNMP, NTP, AAA, RADIUS, usuários locais ou serviços de gerência
- Se não conseguir traduzir algo, explique em warnings

Retorne SOMENTE JSON válido, sem texto adicional:
{
  "commands_revised": ["cmd1", "cmd2", ...],
  "warnings": ["aviso 1", "aviso 2"]
}

Se os comandos já estiverem completos e corretos, retorne-os sem alteração."""

_CLAUDE_GENERATE_SYSTEM = """Você é especialista em configuração de switches de rede.

Receberá a configuração completa de um switch de ORIGEM e o vendor do switch de DESTINO.

Sua tarefa:
- Analise completamente a configuração de origem
- Gere os comandos CLI completos e corretos para o switch de DESTINO
- Inclua: hostname/sysname, VLANs (com nomes), configuração de todas as portas, LAGs, IP de gerência
- Use a sintaxe NATIVA do vendor de destino:
  * HP Comware: sysname <nome>, vlan X / name / quit, interface GigabitEthernet1/0/X / port link-type / quit, interface Vlan-interface X / ip address / quit, save force
  * Cisco IOS: hostname, vlan X / name, interface GigabitEthernetX/X / switchport / exit, write memory
  * Dell N-Series: hostname, vlan X / name, interface TeX/X/X / switchport / exit, write memory
  * Aruba: hostname, vlan X / name, interface X / tagged/untagged vlan
- Para HP Comware: use quit (não exit), use port link-type (não switchport mode)
- Para IP de gerência: inclua o comando correto E adicione warning para revisão
- NÃO inclua: SNMP, NTP, AAA, RADIUS, usuários locais, serviços de gerência

Retorne SOMENTE JSON válido, sem texto adicional:
{
  "commands_revised": ["cmd1", "cmd2", ...],
  "warnings": ["aviso 1", "aviso 2"]
}"""

_SHOW_CONFIG_CMD = {
    "edgeswitch": "show running-config",
    "dell_n":     "show running-config",
    "cisco_ios":  "show running-config",
    "cisco_nxos": "show running-config",
    "hp_comware": "display current-configuration",
    "aruba":      "show running-config",
    "juniper":    "show configuration",
    "intelbras":  "show running-config",
}


@celery_app.task(
    name="app.workers.migration_worker.analyze_config_migration",
    bind=True,
    soft_time_limit=300,
    time_limit=360,
)
def analyze_config_migration(self, migration_id: str) -> dict:
    return asyncio.run(_async_analyze(migration_id))


@celery_app.task(
    name="app.workers.migration_worker.apply_config_migration",
    bind=True,
    soft_time_limit=300,
    time_limit=360,
)
def apply_config_migration(self, migration_id: str) -> dict:
    return asyncio.run(_async_apply(migration_id))


@celery_app.task(
    name="app.workers.migration_worker.regenerate_config_migration",
    bind=True,
    soft_time_limit=300,
    time_limit=360,
)
def regenerate_config_migration(self, migration_id: str) -> dict:
    return asyncio.run(_async_regenerate(migration_id))


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

            # Determine target vendor (needed for smart port mapping)
            tgt_dev = await db.get(Device, row.target_device_id)
            target_vendor = tgt_dev.vendor.value if tgt_dev else row.target_vendor

            # Build port mapping — smart conversion for known vendor pairs
            placeholder: dict[str, str] = _build_port_mapping(
                ir.get("interfaces", []),
                src_dev.vendor.value,
                target_vendor,
            )
            row.port_mapping = placeholder

            ai_level = row.ai_level

            if ai_level == 3:
                # Level 3: skip renderer, full Claude generation
                try:
                    cmds, warns = await _claude_generate_full(
                        source_vendor=src_dev.vendor.value,
                        source_config=source_config,
                        target_vendor=target_vendor,
                    )
                    warns = list(ir.get("warnings", [])) + warns
                except Exception as exc:
                    log.warning("Claude full generation failed for migration %s: %s", migration_id, exc)
                    # Fallback to Level 2
                    rendered = render_config(ir, target_vendor, placeholder)
                    cmds = rendered["commands"]
                    warns = list(ir.get("warnings", [])) + rendered["warnings"]
                    warns.append(f"Geração IA completa falhou — usando análise híbrida ({exc})")
            else:
                # Level 1 or 2: render first, then optionally Claude review
                rendered = render_config(ir, target_vendor, placeholder)
                cmds = rendered["commands"]
                warns = list(ir.get("warnings", [])) + rendered["warnings"]

                if ai_level >= 2:
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


async def _async_regenerate(migration_id: str) -> dict:
    """Re-render from stored IR + port_mapping, respecting ai_level."""
    import app.models  # noqa: F401
    from app.database import AsyncSessionLocal
    from app.models.config_migration import ConfigMigration, MigrationStatus
    from app.services.config_renderer import render_config

    async with AsyncSessionLocal() as db:
        row = await db.get(ConfigMigration, UUID(migration_id))
        if not row:
            return {"error": "Migration not found"}

        try:
            ir = row.migration_plan or {}
            port_mapping = row.port_mapping or {}
            target_vendor = row.target_vendor
            ai_level = row.ai_level

            if ai_level == 3:
                # Full Claude generation from stored source config
                if not row.source_config_raw:
                    raise ValueError("Config de origem não disponível — execute nova análise")
                try:
                    cmds, warns = await _claude_generate_full(
                        source_vendor=row.source_vendor,
                        source_config=row.source_config_raw,
                        target_vendor=target_vendor,
                    )
                    parser_warns = list(ir.get("warnings", []))
                    warns = parser_warns + warns
                except Exception as exc:
                    log.warning("Claude full generation failed during regenerate %s: %s", migration_id, exc)
                    rendered = render_config(ir, target_vendor, port_mapping)
                    cmds = rendered["commands"]
                    warns = list(ir.get("warnings", [])) + rendered["warnings"]
                    warns.append(f"Geração IA completa falhou — usando análise híbrida ({exc})")
            else:
                rendered = render_config(ir, target_vendor, port_mapping)
                cmds = rendered["commands"]
                warns = list(ir.get("warnings", [])) + rendered["warnings"]

                if ai_level >= 2 and row.source_config_raw:
                    try:
                        revised, claude_warns = await _claude_review(
                            source_vendor=row.source_vendor,
                            source_config=row.source_config_raw,
                            ir=ir,
                            target_vendor=target_vendor,
                            commands=cmds,
                        )
                        cmds = revised
                        warns.extend(claude_warns)
                    except Exception as exc:
                        log.warning("Claude review failed during regenerate %s: %s", migration_id, exc)
                        warns.append(f"Revisão IA indisponível — usando comandos do renderer ({exc})")

            row.commands_preview = "\n".join(cmds)
            row.warnings = warns
            row.status = MigrationStatus.ready
            await db.commit()
            return {"ok": True, "migration_id": migration_id}

        except Exception as exc:
            log.exception("regenerate_config_migration failed: %s", exc)
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


def _build_port_mapping(
    interfaces: list[dict],
    source_vendor: str,
    target_vendor: str,
) -> dict[str, str]:
    """Convert source port names to target vendor format where possible.

    EdgeSwitch uses 0/X and lag X.
    HP Comware uses GigabitEthernetX/Y/Z and Bridge-AggregationN.
    Cisco IOS uses GigabitEthernetX/X and Port-channelN.
    """
    mapping: dict[str, str] = {}
    for iface in interfaces:
        src = iface["name"]
        tgt = _convert_port_name(src, source_vendor, target_vendor)
        mapping[src] = tgt
    return mapping


def _convert_port_name(src: str, source_vendor: str, target_vendor: str) -> str:
    """Best-effort port name conversion between vendors."""
    s = src.strip().lower()

    # EdgeSwitch → HP Comware
    if source_vendor == "edgeswitch" and target_vendor == "hp_comware":
        m = re.match(r"^0/(\d+)$", s)
        if m:
            return f"GigabitEthernet1/0/{m.group(1)}"
        m = re.match(r"^lag\s*(\d+)$", s)
        if m:
            return f"Bridge-Aggregation{m.group(1)}"

    # EdgeSwitch → Cisco IOS / Dell N
    if source_vendor == "edgeswitch" and target_vendor in ("cisco_ios", "dell_n"):
        m = re.match(r"^0/(\d+)$", s)
        if m:
            return f"GigabitEthernet0/0/{m.group(1)}"
        m = re.match(r"^lag\s*(\d+)$", s)
        if m:
            return f"Port-channel{m.group(1)}"

    # Dell N → HP Comware
    if source_vendor == "dell_n" and target_vendor == "hp_comware":
        m = re.match(r"^te(\d+)/(\d+)/(\d+)$", s)
        if m:
            return f"GigabitEthernet{m.group(1)}/0/{m.group(3)}"
        m = re.match(r"^po(\d+)$", s)
        if m:
            return f"Bridge-Aggregation{m.group(1)}"

    return src  # fallback: keep source name


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
        system=_CLAUDE_REVIEW_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )

    return _parse_claude_json(msg.content[0].text.strip(), commands)


async def _claude_generate_full(
    source_vendor: str,
    source_config: str,
    target_vendor: str,
) -> tuple[list[str], list[str]]:
    """Level 3: ask Claude to generate commands from scratch without IR/renderer."""
    from anthropic import AsyncAnthropic
    from app.config import settings

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    source_preview = source_config[:8000]
    if len(source_config) > 8000:
        source_preview += f"\n... (truncado — {len(source_config) - 8000} chars restantes)"

    user_content = (
        f"## Config de origem ({source_vendor})\n```\n{source_preview}\n```\n\n"
        f"## Vendor de destino: {target_vendor}\n\n"
        f"Gere os comandos CLI completos para migrar esta configuração para o switch de destino."
    )

    msg = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=_CLAUDE_GENERATE_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )

    return _parse_claude_json(msg.content[0].text.strip(), [])


def _parse_claude_json(raw: str, fallback_commands: list[str]) -> tuple[list[str], list[str]]:
    """Parse Claude JSON response into (commands, warnings)."""
    # Strip markdown fences
    if "```" in raw:
        m = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
        raw = m.group(1).strip() if m else raw.replace("```json", "").replace("```", "").strip()

    # Find JSON object boundaries
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        raw = raw[start:end]

    if not raw:
        log.warning("Claude returned empty response")
        return fallback_commands, ["Revisão IA retornou resposta vazia — comandos gerados automaticamente mantidos"]

    data = json.loads(raw)
    return data.get("commands_revised", fallback_commands), data.get("warnings", [])
