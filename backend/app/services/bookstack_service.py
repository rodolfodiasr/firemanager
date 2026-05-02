"""BookStack service — context fetching and changelog writing."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.integration import IntegrationType
from app.models.operation import Operation, OperationStatus
from app.services.integration_service import resolve_integration


# ── Phase 1A: RAG context ─────────────────────────────────────────────────────

async def fetch_bookstack_context(
    db: AsyncSession,
    device: Device,
    query: str = "",
) -> str:
    """Return BookStack context for AI: direct device page + semantic search.

    Phase 1 (direct fetch) is always attempted if bookstack_page_id is set.
    Phase 4 (semantic search via pgvector) is layered on top when query is provided
    and openai_api_key is configured, searching the full BookStack knowledge base.
    Returns empty string on any failure. Never raises.
    """
    config = await resolve_integration(db, IntegrationType.bookstack, device.tenant_id)
    if not config:
        return ""

    parts: list[str] = []
    exclude_page_ids: set[int] = set()

    # 1. Direct page — highest relevance (human-maintained device documentation)
    if device.bookstack_page_id:
        try:
            from app.connectors.bookstack import connector_from_config
            connector = connector_from_config(config)
            page = await connector.get_page(device.bookstack_page_id)
            content = page.markdown or _strip_html(page.html)
            if content.strip():
                parts.append(f"## {page.name} (documentação do dispositivo)\n\n{content}")
                exclude_page_ids.add(device.bookstack_page_id)
        except Exception:
            pass

    # 2. Semantic search — knowledge base (policies, ISO flows, procedures, etc.)
    if query and device.tenant_id:
        from app.services.embedding_service import semantic_search
        semantic_ctx = await semantic_search(
            db, device.tenant_id, query, exclude_page_ids=exclude_page_ids
        )
        if semantic_ctx:
            parts.append(
                "## Base de conhecimento (busca semântica BookStack)\n\n" + semantic_ctx
            )

    return "\n\n---\n\n".join(parts)


# ── Phase 1B: Changelog append ────────────────────────────────────────────────

async def append_changelog(db: AsyncSession, device: Device, operation: Operation) -> None:
    """Append a change log entry to the FM-managed BookStack page.

    Creates the page automatically if bookstack_fm_page_id is not yet set.
    All failures are silenced — changelog is non-critical.
    """
    config = await resolve_integration(db, IntegrationType.bookstack, device.tenant_id)
    if not config:
        return

    try:
        from app.connectors.bookstack import connector_from_config
        connector = connector_from_config(config)
        entry = _build_changelog_entry(device, operation)

        if device.bookstack_fm_page_id:
            existing = await connector.get_page(device.bookstack_fm_page_id)
            existing_md = existing.markdown or _strip_html(existing.html)
            await connector.update_page(
                page_id=device.bookstack_fm_page_id,
                name=existing.name,
                markdown=existing_md.rstrip() + "\n\n" + entry,
            )
        else:
            book_id = config.get("book_id")
            if not book_id:
                return

            chapter_id = await _resolve_device_chapter_id(db, device)
            page_name = f"[FIREMANAGER] {device.name} — Histórico de Alterações"
            new_page = await connector.create_page(
                book_id=int(book_id),
                name=page_name,
                markdown=entry,
                chapter_id=chapter_id,
            )
            device.bookstack_fm_page_id = new_page.id
            await db.flush()

    except Exception:
        pass  # changelog failure must never break an operation


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _resolve_device_chapter_id(db: AsyncSession, device: Device) -> int | None:
    """Return the BookStack chapter_id linked to any group this device belongs to."""
    from sqlalchemy import select
    from app.models.device_group import DeviceGroup, DeviceGroupMember

    result = await db.execute(
        select(DeviceGroup)
        .join(DeviceGroupMember, DeviceGroupMember.group_id == DeviceGroup.id)
        .where(
            DeviceGroupMember.device_id == device.id,
            DeviceGroup.tenant_id == device.tenant_id,
            DeviceGroup.bookstack_chapter_id.isnot(None),
        )
        .limit(1)
    )
    group = result.scalar_one_or_none()
    return group.bookstack_chapter_id if group else None


def _build_changelog_entry(device: Device, operation: Operation) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    intent = (operation.intent or "operação").replace("_", " ")
    status_icon = "✅" if operation.status == OperationStatus.completed else "❌"

    lines = [
        f"### {status_icon} {now} — {intent}",
        "",
        f"**Dispositivo:** {device.name} ({device.vendor.value})",
        f"**Solicitação:** {operation.natural_language_input}",
    ]

    plan = operation.action_plan or {}

    rule = plan.get("rule_spec")
    if rule and rule.get("name"):
        lines.append(
            f"**Regra:** `{rule['name']}` | "
            f"{rule.get('src_address', '?')} → {rule.get('dst_address', '?')} "
            f"| {rule.get('service', '?')} | {rule.get('action', '?')}"
        )

    nat = plan.get("nat_spec")
    if nat and nat.get("name"):
        lines.append(
            f"**NAT:** `{nat['name']}` | "
            f"{nat.get('source', '?')} → {nat.get('translated_destination', '?')}"
        )

    route = plan.get("route_spec")
    if route and route.get("destination"):
        lines.append(
            f"**Rota:** {route.get('destination', '?')} via {route.get('gateway', '?')} "
            f"({route.get('interface', '?')})"
        )

    ssh_cmds = plan.get("ssh_commands")
    if ssh_cmds:
        lines.append("**Comandos SSH:**")
        for cmd in ssh_cmds:
            lines.append(f"- `{cmd}`")

    if operation.error_message:
        lines.append(f"**Erro:** {operation.error_message}")

    lines += ["", "---"]
    return "\n".join(lines)


# ── Phase 2: Documentation draft ─────────────────────────────────────────────

async def publish_doc_draft(db: AsyncSession, device: Device) -> str:
    """Generate an AI documentation draft and publish it to BookStack.

    Creates the page on first call; updates it on subsequent calls.
    Returns the BookStack page URL.
    Raises ValueError if BookStack is not configured or AI generation fails.
    """
    from sqlalchemy import select
    from app.agent.docs_generator import generate_device_doc
    from app.connectors.bookstack import connector_from_config
    from app.models.operation import Operation, OperationStatus as OpStatus

    config = await resolve_integration(db, IntegrationType.bookstack, device.tenant_id)
    if not config:
        raise ValueError("Integração BookStack não configurada para este tenant")

    book_id = config.get("book_id")
    if not book_id:
        raise ValueError("book_id não definido na integração BookStack")

    # Last 20 completed operations for this device
    result = await db.execute(
        select(Operation)
        .where(
            Operation.device_id == device.id,
            Operation.status == OpStatus.completed,
        )
        .order_by(Operation.created_at.desc())
        .limit(20)
    )
    recent_ops = list(result.scalars().all())

    bookstack_context = await fetch_bookstack_context(db, device)
    doc_markdown = await generate_device_doc(device, recent_ops, bookstack_context)

    if not doc_markdown:
        raise ValueError("Falha ao gerar documentação via IA")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    draft_notice = (
        "> ⚠️ **Rascunho gerado automaticamente pelo FireManager** — "
        f"Gerado em {now}. Revise, edite e remova este aviso quando a documentação estiver aprovada."
    )
    full_content = f"{draft_notice}\n\n{doc_markdown}"

    connector = connector_from_config(config)

    if device.bookstack_doc_page_id:
        existing = await connector.get_page(device.bookstack_doc_page_id)
        await connector.update_page(
            page_id=device.bookstack_doc_page_id,
            name=existing.name,
            markdown=full_content,
        )
        page_slug = existing.slug
    else:
        chapter_id = await _resolve_device_chapter_id(db, device)
        page_name = f"[FIREMANAGER DRAFT] {device.name} — Documentação"
        new_page = await connector.create_page(
            book_id=int(book_id),
            name=page_name,
            markdown=f"# {page_name}\n\n{full_content}",
            chapter_id=chapter_id,
        )
        device.bookstack_doc_page_id = new_page.id
        await db.flush()
        page_slug = new_page.slug

    base_url = config["base_url"].rstrip("/")
    return f"{base_url}/books/{book_id}/pages/{page_slug}"


# ── Phase 3: Periodic snapshot ────────────────────────────────────────────────

async def publish_device_snapshot(db: AsyncSession, device: Device) -> None:
    """Capture current device state and overwrite the BookStack snapshot page.

    Safe for any device — silently returns if BookStack is not configured.
    Designed to be called by the Celery beat task and the manual API endpoint.
    """
    config = await resolve_integration(db, IntegrationType.bookstack, device.tenant_id)
    if not config:
        return

    book_id = config.get("book_id")
    if not book_id:
        return

    from sqlalchemy import select
    from app.models.operation import Operation

    result = await db.execute(
        select(Operation)
        .where(Operation.device_id == device.id)
        .order_by(Operation.created_at.desc())
        .limit(5)
    )
    recent_ops = list(result.scalars().all())

    live_data = await _collect_live_data(device)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    page_name = f"[FIREMANAGER SNAPSHOT] {device.name} — Estado Atual"
    snapshot_md = _build_snapshot_md(device, live_data, recent_ops, now)

    try:
        from app.connectors.bookstack import connector_from_config
        connector = connector_from_config(config)

        if device.bookstack_snapshot_page_id:
            existing = await connector.get_page(device.bookstack_snapshot_page_id)
            await connector.update_page(
                page_id=device.bookstack_snapshot_page_id,
                name=existing.name,
                markdown=snapshot_md,
            )
        else:
            chapter_id = await _resolve_device_chapter_id(db, device)
            new_page = await connector.create_page(
                book_id=int(book_id),
                name=page_name,
                markdown=snapshot_md,
                chapter_id=chapter_id,
            )
            device.bookstack_snapshot_page_id = new_page.id
            await db.flush()

    except Exception:
        pass  # snapshot failure is non-critical


async def _collect_live_data(device: Device) -> dict:
    """Try to collect live structured data from REST API vendors. Never raises."""
    from app.connectors.factory import CLI_VENDORS, get_connector
    from app.models.device import DeviceStatus

    if device.status != DeviceStatus.online:
        return {"status": device.status.value}

    if device.vendor in CLI_VENDORS:
        return {"status": "online", "cli_vendor": True}

    try:
        connector = get_connector(device)
        rules = await connector.list_rules()
        nats = await connector.list_nat_policies()
        routes = await connector.list_route_policies()
        return {"status": "online", "rules": rules, "nats": nats, "routes": routes}
    except Exception:
        return {"status": "error"}


def _build_snapshot_md(device: Device, live_data: dict, recent_ops: list, timestamp: str) -> str:
    status = live_data.get("status", "unknown")
    icon = {"online": "✅", "offline": "❌", "error": "⚠️", "unknown": "❓"}.get(status, "❓")
    last_seen = (
        device.last_seen.strftime("%Y-%m-%d %H:%M UTC") if device.last_seen else "nunca"
    )

    lines = [
        f"> 🕐 Última atualização automática: **{timestamp}**",
        "",
        "## Status do dispositivo",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Status | {icon} {status} |",
        f"| Vendor | {device.vendor.value} |",
        f"| Categoria | {device.category.value} |",
        f"| Host | `{device.host}:{device.port}` |",
        f"| Firmware | {device.firmware_version or 'desconhecido'} |",
        f"| Último acesso | {last_seen} |",
        "",
        "## Configuração atual",
        "",
    ]

    if live_data.get("cli_vendor"):
        lines += [
            "_Vendor CLI — coleta estruturada não realizada no snapshot periódico._",
            "_Consulte o histórico de operações para ver as alterações realizadas via FireManager._",
        ]
    elif "rules" in live_data:
        rules = live_data["rules"]
        nats = live_data.get("nats", [])
        routes = live_data.get("routes", [])

        lines.append(f"### Regras de firewall ({len(rules)})")
        if rules:
            lines += [
                "",
                "| # | Nome | Origem | Destino | Serviço | Ação | Ativo |",
                "|---|---|---|---|---|---|---|",
            ]
            for i, r in enumerate(rules[:50], 1):
                enabled = "✅" if r.enabled else "—"
                lines.append(
                    f"| {i} | {r.name} | {r.src} | {r.dst} | {r.service} | {r.action} | {enabled} |"
                )
        else:
            lines.append("_Nenhuma regra configurada._")

        lines += ["", f"### Políticas NAT ({len(nats)})"]
        if nats:
            lines += [
                "",
                "| # | Nome | Entrada | Destino → Traduzido |",
                "|---|---|---|---|",
            ]
            for i, n in enumerate(nats[:30], 1):
                lines.append(
                    f"| {i} | {n.name} | {n.inbound} | {n.destination} → {n.translated_destination} |"
                )
        else:
            lines.append("_Nenhuma política NAT configurada._")

        lines += ["", f"### Rotas estáticas ({len(routes)})"]
        if routes:
            lines += [
                "",
                "| # | Destino | Gateway | Interface |",
                "|---|---|---|---|",
            ]
            for i, r in enumerate(routes[:30], 1):
                lines.append(
                    f"| {i} | {r.destination} | {r.gateway} | {r.interface} |"
                )
        else:
            lines.append("_Nenhuma rota estática configurada._")

    else:
        lines.append(
            "_Dados não disponíveis — dispositivo offline ou erro de coleta._"
        )

    lines += ["", "## Atividade recente (últimas 5 operações)", ""]
    if recent_ops:
        for op in recent_ops:
            op_icon = "✅" if op.status.value == "completed" else "❌"
            date = op.created_at.strftime("%Y-%m-%d") if op.created_at else "?"
            intent = (op.intent or "?").replace("_", " ")
            excerpt = op.natural_language_input[:100].replace("\n", " ")
            lines.append(f"- {op_icon} **{date}** — *{intent}*: {excerpt}")
    else:
        lines.append("_Nenhuma operação registrada._")

    return "\n".join(lines)


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()
