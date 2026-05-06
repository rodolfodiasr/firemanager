"""Celery task: poll GLPI for open tickets and analyse with Claude AI.

For each active GlpiIntegration (per tenant):
  1. Fetch open tickets within lookback_hours matching priority/type filters
  2. Skip tickets already tracked in glpi_ticket_analyses
  3. Detect recurrence by searching similar closed tickets
  4. Call Claude to produce structured diagnostic analysis
  5. Post the analysis as a followup note in GLPI
  6. Persist the result in glpi_ticket_analyses

Design decisions:
  - Per-ticket isolation: one ticket failure does not block the rest
  - Idempotency: unique constraint (tenant_id, glpi_ticket_id) prevents duplicates
  - Recurrence threshold: ≥ 2 similar solved tickets marks a ticket as recurrent
"""
import asyncio
import json
import logging

from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)

_RECURRENCE_THRESHOLD = 2   # similar solved tickets needed to flag as recurrent
_MAX_CONTENT_CHARS    = 4000  # truncate ticket content sent to Claude

_SYSTEM_PROMPT = """Você é um assistente especialista em TI e segurança da informação integrado ao FireManager, plataforma MSSP.
Analise o ticket de suporte fornecido e responda SOMENTE com JSON válido, sem texto adicional, no seguinte formato:

{
  "diagnostico": "Diagnóstico técnico claro e objetivo em português",
  "acoes_imediatas": "Ações imediatas que o técnico deve executar agora",
  "plano_remediacao": "Plano de remediação completo passo a passo",
  "causa_raiz": "Causa raiz mais provável do problema",
  "prevencao": "Como prevenir recorrência deste problema",
  "confianca": 0.85,
  "is_security_incident": false,
  "is_recurrent": false
}

Regras:
- confianca: número entre 0.0 e 1.0 representando sua confiança na análise
- is_security_incident: true se o ticket envolve incidente de segurança (ataque, vazamento, comprometimento)
- is_recurrent: true se o problema parece ter ocorrido antes ou é estrutural
- Seja preciso e técnico. Se não houver informações suficientes, diga isso no diagnóstico."""


@celery_app.task(
    name="app.workers.glpi_sync.run_glpi_sync",
    bind=True,
    soft_time_limit=1800,   # 30 min soft limit
    time_limit=1900,
)
def run_glpi_sync(self: object) -> dict:
    return asyncio.get_event_loop().run_until_complete(_async_glpi_sync())


async def _async_glpi_sync() -> dict:
    import app.models  # ensure all ORM models registered
    from app.database import AsyncSessionLocal
    from app.models.glpi_integration import GlpiIntegration
    from sqlalchemy import select

    summary = {
        "integrations": 0,
        "tickets_analysed": 0,
        "tickets_skipped": 0,
        "errors": 0,
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
            summary["integrations"]      += 1
            summary["tickets_analysed"]  += stats["analysed"]
            summary["tickets_skipped"]   += stats["skipped"]
            summary["errors"]            += stats["errors"]
        except Exception as exc:
            summary["errors"] += 1
            log.error("glpi_sync_integration_failed tenant=%s error=%s", integration.tenant_id, exc)

    log.info(
        "glpi_sync_done integrations=%d analysed=%d skipped=%d errors=%d",
        summary["integrations"], summary["tickets_analysed"],
        summary["tickets_skipped"], summary["errors"],
    )
    return summary


async def _sync_integration(integration) -> dict:
    from app.services.glpi_service import GlpiClient
    from app.utils.crypto import decrypt_credentials

    stats = {"analysed": 0, "skipped": 0, "errors": 0}

    trigger_types = integration.trigger_types or []
    # Types 1/2 are GLPI Ticket types; 3=Problem module; 4=Change module
    ticket_types  = [t for t in trigger_types if t in (1, 2)] or None
    fetch_problems = 3 in trigger_types
    fetch_changes  = 4 in trigger_types

    creds = decrypt_credentials(integration.encrypted_password)
    password = creds.get("password", "")

    try:
        async with GlpiClient(
            glpi_url=integration.glpi_url,
            app_token=integration.app_token,
            username=integration.username,
            password=password,
            verify_ssl=integration.verify_ssl,
        ) as client:
            items: list[tuple[dict, str]] = []  # (item_data, glpi_itemtype)

            # Tickets (Incident / Request)
            if ticket_types or not trigger_types:
                tickets = await client.get_open_tickets(
                    min_priority=integration.min_priority,
                    trigger_types=ticket_types,
                    trigger_categories=integration.trigger_categories or None,
                    lookback_hours=integration.lookback_hours,
                )
                items += [(t, "Ticket") for t in tickets]
                log.info("glpi_tickets_fetched tenant=%s count=%d", integration.tenant_id, len(tickets))

            # Problems
            if fetch_problems:
                problems = await client.get_open_problems(lookback_hours=integration.lookback_hours)
                items += [(p, "Problem") for p in problems]
                log.info("glpi_problems_fetched tenant=%s count=%d", integration.tenant_id, len(problems))

            log.info("glpi_items_total tenant=%s count=%d", integration.tenant_id, len(items))

            for item_data, itemtype in items:
                try:
                    result = await _process_ticket(integration, item_data, client, itemtype=itemtype)
                    if result == "analysed":
                        stats["analysed"] += 1
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


async def _process_ticket(integration, ticket_data: dict, client, itemtype: str = "Ticket") -> str:
    """Analyse a single ticket/problem/change. Returns 'analysed' or 'skipped'."""
    from app.database import AsyncSessionLocal
    from app.models.glpi_ticket_analysis import GlpiTicketAnalysis, GlpiAnalysisStatus
    from sqlalchemy import select

    glpi_ticket_id = int(ticket_data.get("2", 0))
    if not glpi_ticket_id:
        return "skipped"

    title   = str(ticket_data.get("1", ""))
    content = GlpiClient_strip_html(ticket_data.get("21", ""))

    async with AsyncSessionLocal() as db:
        # Idempotency check — skip if already tracked
        existing = await db.execute(
            select(GlpiTicketAnalysis.id).where(
                GlpiTicketAnalysis.tenant_id     == integration.tenant_id,
                GlpiTicketAnalysis.glpi_ticket_id == glpi_ticket_id,
            )
        )
        if existing.scalar():
            return "skipped"

        # Detect recurrence via similar closed tickets
        similar = await client.get_similar_tickets(title, limit=10)
        is_recurrent    = len(similar) >= _RECURRENCE_THRESHOLD
        recurrence_count = len(similar)
        related_ids      = [int(t.get("2", 0)) for t in similar if t.get("2")]

        # Create tracking record (pending)
        analysis = GlpiTicketAnalysis(
            tenant_id           = integration.tenant_id,
            glpi_integration_id = integration.id,
            glpi_ticket_id      = glpi_ticket_id,
            glpi_ticket_title   = title[:500],
            glpi_ticket_content = content[:_MAX_CONTENT_CHARS],
            status              = GlpiAnalysisStatus.analyzing,
            is_recurrent        = is_recurrent,
            recurrence_count    = recurrence_count,
            related_ticket_ids  = related_ids or None,
        )
        db.add(analysis)
        await db.flush()
        await db.refresh(analysis)
        analysis_id = analysis.id
        await db.commit()

    # Call Claude outside the DB session (long IO)
    try:
        ai_result = await _call_claude(title, content, is_recurrent, recurrence_count)
    except Exception as exc:
        async with AsyncSessionLocal() as db:
            rec = await db.get(GlpiTicketAnalysis, analysis_id)
            if rec:
                rec.status        = GlpiAnalysisStatus.failed
                rec.error_message = str(exc)[:1000]
                await db.commit()
        log.warning("claude_analysis_failed ticket=%d error=%s", glpi_ticket_id, exc)
        return "skipped"

    # Post followup to GLPI
    followup_id = None
    try:
        followup_text = _build_followup(ai_result, is_recurrent, recurrence_count)
        followup_id   = await client.add_followup(glpi_ticket_id, followup_text, itemtype=itemtype)
    except Exception as exc:
        log.warning("glpi_followup_failed ticket=%d error=%s", glpi_ticket_id, exc)

    # Persist completed analysis
    async with AsyncSessionLocal() as db:
        rec = await db.get(GlpiTicketAnalysis, analysis_id)
        if rec:
            rec.status              = GlpiAnalysisStatus.completed
            rec.diagnostico         = ai_result.get("diagnostico")
            rec.acoes_imediatas     = ai_result.get("acoes_imediatas")
            rec.plano_remediacao    = ai_result.get("plano_remediacao")
            rec.causa_raiz          = ai_result.get("causa_raiz")
            rec.prevencao           = ai_result.get("prevencao")
            rec.confianca           = float(ai_result.get("confianca", 0.0))
            rec.is_security_incident = bool(ai_result.get("is_security_incident", False))
            rec.is_recurrent        = is_recurrent or bool(ai_result.get("is_recurrent", False))
            rec.glpi_followup_id    = followup_id
            await db.commit()

    log.info(
        "ticket_analysed ticket=%d security=%s recurrent=%s confidence=%.2f",
        glpi_ticket_id,
        ai_result.get("is_security_incident"),
        rec.is_recurrent if rec else is_recurrent,
        float(ai_result.get("confianca", 0.0)),
    )
    return "analysed"


async def _call_claude(
    title: str,
    content: str,
    is_recurrent: bool,
    recurrence_count: int,
) -> dict:
    from anthropic import AsyncAnthropic
    from app.config import settings

    recurrence_note = (
        f"\n\nNota: Este ticket parece ser recorrente — foram encontrados {recurrence_count} "
        "tickets similares resolvidos anteriormente. Considere isso na análise."
        if is_recurrent else ""
    )

    user_prompt = (
        f"Título do ticket: {title}\n\n"
        f"Descrição:\n{content[:_MAX_CONTENT_CHARS]}"
        f"{recurrence_note}"
    )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = msg.content[0].text if msg.content else "{}"
    return _parse_json(raw)


def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON block from markdown code fences
        start = raw.find("{")
        end   = raw.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass
    return {}


def _build_followup(ai_result: dict, is_recurrent: bool, recurrence_count: int) -> str:
    """Build the followup note text posted to GLPI."""
    confianca = float(ai_result.get("confianca", 0.0))
    pct       = round(confianca * 100)
    security  = ai_result.get("is_security_incident", False)

    header_flags = []
    if security:
        header_flags.append("⚠️ INCIDENTE DE SEGURANÇA")
    if is_recurrent:
        header_flags.append(f"🔁 RECORRENTE ({recurrence_count} tickets similares)")

    lines = ["<b>🤖 Análise automática FireManager</b>"]
    if header_flags:
        lines.append(" | ".join(header_flags))
    lines.append(f"<i>Confiança da análise: {pct}%</i>")
    lines.append("")

    def section(title: str, text: str | None) -> None:
        if text:
            lines.append(f"<b>{title}</b>")
            lines.append(text)
            lines.append("")

    section("Diagnóstico",        ai_result.get("diagnostico"))
    section("Ações imediatas",    ai_result.get("acoes_imediatas"))
    section("Causa raiz",         ai_result.get("causa_raiz"))
    section("Plano de remediação", ai_result.get("plano_remediacao"))
    section("Prevenção",          ai_result.get("prevencao"))

    return "\n".join(lines)


# Local alias so _process_ticket can call strip_html without circular import
def GlpiClient_strip_html(html: str | None) -> str:
    from app.services.glpi_service import GlpiClient
    return GlpiClient.strip_html(html)
