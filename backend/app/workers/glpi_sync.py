"""Celery task: poll GLPI for open tickets and analyse with Claude AI.

For each active GlpiIntegration (per tenant):
  1. Fetch open tickets within lookback_hours matching priority/type filters
  2. Skip tickets already tracked in glpi_ticket_analyses
  3. Detect recurrence by searching similar closed tickets
  4. Correlate ticket to FireManager devices (IP/hostname extraction)
  5. Collect enrichment data from Zabbix/Wazuh/device SSH (if configured)
  6. Call Claude to produce structured diagnostic analysis (if auto_analysis_enabled)
  7. Post the analysis as a followup note in GLPI
  8. Persist the result in glpi_ticket_analyses

Design decisions:
  - Per-ticket isolation: one ticket failure does not block the rest
  - Idempotency: unique constraint (tenant_id, glpi_ticket_id) prevents duplicates
  - Recurrence threshold: >= 2 similar solved tickets marks a ticket as recurrent
  - Analysis mode: controlled per-integration via auto_analysis_enabled flag
  - Enrichment: Zabbix/Wazuh/device logs collected only when explicitly enabled
  - Manual queue: tickets without device correlation go to pending_manual when configured
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)

_RECURRENCE_THRESHOLD = 2    # similar solved tickets needed to flag as recurrent
_MAX_CONTENT_CHARS    = 4000  # truncate ticket content sent to Claude
_MAX_ENRICHMENT_CHARS = 2000  # max chars per enrichment source

_SYSTEM_PROMPT = """Você é um especialista em TI integrado ao FireManager. Sua análise será lida por analistas de helpdesk — seja direto, prático e escaneável.

Responda SOMENTE com JSON válido, sem texto adicional:

{
  "diagnostico": "O que está acontecendo em até 2 frases. Direto ao ponto.",
  "acoes_imediatas": "O que fazer AGORA para estabilizar. Máximo 3 passos numerados.",
  "plano_remediacao": "Resolução definitiva para não voltar. Máximo 4 passos numerados, priorizados.",
  "causa_raiz": "Causa raiz mais provável em 1 frase.",
  "prevencao": "Uma medida preventiva objetiva.",
  "confianca": 0.85,
  "is_security_incident": false,
  "is_recurrent": false,
  "kb_status": "sem_documentacao",
  "kb_docs": []
}

Regras:
- diagnostico: máximo 2 frases, sem jargão desnecessário
- acoes_imediatas: apenas o essencial para estabilizar agora, numere os passos
- plano_remediacao: resolução definitiva de médio prazo, numere e priorize os passos
- causa_raiz: 1 frase objetiva
- confianca: 0.0 a 1.0 — reduza se os dados forem insuficientes
- is_security_incident: true se envolver ataque, vazamento, acesso não autorizado ou comprometimento
- is_recurrent: true se o problema parece estrutural ou já ocorreu antes
- Se dados de monitoramento (Zabbix/Wazuh/logs) estiverem disponíveis, use-os para enriquecer a análise
- Se as informações forem insuficientes, diga isso no diagnóstico e sugira o que coletar
- kb_status: avalie a base de conhecimento fornecida e classifique:
    "documentado" — o problema e solução já estão bem documentados na KB
    "parcialmente_documentado" — existe documentação mas está incompleta ou desatualizada
    "sem_documentacao" — não há documentação para este tipo de problema
    "nao_verificado" — não foi possível verificar (KB não disponível)
- kb_docs: lista de títulos dos documentos da KB relevantes encontrados (vazia se nenhum)"""


@celery_app.task(
    name="app.workers.glpi_sync.run_glpi_sync",
    bind=True,
    soft_time_limit=1800,   # 30 min soft limit
    time_limit=1900,
)
def run_glpi_sync(self: object) -> dict:
    from app.database import engine
    engine.dispose()
    return asyncio.run(_async_glpi_sync())


async def _async_glpi_sync() -> dict:
    import app.models  # ensure all ORM models registered
    from app.database import AsyncSessionLocal
    from app.models.glpi_integration import GlpiIntegration
    from sqlalchemy import select

    summary = {
        "integrations":     0,
        "tickets_analysed": 0,
        "tickets_queued":   0,   # pending_manual
        "tickets_skipped":  0,
        "errors":           0,
    }

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GlpiIntegration).where(GlpiIntegration.is_active == True)
        )
        integrations = list(result.scalars().all())

    log.info("glpi_sync_start integrations=%d", len(integrations))

    for integration in integrations:
        try:
            stats = await _sync_integration(integration)
            summary["integrations"]     += 1
            summary["tickets_analysed"] += stats["analysed"]
            summary["tickets_queued"]   += stats["queued"]
            summary["tickets_skipped"]  += stats["skipped"]
            summary["errors"]           += stats["errors"]
        except Exception as exc:
            summary["errors"] += 1
            log.error("glpi_sync_integration_failed tenant=%s error=%s", integration.tenant_id, exc)

    log.info(
        "glpi_sync_done integrations=%d analysed=%d queued=%d skipped=%d errors=%d",
        summary["integrations"], summary["tickets_analysed"], summary["tickets_queued"],
        summary["tickets_skipped"], summary["errors"],
    )
    return summary


async def _sync_integration(integration) -> dict:
    from app.services.glpi_service import GlpiClient
    from app.utils.crypto import decrypt_credentials

    stats = {"analysed": 0, "queued": 0, "skipped": 0, "errors": 0}

    trigger_types  = integration.trigger_types or []
    ticket_types   = [t for t in trigger_types if t in (1, 2)] or None
    fetch_problems = 3 in trigger_types
    fetch_changes  = 4 in trigger_types

    creds    = decrypt_credentials(integration.encrypted_password)
    password = creds.get("password", "")

    try:
        async with GlpiClient(
            glpi_url=integration.glpi_url,
            app_token=integration.app_token,
            username=integration.username,
            password=password,
            verify_ssl=integration.verify_ssl,
        ) as client:
            items: list[tuple[dict, str]] = []

            if ticket_types or not trigger_types:
                tickets = await client.get_open_tickets(
                    min_priority=integration.min_priority,
                    trigger_types=ticket_types,
                    trigger_categories=integration.trigger_categories or None,
                    lookback_hours=integration.lookback_hours,
                )
                items += [(t, "Ticket") for t in tickets]
                log.info("glpi_tickets_fetched tenant=%s count=%d", integration.tenant_id, len(tickets))

            if fetch_problems:
                problems = await client.get_open_problems(lookback_hours=integration.lookback_hours)
                items += [(p, "Problem") for p in problems]
                log.info("glpi_problems_fetched tenant=%s count=%d", integration.tenant_id, len(problems))

            if fetch_changes:
                changes = await client.get_open_changes(lookback_hours=integration.lookback_hours)
                items += [(c, "Change") for c in changes]
                log.info("glpi_changes_fetched tenant=%s count=%d", integration.tenant_id, len(changes))

            log.info("glpi_items_total tenant=%s count=%d", integration.tenant_id, len(items))

            for item_data, itemtype in items:
                try:
                    result = await _process_ticket(integration, item_data, client, itemtype=itemtype)
                    if result == "analysed":
                        stats["analysed"] += 1
                    elif result == "queued":
                        stats["queued"] += 1
                    else:
                        stats["skipped"] += 1
                except Exception as exc:
                    stats["errors"] += 1
                    item_id = item_data.get("2", "?")
                    log.warning("item_process_failed item=%s type=%s error=%s", item_id, itemtype, exc)
    except Exception as exc:
        log.error("glpi_client_failed url=%s error=%s", integration.glpi_url, exc)
        stats["errors"] += 1

    return stats


def _is_glpi_item_closed(status: int, itemtype: str) -> bool:
    """Return True if the GLPI status value indicates the item is solved or closed."""
    if itemtype == "Ticket":
        return status >= 5   # Solved(5) or Closed(6)
    return status >= 6       # Closed — Problems/Changes: statuses 1-5 are open


async def _process_ticket(integration, ticket_data: dict, client, itemtype: str = "Ticket") -> str:
    """Analyse a single ticket/problem/change. Returns 'analysed', 'queued', or 'skipped'."""
    from app.database import AsyncSessionLocal
    from app.models.glpi_ticket_analysis import GlpiTicketAnalysis, GlpiAnalysisStatus
    from sqlalchemy import select

    glpi_ticket_id = int(ticket_data.get("2", 0))
    if not glpi_ticket_id:
        return "skipped"

    # Part A: skip if item status is already solved/closed (race-condition guard)
    raw_status = ticket_data.get("12")
    if raw_status is not None:
        try:
            if _is_glpi_item_closed(int(raw_status), itemtype):
                log.debug("item_already_closed ticket=%d type=%s status=%s", glpi_ticket_id, itemtype, raw_status)
                return "skipped"
        except (ValueError, TypeError):
            pass

    title   = str(ticket_data.get("1", ""))
    content = GlpiClient_strip_html(ticket_data.get("21", ""))

    async with AsyncSessionLocal() as db:
        # Idempotency — skip if already tracked
        existing = await db.execute(
            select(GlpiTicketAnalysis.id).where(
                GlpiTicketAnalysis.tenant_id      == integration.tenant_id,
                GlpiTicketAnalysis.glpi_ticket_id == glpi_ticket_id,
            )
        )
        if existing.scalar():
            return "skipped"

        # Recurrence detection via similar closed tickets
        similar          = await client.get_similar_tickets(title, limit=10)
        is_recurrent     = len(similar) >= _RECURRENCE_THRESHOLD
        recurrence_count = len(similar)
        related_ids      = [int(t.get("2", 0)) for t in similar if t.get("2")]

        # ── Device correlation ────────────────────────────────────────────────
        correlated_device_ids: list = []
        if integration.auto_correlate_devices:
            correlated_device_ids = await _correlate_devices(
                db, integration.tenant_id, title, content
            )

        # ── Decide analysis mode ──────────────────────────────────────────────
        # Tickets go to manual queue when:
        #   - auto_analysis_enabled is False, OR
        #   - unmatched_to_manual_queue is True AND no device was correlated
        #     (unless force overrides apply)
        needs_force = (
            (integration.force_analysis_on_security and _looks_like_security(title, content))
            or (integration.force_analysis_on_recurrent and is_recurrent)
        )

        go_to_manual_queue = (
            not integration.auto_analysis_enabled
            or (
                integration.unmatched_to_manual_queue
                and not correlated_device_ids
                and not needs_force
            )
        )

        initial_status = GlpiAnalysisStatus.pending_manual if go_to_manual_queue else GlpiAnalysisStatus.analyzing

        analysis = GlpiTicketAnalysis(
            tenant_id            = integration.tenant_id,
            glpi_integration_id  = integration.id,
            glpi_ticket_id       = glpi_ticket_id,
            glpi_itemtype        = itemtype,
            glpi_ticket_title    = title[:500],
            glpi_ticket_content  = content[:_MAX_CONTENT_CHARS],
            status               = initial_status,
            is_recurrent         = is_recurrent,
            recurrence_count     = recurrence_count,
            related_ticket_ids   = related_ids or None,
        )
        db.add(analysis)
        await db.flush()
        await db.refresh(analysis)
        analysis_id = analysis.id
        await db.commit()

    if go_to_manual_queue:
        log.info(
            "ticket_queued_manual ticket=%d tenant=%s reason=%s",
            glpi_ticket_id,
            integration.tenant_id,
            "auto_disabled" if not integration.auto_analysis_enabled else "no_device_match",
        )
        return "queued"

    # ── Collect enrichment data ───────────────────────────────────────────────
    enrichment: dict[str, str] = {}

    if correlated_device_ids:
        enrichment = await _collect_enrichment(
            integration, correlated_device_ids
        )

    # ── RAG: knowledge base docs ──────────────────────────────────────────────
    knowledge_ctx = ""
    try:
        from app.services.knowledge_service import semantic_search_documents
        async with AsyncSessionLocal() as rag_db:
            knowledge_ctx = await semantic_search_documents(
                rag_db, integration.tenant_id,
                f"{title} {content[:300]}", top_k=3, module="glpi",
            )
    except Exception:
        pass

    # ── Call Claude ───────────────────────────────────────────────────────────
    try:
        ai_result = await _call_claude(title, content, is_recurrent, recurrence_count, enrichment, knowledge_ctx)
    except Exception as exc:
        async with AsyncSessionLocal() as db:
            rec = await db.get(GlpiTicketAnalysis, analysis_id)
            if rec:
                rec.status        = GlpiAnalysisStatus.failed
                rec.error_message = str(exc)[:1000]
                await db.commit()
        log.warning("claude_analysis_failed ticket=%d error=%s", glpi_ticket_id, exc)
        return "skipped"

    # ── Post followup to GLPI ─────────────────────────────────────────────────
    followup_id = None
    try:
        followup_text = _build_followup(
            ai_result, is_recurrent, recurrence_count,
            related_ids=related_ids, enrichment_sources=list(enrichment.keys()),
        )
        followup_id = await client.add_followup(glpi_ticket_id, followup_text, itemtype=itemtype)
    except Exception as exc:
        log.warning("glpi_followup_failed ticket=%d error=%s", glpi_ticket_id, exc)

    # ── Persist completed analysis ────────────────────────────────────────────
    kb_status = ai_result.get("kb_status") or "nao_verificado"
    kb_docs   = ai_result.get("kb_docs") or []

    async with AsyncSessionLocal() as db:
        rec = await db.get(GlpiTicketAnalysis, analysis_id)
        if rec:
            rec.status               = GlpiAnalysisStatus.completed
            rec.diagnostico          = ai_result.get("diagnostico")
            rec.acoes_imediatas      = ai_result.get("acoes_imediatas")
            rec.plano_remediacao     = ai_result.get("plano_remediacao")
            rec.causa_raiz           = ai_result.get("causa_raiz")
            rec.prevencao            = ai_result.get("prevencao")
            rec.confianca            = float(ai_result.get("confianca", 0.0))
            rec.is_security_incident = bool(ai_result.get("is_security_incident", False))
            rec.is_recurrent         = is_recurrent or bool(ai_result.get("is_recurrent", False))
            rec.glpi_followup_id     = followup_id
            rec.kb_status            = kb_status
            rec.kb_docs              = kb_docs if isinstance(kb_docs, list) else []
            await db.commit()

    # ── Criar RemediationPlan a partir do plano_remediacao ────────────────────
    if ai_result.get("plano_remediacao") and correlated_device_ids:
        try:
            from app.services.remediation_service import generate_plan_from_context
            from app.models.device import Device
            from sqlalchemy import select as sa_select
            async with AsyncSessionLocal() as rdb:
                dev_result = await rdb.execute(
                    sa_select(Device).where(Device.id == correlated_device_ids[0])
                )
                dev = dev_result.scalar_one_or_none()
                device_name = dev.name if dev else None
                await generate_plan_from_context(
                    db=rdb,
                    tenant_id=integration.tenant_id,
                    request=(
                        f"[GLPI #{glpi_ticket_id}] {title}\n\n"
                        f"Plano de remediação:\n{ai_result['plano_remediacao']}"
                    ),
                    origin_type="glpi_ticket",
                    origin_ref=str(glpi_ticket_id),
                    device_name=device_name,
                )
                await rdb.commit()
        except Exception as exc:
            log.warning("glpi_remediation_plan_failed ticket=%d error=%s", glpi_ticket_id, exc)

    # ── KR (Knowledge Registration) loop ─────────────────────────────────────
    if integration.auto_create_kr and kb_status in ("sem_documentacao", "parcialmente_documentado"):
        try:
            await _maybe_open_kr(integration, analysis_id, client)
        except Exception as exc:
            log.warning("kr_loop_failed ticket=%d error=%s", glpi_ticket_id, exc)

    log.info(
        "ticket_analysed ticket=%d security=%s recurrent=%s confidence=%.2f enriched=%s kb_status=%s",
        glpi_ticket_id,
        ai_result.get("is_security_incident"),
        rec.is_recurrent if rec else is_recurrent,
        float(ai_result.get("confianca", 0.0)),
        list(enrichment.keys()),
        kb_status,
    )
    return "analysed"


# ── Device correlation ────────────────────────────────────────────────────────

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


async def _correlate_devices(db, tenant_id, title: str, content: str) -> list:
    """Extract IPs and hostnames from ticket text and match to FireManager devices."""
    from app.models.device import Device
    from sqlalchemy import select, or_

    text = f"{title} {content}".lower()
    ips  = set(_IP_RE.findall(f"{title} {content}"))

    # Load tenant devices once
    result  = await db.execute(select(Device).where(Device.tenant_id == tenant_id))
    devices = list(result.scalars().all())

    matched: list = []
    for device in devices:
        # IP match (exact)
        if device.host and device.host in ips:
            matched.append(str(device.id))
            continue
        # Hostname match (device name appears in ticket text, case-insensitive)
        if device.name and device.name.lower() in text:
            matched.append(str(device.id))

    return matched


def _looks_like_security(title: str, content: str) -> bool:
    """Quick heuristic: does this ticket look like a security incident?"""
    keywords = (
        "ataque", "attack", "breach", "vazamento", "intrusion", "malware",
        "ransomware", "acesso não autorizado", "unauthorized", "comprometimento",
        "exploit", "vulnerabilidade", "brute force", "ddos",
    )
    text = f"{title} {content}".lower()
    return any(k in text for k in keywords)


# ── Enrichment data collection ────────────────────────────────────────────────

async def _collect_enrichment(integration, device_ids: list) -> dict[str, str]:
    """Collect Zabbix, Wazuh, and/or device SSH logs for correlated devices."""
    enrichment: dict[str, str] = {}

    if integration.enrich_zabbix:
        try:
            data = await _fetch_zabbix_data(integration.tenant_id, device_ids)
            if data:
                enrichment["zabbix"] = data
        except Exception as exc:
            log.warning("enrichment_zabbix_failed tenant=%s error=%s", integration.tenant_id, exc)

    if integration.enrich_wazuh:
        try:
            data = await _fetch_wazuh_data(integration.tenant_id, device_ids)
            if data:
                enrichment["wazuh"] = data
        except Exception as exc:
            log.warning("enrichment_wazuh_failed tenant=%s error=%s", integration.tenant_id, exc)

    if integration.enrich_device_logs:
        try:
            data = await _fetch_device_logs(
                integration.tenant_id, device_ids,
                timeout=integration.device_logs_timeout_seconds,
            )
            if data:
                enrichment["device_logs"] = data
        except Exception as exc:
            log.warning("enrichment_device_logs_failed tenant=%s error=%s", integration.tenant_id, exc)

    return enrichment


async def _fetch_zabbix_data(tenant_id, device_ids: list) -> str | None:
    """Fetch recent triggers and metrics from Zabbix for the correlated devices."""
    from app.database import AsyncSessionLocal
    from app.models.device import Device
    from app.services import zabbix_service
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result  = await db.execute(select(Device).where(Device.id.in_(device_ids)))
        devices = list(result.scalars().all())

    if not devices:
        return None

    parts: list[str] = []
    for device in devices:
        try:
            host_id = device.zabbix_host_name or device.host
            summary = await zabbix_service.get_host_recent_summary(
                tenant_id=tenant_id,
                host_identifier=host_id,
                hours=24,
            )
            if summary:
                parts.append(f"[{device.name} / {device.host}]\n{summary}")
        except Exception as exc:
            log.debug("zabbix_host_failed device=%s error=%s", device.id, exc)

    return "\n\n".join(parts)[:_MAX_ENRICHMENT_CHARS] if parts else None


async def _fetch_wazuh_data(tenant_id, device_ids: list) -> str | None:
    """Fetch recent security events from Wazuh for the correlated devices."""
    from app.database import AsyncSessionLocal
    from app.models.device import Device
    from app.services import wazuh_service
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result  = await db.execute(select(Device).where(Device.id.in_(device_ids)))
        devices = list(result.scalars().all())

    if not devices:
        return None

    parts: list[str] = []
    for device in devices:
        try:
            agent_id = device.wazuh_agent_name or device.host
            summary  = await wazuh_service.get_agent_recent_alerts(
                tenant_id=tenant_id,
                agent_identifier=agent_id,
                hours=24,
            )
            if summary:
                parts.append(f"[{device.name} / {device.host}]\n{summary}")
        except Exception as exc:
            log.debug("wazuh_agent_failed device=%s error=%s", device.id, exc)

    return "\n\n".join(parts)[:_MAX_ENRICHMENT_CHARS] if parts else None


async def _fetch_device_logs(tenant_id, device_ids: list, timeout: int = 30) -> str | None:
    """Fetch recent logs directly from devices via SSH/REST connectors."""
    from app.database import AsyncSessionLocal
    from app.models.device import Device
    from app.connectors.factory import CLI_VENDORS, get_connector, get_ssh_connector
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result  = await db.execute(select(Device).where(Device.id.in_(device_ids)))
        devices = list(result.scalars().all())

    if not devices:
        return None

    parts: list[str] = []
    for device in devices:
        try:
            logs = await asyncio.wait_for(
                _get_device_log_snippet(device),
                timeout=timeout,
            )
            if logs:
                parts.append(f"[{device.name} / {device.host}]\n{logs}")
        except asyncio.TimeoutError:
            log.warning("device_logs_timeout device=%s timeout=%ds", device.id, timeout)
        except Exception as exc:
            log.debug("device_logs_failed device=%s error=%s", device.id, exc)

    return "\n\n".join(parts)[:_MAX_ENRICHMENT_CHARS] if parts else None


async def _get_device_log_snippet(device) -> str | None:
    """Run vendor-appropriate log commands on a single device."""
    from app.connectors.factory import CLI_VENDORS, get_ssh_connector
    from app.models.device import VendorEnum

    # Only attempt on SSH-capable devices
    if device.vendor not in CLI_VENDORS:
        return None

    connector = get_ssh_connector(device)
    # Generic "show log" command — each vendor connector maps this appropriately
    result = await asyncio.to_thread(connector.execute_commands, ["show log"])
    if result and result.get("output"):
        output = str(result["output"])
        # Return last 50 lines at most
        lines = output.strip().splitlines()
        return "\n".join(lines[-50:])
    return None


# ── Claude call ───────────────────────────────────────────────────────────────

async def _call_claude(
    title: str,
    content: str,
    is_recurrent: bool,
    recurrence_count: int,
    enrichment: dict[str, str] | None = None,
    knowledge_ctx: str = "",
) -> dict:
    from anthropic import AsyncAnthropic
    from app.config import settings

    recurrence_note = (
        f"\n\nNota: Este ticket parece ser recorrente — foram encontrados {recurrence_count} "
        "tickets similares resolvidos anteriormente. Considere isso na análise."
        if is_recurrent else ""
    )

    enrichment_block = ""
    if enrichment:
        sections: list[str] = []
        label_map = {
            "zabbix":      "DADOS ZABBIX (últimas 24h — métricas e triggers)",
            "wazuh":       "DADOS WAZUH (últimas 24h — alertas de segurança)",
            "device_logs": "LOGS DO DISPOSITIVO (via SSH)",
        }
        for key, data in enrichment.items():
            label = label_map.get(key, key.upper())
            sections.append(f"\n\n--- {label} ---\n{data}")
        enrichment_block = "".join(sections)

    knowledge_block = (
        f"\n\n--- BASE DE CONHECIMENTO (documentação técnica relevante) ---\n{knowledge_ctx}"
        if knowledge_ctx else ""
    )

    user_prompt = (
        f"Título do ticket: {title}\n\n"
        f"Descrição:\n{content[:_MAX_CONTENT_CHARS]}"
        f"{recurrence_note}"
        f"{knowledge_block}"
        f"{enrichment_block}"
    )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg    = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = msg.content[0].text if msg.content else "{}"
    return _parse_json(raw)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end   = raw.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass
    return {}


def _steps_to_html(text: str) -> str:
    import re
    items = re.split(r"\n?\s*\d+\.\s+", text.strip())
    items = [i.strip() for i in items if i.strip()]
    if not items:
        return text
    return "<ol>" + "".join(f"<li>{i}</li>" for i in items) + "</ol>"


def _build_followup(
    ai_result: dict,
    is_recurrent: bool,
    recurrence_count: int,
    related_ids: list | None = None,
    enrichment_sources: list[str] | None = None,
) -> str:
    confianca = float(ai_result.get("confianca", 0.0))
    pct       = round(confianca * 100)
    security  = ai_result.get("is_security_incident", False)

    parts: list[str] = []

    # ── Header ────────────────────────────────────────────────────────────────
    badges: list[str] = []
    if security:
        badges.append("⚠️ <b>INCIDENTE DE SEGURANÇA</b>")
    if is_recurrent:
        badges.append(f"🔁 <b>RECORRENTE</b> ({recurrence_count} chamados similares)")

    sources_label = ""
    if enrichment_sources:
        label_map = {"zabbix": "Zabbix", "wazuh": "Wazuh", "device_logs": "Logs SSH"}
        names = [label_map.get(s, s) for s in enrichment_sources]
        sources_label = f"<br><i>Fontes: GLPI + {' + '.join(names)}</i>"

    header = "<b>🤖 Análise FireManager</b>"
    if badges:
        header += f" &nbsp;|&nbsp; {' &nbsp;|&nbsp; '.join(badges)}"
    parts.append(f"<p>{header}<br><i>Confiança da análise: {pct}%</i>{sources_label}</p>")
    parts.append("<hr/>")

    if diagnostico := ai_result.get("diagnostico"):
        parts.append(f"<p><b>📋 Diagnóstico</b><br>{diagnostico}</p>")

    if acao_imediata := ai_result.get("acoes_imediatas"):
        parts.append(f"<p><b>⚡ Ação imediata — faça agora</b></p>{_steps_to_html(acao_imediata)}")

    if acao_definitiva := ai_result.get("plano_remediacao"):
        parts.append(f"<p><b>🔧 Ação definitiva — médio prazo</b></p>{_steps_to_html(acao_definitiva)}")

    if is_recurrent and recurrence_count:
        ref_part = ""
        if related_ids:
            ids_str  = ", ".join(f"#{i}" for i in related_ids[:5])
            ref_part = f" — chamados anteriores: {ids_str}"
        parts.append(
            f"<p><b>🔁 Recorrência</b><br>"
            f"Sim, {recurrence_count} chamados similares resolvidos anteriormente{ref_part}.</p>"
        )

    if causa := ai_result.get("causa_raiz"):
        parts.append(f"<p><b>🔍 Causa raiz:</b> {causa}</p>")

    return "\n".join(parts)


def GlpiClient_strip_html(html: str | None) -> str:
    from app.services.glpi_service import GlpiClient
    return GlpiClient.strip_html(html)


# ── KR (Knowledge Registration) loop ─────────────────────────────────────────

async def _maybe_open_kr(integration, analysis_id, client) -> None:
    """Open a KR ticket in GLPI and generate a draft if KB coverage is insufficient."""
    from uuid import UUID
    from app.database import AsyncSessionLocal
    from app.models.glpi_ticket_analysis import GlpiTicketAnalysis

    async with AsyncSessionLocal() as db:
        analysis = await db.get(GlpiTicketAnalysis, analysis_id)
        if not analysis or analysis.kr_ticket_id:
            # already has a KR ticket — skip
            return

        kb_status = analysis.kb_status or "nao_verificado"
        kr_type   = "Criação" if kb_status == "sem_documentacao" else "Melhoria"
        name      = f"[KR - {kr_type}] {analysis.glpi_ticket_title[:180]}"
        content   = (
            f"<p><b>Chamado de Registro de Conhecimento</b> gerado automaticamente pelo Eternity SecOps.</p>"
            f"<p><b>Origem:</b> {analysis.glpi_itemtype} #{analysis.glpi_ticket_id} — {analysis.glpi_ticket_title}</p>"
            f"<p><b>Status da base de conhecimento:</b> {kb_status}</p>"
            f"<p><b>Diagnóstico:</b> {analysis.diagnostico or ''}</p>"
            f"<p><b>Ação requerida:</b> {'Criar documentação técnica para este problema.' if kb_status == 'sem_documentacao' else 'Atualizar/complementar documentação existente.'}</p>"
        )

        kr_ticket_id = await client.create_ticket(
            name=name,
            content=content,
            type_=2,
            priority=3,
            category_id=integration.kr_category_id,
        )
        if not kr_ticket_id:
            log.warning("kr_ticket_create_failed analysis=%s", analysis_id)
            return

        analysis.kr_ticket_id = kr_ticket_id
        await db.flush()
        await db.refresh(analysis)

        # Generate doc draft from the analysis context
        draft_id = await _generate_kr_draft(db, analysis)
        if draft_id:
            analysis.kr_draft_id = draft_id

        await db.commit()
        log.info("kr_loop_done analysis=%s kr_ticket=%d draft=%s", analysis_id, kr_ticket_id, draft_id)


async def _generate_kr_draft(db, analysis) -> "UUID | None":
    """Generate an AssistantDocDraft from a GLPI analysis (no session required)."""
    from app.models.doc_draft import AssistantDocDraft
    from app.services import doc_sanitizer

    try:
        content_md = await _call_claude_for_draft(analysis)
    except Exception as exc:
        log.warning("kr_draft_claude_failed analysis=%s error=%s", analysis.id, exc)
        return None

    sanitized, warnings = doc_sanitizer.sanitize(content_md)

    draft = AssistantDocDraft(
        session_id=None,
        tenant_id=analysis.tenant_id,
        created_by=None,
        title=f"Documentação — {analysis.glpi_ticket_title[:200]}",
        content=sanitized,
        status="draft",
        doc_type="knowledge",
        sanitizer_warnings=warnings,
        similar_docs=[],
        glpi_analysis_id=analysis.id,
    )
    db.add(draft)
    await db.flush()
    await db.refresh(draft)
    return draft.id


async def _call_claude_for_draft(analysis) -> str:
    """Ask Claude to produce a structured Markdown knowledge article from the analysis."""
    from anthropic import AsyncAnthropic
    from app.config import settings

    _DRAFT_SYSTEM = (
        "Você é um redator técnico especializado em TI. "
        "Com base na análise de chamado fornecida, escreva um artigo de conhecimento técnico em Markdown. "
        "Use as seções: ## Sintoma, ## Diagnóstico, ## Solução, ## Prevenção. "
        "Seja objetivo, use listas quando possível. Não inclua IPs ou senhas reais."
    )
    user_prompt = (
        f"**Título do chamado:** {analysis.glpi_ticket_title}\n\n"
        f"**Diagnóstico:** {analysis.diagnostico or ''}\n\n"
        f"**Ações imediatas:** {analysis.acoes_imediatas or ''}\n\n"
        f"**Plano de remediação:** {analysis.plano_remediacao or ''}\n\n"
        f"**Causa raiz:** {analysis.causa_raiz or ''}\n\n"
        f"**Prevenção:** {analysis.prevencao or ''}\n\n"
        "Gere agora o artigo de conhecimento técnico completo em Markdown."
    )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        system=_DRAFT_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return msg.content[0].text if msg.content else ""


# ── Stale analysis cleanup task ───────────────────────────────────────────────

_STALE_CUTOFF_MINUTES = 30  # analyses older than this are eligible for cleanup


@celery_app.task(
    name="app.workers.glpi_sync.clean_stale_glpi_analyses",
    bind=True,
    soft_time_limit=300,
    time_limit=360,
)
def clean_stale_glpi_analyses(self: object) -> dict:
    """Mark pending/pending_manual analyses as cancelled if the GLPI item is now closed."""
    from app.database import engine
    engine.dispose()
    return asyncio.run(_async_clean_stale_analyses())


async def _async_clean_stale_analyses() -> dict:
    import app.models  # noqa: F401
    from datetime import timedelta
    from uuid import UUID
    from app.database import AsyncSessionLocal
    from app.models.glpi_integration import GlpiIntegration
    from app.models.glpi_ticket_analysis import GlpiTicketAnalysis, GlpiAnalysisStatus
    from app.services.glpi_service import GlpiClient
    from app.utils.crypto import decrypt_credentials
    from sqlalchemy import select, and_

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=_STALE_CUTOFF_MINUTES)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GlpiTicketAnalysis).where(
                and_(
                    GlpiTicketAnalysis.status.in_([
                        GlpiAnalysisStatus.pending,
                        GlpiAnalysisStatus.pending_manual,
                    ]),
                    GlpiTicketAnalysis.created_at < cutoff,
                )
            )
        )
        analyses = list(result.scalars().all())

    if not analyses:
        return {"cancelled": 0, "errors": 0, "checked": 0}

    # Group by integration to reuse GLPI sessions
    by_integration: dict[str, list] = {}
    for analysis in analyses:
        key = str(analysis.glpi_integration_id)
        by_integration.setdefault(key, []).append(analysis)

    cancelled = 0
    errors    = 0

    for integration_id_str, group in by_integration.items():
        try:
            async with AsyncSessionLocal() as db:
                integration = await db.get(GlpiIntegration, UUID(integration_id_str))
                if not integration or not integration.is_active:
                    continue

            creds    = decrypt_credentials(integration.encrypted_password)
            password = creds.get("password", "")

            async with GlpiClient(
                glpi_url=integration.glpi_url,
                app_token=integration.app_token,
                username=integration.username,
                password=password,
                verify_ssl=integration.verify_ssl,
            ) as client:
                for analysis in group:
                    try:
                        status = await client.get_item_status(
                            analysis.glpi_ticket_id,
                            analysis.glpi_itemtype,
                        )
                        if status is not None and _is_glpi_item_closed(status, analysis.glpi_itemtype):
                            async with AsyncSessionLocal() as updb:
                                rec = await updb.get(GlpiTicketAnalysis, analysis.id)
                                if rec and rec.status in (
                                    GlpiAnalysisStatus.pending,
                                    GlpiAnalysisStatus.pending_manual,
                                ):
                                    rec.status = GlpiAnalysisStatus.cancelled
                                    await updb.commit()
                                    cancelled += 1
                                    log.info(
                                        "analysis_cancelled analysis=%s ticket=%d glpi_status=%d",
                                        analysis.id, analysis.glpi_ticket_id, status,
                                    )
                    except Exception as exc:
                        errors += 1
                        log.debug("cleanup_item_failed analysis=%s error=%s", analysis.id, exc)

        except Exception as exc:
            errors += 1
            log.warning("cleanup_integration_failed integration=%s error=%s", integration_id_str, exc)

    log.info(
        "glpi_cleanup_done cancelled=%d errors=%d checked=%d",
        cancelled, errors, len(analyses),
    )
    return {"cancelled": cancelled, "errors": errors, "checked": len(analyses)}


# ── Manual analysis task ──────────────────────────────────────────────────────

@celery_app.task(
    name="app.workers.glpi_sync.run_glpi_analysis_manual",
    bind=True,
    soft_time_limit=600,
    time_limit=660,
)
def run_glpi_analysis_manual(self: object, analysis_id: str, device_ids: list[str]) -> dict:
    from app.database import engine
    engine.dispose()
    return asyncio.run(_async_run_manual_analysis(analysis_id, device_ids))


async def _async_run_manual_analysis(analysis_id: str, device_ids: list[str]) -> dict:
    import app.models  # noqa: F401 — ensure ORM models registered
    from uuid import UUID
    from app.database import AsyncSessionLocal
    from app.models.glpi_integration import GlpiIntegration
    from app.models.glpi_ticket_analysis import GlpiTicketAnalysis, GlpiAnalysisStatus
    from app.services.glpi_service import GlpiClient
    from app.utils.crypto import decrypt_credentials

    aid = UUID(analysis_id)

    async with AsyncSessionLocal() as db:
        analysis    = await db.get(GlpiTicketAnalysis, aid)
        if not analysis or analysis.status != GlpiAnalysisStatus.analyzing:
            log.warning("manual_analysis_skip id=%s status=%s", analysis_id, analysis.status if analysis else "not_found")
            return {"skipped": True}
        integration = await db.get(GlpiIntegration, analysis.glpi_integration_id)
        if not integration:
            log.error("manual_analysis_no_integration id=%s", analysis_id)
            return {"error": "integration not found"}

        title            = analysis.glpi_ticket_title
        content          = analysis.glpi_ticket_content or ""
        is_recurrent     = analysis.is_recurrent or False
        recurrence_count = analysis.recurrence_count or 0
        related_ids      = list(analysis.related_ticket_ids or [])
        glpi_ticket_id   = analysis.glpi_ticket_id
        itemtype         = analysis.glpi_itemtype

    # Enrichment — use provided device_ids, fall back to auto-correlation
    effective_device_ids = device_ids
    if not effective_device_ids and integration.auto_correlate_devices:
        async with AsyncSessionLocal() as db:
            effective_device_ids = await _correlate_devices(
                db, integration.tenant_id, title, content
            )

    enrichment: dict[str, str] = {}
    if effective_device_ids:
        enrichment = await _collect_enrichment(integration, effective_device_ids)

    # RAG: knowledge base docs
    knowledge_ctx = ""
    try:
        from app.services.knowledge_service import semantic_search_documents
        async with AsyncSessionLocal() as rag_db:
            knowledge_ctx = await semantic_search_documents(
                rag_db, integration.tenant_id,
                f"{title} {content[:300]}", top_k=3, module="glpi",
            )
    except Exception:
        pass

    # Call Claude
    try:
        ai_result = await _call_claude(title, content, is_recurrent, recurrence_count, enrichment, knowledge_ctx)
    except Exception as exc:
        async with AsyncSessionLocal() as db:
            rec = await db.get(GlpiTicketAnalysis, aid)
            if rec:
                rec.status        = GlpiAnalysisStatus.failed
                rec.error_message = str(exc)[:1000]
                await db.commit()
        log.warning("manual_claude_failed id=%s error=%s", analysis_id, exc)
        return {"error": str(exc)}

    # Post followup to GLPI
    followup_id = None
    try:
        creds    = decrypt_credentials(integration.encrypted_password)
        password = creds.get("password", "")
        async with GlpiClient(
            glpi_url=integration.glpi_url,
            app_token=integration.app_token,
            username=integration.username,
            password=password,
            verify_ssl=integration.verify_ssl,
        ) as client:
            followup_text = _build_followup(
                ai_result, is_recurrent, recurrence_count,
                related_ids=related_ids, enrichment_sources=list(enrichment.keys()),
            )
            followup_id = await client.add_followup(glpi_ticket_id, followup_text, itemtype=itemtype)
    except Exception as exc:
        log.warning("manual_glpi_followup_failed id=%s error=%s", analysis_id, exc)

    # Persist
    async with AsyncSessionLocal() as db:
        rec = await db.get(GlpiTicketAnalysis, aid)
        if rec:
            rec.status               = GlpiAnalysisStatus.completed
            rec.diagnostico          = ai_result.get("diagnostico")
            rec.acoes_imediatas      = ai_result.get("acoes_imediatas")
            rec.plano_remediacao     = ai_result.get("plano_remediacao")
            rec.causa_raiz           = ai_result.get("causa_raiz")
            rec.prevencao            = ai_result.get("prevencao")
            rec.confianca            = float(ai_result.get("confianca", 0.0))
            rec.is_security_incident = bool(ai_result.get("is_security_incident", False))
            rec.is_recurrent         = is_recurrent or bool(ai_result.get("is_recurrent", False))
            rec.glpi_followup_id     = followup_id
            await db.commit()

    log.info(
        "manual_analysis_done id=%s ticket=%d enriched=%s",
        analysis_id, glpi_ticket_id, list(enrichment.keys()),
    )
    return {"analysed": True}
