"""BookStack service — context fetching and changelog writing."""
from __future__ import annotations

import re
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device, VendorEnum
from app.models.integration import IntegrationType
from app.models.operation import Operation, OperationStatus
from app.services.integration_service import resolve_integration

log = structlog.get_logger()


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
        import httpx
        from app.connectors.bookstack import connector_from_config
        connector = connector_from_config(config)
        entry = _build_changelog_entry(device, operation)

        if device.bookstack_fm_page_id:
            try:
                existing = await connector.get_page(device.bookstack_fm_page_id)
                existing_md = existing.markdown or _strip_html(existing.html)
                await connector.update_page(
                    page_id=device.bookstack_fm_page_id,
                    name=existing.name,
                    markdown=existing_md.rstrip() + "\n\n" + entry,
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    device.bookstack_fm_page_id = None
                    await db.flush()
                else:
                    raise

        if not device.bookstack_fm_page_id:
            book_id = config.get("book_id")
            if not book_id:
                return

            chapter_id = await _resolve_chapter_id(db, device, config)
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


async def _resolve_chapter_id(db: AsyncSession, device: Device, config: dict) -> int | None:
    """Resolve chapter_id with priority: device group > integration config > None."""
    chapter_id = await _resolve_device_chapter_id(db, device)
    if chapter_id is None and config.get("chapter_id"):
        try:
            chapter_id = int(config["chapter_id"])
        except (ValueError, TypeError):
            pass
    return chapter_id


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
        chapter_id = await _resolve_chapter_id(db, device, config)
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
        import httpx
        connector = connector_from_config(config)

        if device.bookstack_snapshot_page_id:
            try:
                existing = await connector.get_page(device.bookstack_snapshot_page_id)
                await connector.update_page(
                    page_id=device.bookstack_snapshot_page_id,
                    name=existing.name,
                    markdown=snapshot_md,
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    # Page was deleted externally — clear stale ID and recreate
                    device.bookstack_snapshot_page_id = None
                    await db.flush()
                else:
                    raise

        if not device.bookstack_snapshot_page_id:
            chapter_id = await _resolve_chapter_id(db, device, config)
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

    data: dict = {"status": "online"}

    log.info("snapshot_collect_start", device=device.name, vendor=str(device.vendor))

    # SSH before REST: SonicWall allows only one management session at a time.
    # Running SSH show commands before opening the REST session avoids the conflict.
    if device.vendor == VendorEnum.sonicwall:
        log.info("snapshot_ssh_phase_start", device=device.name)
        await _collect_ssh_resources(device, data)

    try:
        connector = get_connector(device)
        rules = await connector.list_rules()
        nats = await connector.list_nat_policies()
        routes = await connector.list_route_policies()
        data.update({"rules": rules, "nats": nats, "routes": routes})

        if hasattr(connector, "collect_extended_snapshot"):
            extended = await connector.collect_extended_snapshot()
            data.update(extended)

        return data
    except Exception:
        return data  # return SSH data even if REST fails


async def _collect_ssh_resources(device: Device, data: dict) -> None:
    """Collect SSH-only resources (security, content filter, app rules) for SonicWall."""
    from app.connectors.factory import get_ssh_connector
    from app.api.inspect import _parse_named_blocks, _SECURITY_COMMANDS
    from app.services.operation_service import _parse_security_status

    try:
        ssh = get_ssh_connector(device)

        sec_result = await ssh.execute_show_commands(_SECURITY_COMMANDS)
        if sec_result.success:
            data["security_services"] = _parse_security_status(_SECURITY_COMMANDS, sec_result.output)
            log.info("sw_snapshot_ssh_security", device=device.name, count=len(data["security_services"]))
        else:
            log.warning("sw_snapshot_ssh_security_failed", device=device.name, error=getattr(sec_result, "error", "?"))

        cf_result = await ssh.execute_show_commands_full(["show content-filter"])
        if cf_result.success:
            data["content_filter_ssh"] = _parse_named_blocks(
                cf_result.output,
                ["profile", "policy", "uri-list-object", "uri-list-group", "action", "reputation-object"],
            )
            log.info("sw_snapshot_ssh_content_filter", device=device.name, count=len(data["content_filter_ssh"]))
        else:
            log.warning("sw_snapshot_ssh_cf_failed", device=device.name, error=getattr(cf_result, "error", "?"))

        ar_result = await ssh.execute_show_commands(["show app-rules"])
        if ar_result.success:
            data["app_rules_ssh"] = _parse_named_blocks(
                ar_result.output, ["policy", "match-object", "action-object"]
            )
            log.info("sw_snapshot_ssh_app_rules", device=device.name, count=len(data["app_rules_ssh"]))
        else:
            log.warning("sw_snapshot_ssh_ar_failed", device=device.name, error=getattr(ar_result, "error", "?"))

    except Exception as exc:
        log.warning("sw_snapshot_ssh_exception", device=device.name, error=str(exc))


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

        # ── Address objects ────────────────────────────────────────────────────
        addr_objs = live_data.get("address_objects", [])
        if addr_objs:
            lines += ["", f"### Objetos de endereço customizados ({len(addr_objs)})", ""]
            lines += ["| Nome | Tipo | Valor | Zona |", "|---|---|---|---|"]
            for obj in addr_objs:
                lines.append(
                    f"| {obj['name']} | {obj['type']} | `{obj['value']}` | {obj['zone']} |"
                )

        addr_groups = live_data.get("address_groups", [])
        if addr_groups:
            lines += ["", f"### Grupos de endereço customizados ({len(addr_groups)})", ""]
            lines += ["| Nome | Membros |", "|---|---|"]
            for grp in addr_groups:
                members = ", ".join(grp["members"]) if grp["members"] else "—"
                lines.append(f"| {grp['name']} | {members} |")

        # ── Service objects ────────────────────────────────────────────────────
        svc_objs = live_data.get("service_objects", [])
        if svc_objs:
            lines += ["", f"### Objetos de serviço customizados ({len(svc_objs)})", ""]
            lines += ["| Nome | Protocolo | Porta(s) |", "|---|---|---|"]
            for obj in svc_objs:
                lines.append(f"| {obj['name']} | {obj['proto']} | {obj['port']} |")

        svc_groups = live_data.get("service_groups", [])
        if svc_groups:
            lines += ["", f"### Grupos de serviço customizados ({len(svc_groups)})", ""]
            lines += ["| Nome | Membros |", "|---|---|"]
            for grp in svc_groups:
                members = ", ".join(grp["members"]) if grp["members"] else "—"
                lines.append(f"| {grp['name']} | {members} |")

        # ── Content Filter ─────────────────────────────────────────────────────
        cf_ssh = live_data.get("content_filter_ssh")
        cf_rest = live_data.get("content_filter", [])
        if cf_ssh is not None:
            if cf_ssh:
                lines += ["", f"### Content Filter ({len(cf_ssh)} itens)", ""]
                lines += ["| Tipo | Nome | Detalhes |", "|---|---|---|"]
                for item in cf_ssh:
                    details = (item.get("details", "") or "").replace("\n", " ").strip()
                    details_short = details[:120] + "…" if len(details) > 120 else details
                    lines.append(f"| {item.get('type', '')} | {item['name']} | {details_short} |")
            else:
                lines += ["", "### Content Filter", "", "_Nenhuma política configurada._"]
        elif cf_rest:
            lines += ["", f"### Regras de Content Filter ({len(cf_rest)})", ""]
            lines += ["| Nome | Status | Categorias bloqueadas |", "|---|---|---|"]
            for p in cf_rest:
                status = "✅ Ativo" if p["enabled"] else "❌ Inativo"
                cats = ", ".join(p["blocked_categories"]) if p["blocked_categories"] else "—"
                lines.append(f"| {p['name']} | {status} | {cats} |")

        # ── App Rules ─────────────────────────────────────────────────────────
        ar_ssh = live_data.get("app_rules_ssh")
        ar_rest = live_data.get("app_rules", [])
        if ar_ssh is not None:
            if ar_ssh:
                lines += ["", f"### App Rules ({len(ar_ssh)} itens)", ""]
                lines += ["| Tipo | Nome | Detalhes |", "|---|---|---|"]
                for item in ar_ssh:
                    details = (item.get("details", "") or "").replace("\n", " ").strip()
                    details_short = details[:120] + "…" if len(details) > 120 else details
                    lines.append(f"| {item.get('type', '')} | {item['name']} | {details_short} |")
            else:
                lines += ["", "### App Rules", "", "_Nenhuma regra configurada._"]
        elif ar_rest:
            lines += ["", f"### App Rules ({len(ar_rest)})", ""]
            lines += ["| Nome | Aplicação | Ação | Status |", "|---|---|---|---|"]
            for ar in ar_rest:
                status_icon = "✅" if ar["enabled"] else "❌"
                lines.append(
                    f"| {ar['name']} | {ar['application']} | {ar['action']} | {status_icon} |"
                )

        # ── Security settings ──────────────────────────────────────────────────
        sec_ssh = live_data.get("security_services")
        sec_rest = live_data.get("security_settings", {})
        if sec_ssh is not None:
            if sec_ssh:
                lines += ["", f"### Serviços de segurança ({len(sec_ssh)})", ""]
                lines += ["| Serviço | Status |", "|---|---|"]
                for svc in sec_ssh:
                    enabled = svc.get("enabled")
                    icon = "✅ Ativo" if enabled is True else ("❌ Inativo" if enabled is False else "— Desconhecido")
                    lines.append(f"| {svc['service']} | {icon} |")
            else:
                lines += ["", "### Serviços de segurança", "", "_Nenhum serviço de segurança detectado._"]
        elif sec_rest:
            lines += ["", "### Configurações de segurança", ""]
            lines += [
                "| Serviço | Status | Inspeção Entrada | Inspeção Saída |",
                "|---|---|---|---|",
            ]
            for key, label in [
                ("gateway_av", "Gateway Antivírus"),
                ("anti_spyware", "Anti-Spyware"),
                ("ips", "Intrusion Prevention (IPS)"),
            ]:
                if key in sec_rest:
                    s = sec_rest[key]
                    enabled = "✅ Ativo" if s.get("enabled") else "❌ Inativo"
                    inbound = "✅" if s.get("inbound") else "—"
                    outbound = "✅" if s.get("outbound") else "—"
                    lines.append(f"| {label} | {enabled} | {inbound} | {outbound} |")

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
