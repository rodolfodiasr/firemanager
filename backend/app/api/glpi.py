"""GLPI integration API — per-tenant config and ticket analysis listing."""
import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TenantContext, get_current_user, require_tenant_admin, User
from app.database import get_db
from sqlalchemy.orm import joinedload
from app.models.glpi_integration import GlpiIntegration
from app.models.glpi_ticket_analysis import GlpiTicketAnalysis, GlpiAnalysisStatus
from app.schemas.glpi import (
    GlpiAnalysisListItem,
    GlpiIntegrationCreate,
    GlpiIntegrationRead,
    GlpiIntegrationUpdate,
    GlpiRunAnalysisRequest,
    GlpiTestResult,
    GlpiTicketAnalysisRead,
)
from app.utils.crypto import decrypt_credentials, encrypt_credentials

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_integration_for_tenant(
    integration_id: UUID,
    tenant_id: UUID,
    db: AsyncSession,
) -> GlpiIntegration:
    result = await db.execute(
        select(GlpiIntegration).where(GlpiIntegration.id == integration_id)
    )
    intg = result.scalar_one_or_none()
    if not intg:
        raise HTTPException(status_code=404, detail="Integração GLPI não encontrada")
    if intg.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Sem acesso a esta integração")
    return intg


# ── Integration endpoints ─────────────────────────────────────────────────────

@router.get("/integrations", response_model=GlpiIntegrationRead | None)
async def get_glpi_integration(
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> GlpiIntegrationRead | None:
    """Return the GLPI integration for the current tenant, or null if not configured."""
    result = await db.execute(
        select(GlpiIntegration).where(GlpiIntegration.tenant_id == ctx.tenant.id)
    )
    intg = result.scalar_one_or_none()
    if not intg:
        return None
    return GlpiIntegrationRead.model_validate(intg)


@router.post("/integrations", response_model=GlpiIntegrationRead, status_code=201)
async def create_glpi_integration(
    data: GlpiIntegrationCreate,
    ctx:  Annotated[TenantContext, Depends(require_tenant_admin)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> GlpiIntegrationRead:
    """Create a GLPI integration for the current tenant (one per tenant)."""
    existing = await db.execute(
        select(GlpiIntegration.id).where(GlpiIntegration.tenant_id == ctx.tenant.id)
    )
    if existing.scalar():
        raise HTTPException(
            status_code=409,
            detail="Já existe uma integração GLPI para este tenant. Use PATCH para atualizar.",
        )

    encrypted = encrypt_credentials({"password": data.password})

    intg = GlpiIntegration(
        tenant_id             = ctx.tenant.id,
        glpi_url              = data.glpi_url,
        app_token             = data.app_token,
        username              = data.username,
        encrypted_password    = encrypted,
        verify_ssl            = data.verify_ssl,
        min_priority          = data.min_priority,
        trigger_types         = data.trigger_types,
        trigger_categories    = data.trigger_categories,
        tag_analyzed          = data.tag_analyzed,
        poll_interval_minutes = data.poll_interval_minutes,
        lookback_hours        = data.lookback_hours,
    )
    db.add(intg)
    await db.flush()
    await db.refresh(intg)
    await db.commit()
    return GlpiIntegrationRead.model_validate(intg)


@router.patch("/integrations/{integration_id}", response_model=GlpiIntegrationRead)
async def update_glpi_integration(
    integration_id: UUID,
    data: GlpiIntegrationUpdate,
    ctx:  Annotated[TenantContext, Depends(require_tenant_admin)],
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> GlpiIntegrationRead:
    intg = await _get_integration_for_tenant(integration_id, ctx.tenant.id, db)

    if data.glpi_url is not None:
        intg.glpi_url = data.glpi_url
    if data.app_token is not None:
        intg.app_token = data.app_token
    if data.username is not None:
        intg.username = data.username
    if data.password is not None:
        intg.encrypted_password = encrypt_credentials({"password": data.password})
    if data.verify_ssl is not None:
        intg.verify_ssl = data.verify_ssl
    if data.is_active is not None:
        intg.is_active = data.is_active
    if data.min_priority is not None:
        intg.min_priority = data.min_priority
    if data.trigger_types is not None:
        intg.trigger_types = data.trigger_types
    if data.trigger_categories is not None:
        intg.trigger_categories = data.trigger_categories
    if data.tag_analyzed is not None:
        intg.tag_analyzed = data.tag_analyzed
    if data.poll_interval_minutes is not None:
        intg.poll_interval_minutes = data.poll_interval_minutes
    if data.lookback_hours is not None:
        intg.lookback_hours = data.lookback_hours
    if data.auto_create_kr is not None:
        intg.auto_create_kr = data.auto_create_kr
    if data.kr_category_id is not None:
        intg.kr_category_id = data.kr_category_id

    await db.flush()
    await db.refresh(intg)
    await db.commit()
    return GlpiIntegrationRead.model_validate(intg)


@router.delete("/integrations/{integration_id}", status_code=204)
async def delete_glpi_integration(
    integration_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> None:
    intg = await _get_integration_for_tenant(integration_id, ctx.tenant.id, db)
    await db.delete(intg)
    await db.commit()


# ── Test connection ───────────────────────────────────────────────────────────

@router.post("/integrations/{integration_id}/test", response_model=GlpiTestResult)
async def test_glpi_integration(
    integration_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> GlpiTestResult:
    """Test connectivity to the GLPI instance — initSession then killSession."""
    from app.services.glpi_service import GlpiClient

    intg = await _get_integration_for_tenant(integration_id, ctx.tenant.id, db)
    creds = decrypt_credentials(intg.encrypted_password)
    password = creds.get("password", "")

    t0 = time.monotonic()
    try:
        async with GlpiClient(
            glpi_url=intg.glpi_url,
            app_token=intg.app_token,
            username=intg.username,
            password=password,
            verify_ssl=intg.verify_ssl,
        ) as client:
            # If we reach here the session opened successfully
            latency = round((time.monotonic() - t0) * 1000, 1)
            return GlpiTestResult(
                success=True,
                message="Conexão com GLPI estabelecida com sucesso.",
                latency_ms=latency,
            )
    except Exception as exc:
        latency = round((time.monotonic() - t0) * 1000, 1)
        return GlpiTestResult(
            success=False,
            message=f"Falha ao conectar: {exc}",
            latency_ms=latency,
        )


# ── Manual sync trigger ───────────────────────────────────────────────────────

@router.post("/integrations/{integration_id}/sync", status_code=202)
async def trigger_glpi_sync(
    integration_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Dispatch the GLPI sync Celery task immediately (without waiting for beat schedule)."""
    from app.workers.glpi_sync import run_glpi_sync

    intg = await _get_integration_for_tenant(integration_id, ctx.tenant.id, db)
    if not intg.is_active:
        raise HTTPException(status_code=400, detail="Integração inativa. Ative-a antes de sincronizar.")

    run_glpi_sync.delay()
    return {"message": "Sincronização GLPI iniciada em background."}


# ── Analyses listing ──────────────────────────────────────────────────────────

@router.get("/analyses", response_model=list[GlpiAnalysisListItem])
async def list_glpi_analyses(
    ctx:    Annotated[TenantContext, Depends(require_tenant_admin)],
    db:     Annotated[AsyncSession, Depends(get_db)],
    skip:   int = Query(0, ge=0),
    limit:  int = Query(50, ge=1, le=200),
    status: GlpiAnalysisStatus | None = Query(None),
    security_only: bool = Query(False),
    recurrent_only: bool = Query(False),
    itemtype: str | None = Query(None),
) -> list[GlpiAnalysisListItem]:
    """List ticket analyses for the current tenant, newest first."""
    stmt = (
        select(GlpiTicketAnalysis, GlpiIntegration.glpi_url)
        .join(GlpiIntegration, GlpiTicketAnalysis.glpi_integration_id == GlpiIntegration.id)
        .where(GlpiTicketAnalysis.tenant_id == ctx.tenant.id)
        .order_by(GlpiTicketAnalysis.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if status:
        stmt = stmt.where(GlpiTicketAnalysis.status == status)
    if security_only:
        stmt = stmt.where(GlpiTicketAnalysis.is_security_incident == True)
    if recurrent_only:
        stmt = stmt.where(GlpiTicketAnalysis.is_recurrent == True)
    if itemtype:
        stmt = stmt.where(GlpiTicketAnalysis.glpi_itemtype == itemtype)

    result = await db.execute(stmt)
    rows = result.all()
    return [
        GlpiAnalysisListItem.model_validate(row[0]).model_copy(update={"glpi_url": row[1]})
        for row in rows
    ]


@router.post("/analyses/{analysis_id}/run", status_code=202)
async def run_glpi_analysis(
    analysis_id: UUID,
    body: GlpiRunAnalysisRequest,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(
        select(GlpiTicketAnalysis).where(GlpiTicketAnalysis.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Análise não encontrada")
    if analysis.tenant_id != ctx.tenant.id:
        raise HTTPException(status_code=403, detail="Sem acesso a esta análise")
    if analysis.status != GlpiAnalysisStatus.pending_manual:
        raise HTTPException(
            status_code=409,
            detail=f"Análise não está em fila manual (status atual: {analysis.status})",
        )

    analysis.status = GlpiAnalysisStatus.analyzing
    await db.commit()

    from app.workers.glpi_sync import run_glpi_analysis_manual
    run_glpi_analysis_manual.delay(str(analysis_id), body.device_ids)

    return {"queued": True, "analysis_id": str(analysis_id)}


@router.post("/analyses/{analysis_id}/open-chat", status_code=200)
async def open_chat_from_glpi(
    analysis_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Create (or retrieve existing) AssistantSession linked to this GLPI ticket.

    Returns session_id so the frontend can navigate to /assistant?session=<id>.
    Idempotent: if a session already exists for this ticket + user, reuses it.
    """
    from sqlalchemy import select as sa_select
    from app.models.assistant import AssistantSession
    from app.services.llm_provider import get_provider

    result = await db.execute(
        sa_select(GlpiTicketAnalysis).where(GlpiTicketAnalysis.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Análise não encontrada")
    if analysis.tenant_id != ctx.tenant.id:
        raise HTTPException(status_code=403, detail="Sem acesso a esta análise")

    # Reuse session if one already exists for this ticket + user
    existing = await db.execute(
        sa_select(AssistantSession).where(
            AssistantSession.tenant_id == ctx.tenant.id,
            AssistantSession.user_id == ctx.user.id,
            AssistantSession.glpi_ticket_id == analysis.glpi_ticket_id,
            AssistantSession.glpi_integration_id == analysis.glpi_integration_id,
        )
    )
    session = existing.scalar_one_or_none()

    if not session:
        provider = get_provider(None)
        session = AssistantSession(
            tenant_id=ctx.tenant.id,
            user_id=ctx.user.id,
            model_used=provider.name,
            title=f"[{analysis.glpi_itemtype} #{analysis.glpi_ticket_id}] {analysis.glpi_ticket_title or ''}".strip()[:120],
            glpi_ticket_id=analysis.glpi_ticket_id,
            glpi_integration_id=analysis.glpi_integration_id,
            glpi_itemtype=analysis.glpi_itemtype,
            glpi_ticket_title=analysis.glpi_ticket_title,
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
        await db.commit()

    return {"session_id": str(session.id)}


@router.get("/kr-drafts", response_model=list[dict])
async def list_kr_drafts(
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    """List pending KR drafts generated from GLPI analyses (not yet published or rejected)."""
    from app.models.doc_draft import AssistantDocDraft

    stmt = (
        select(AssistantDocDraft, GlpiTicketAnalysis)
        .join(GlpiTicketAnalysis, AssistantDocDraft.glpi_analysis_id == GlpiTicketAnalysis.id)
        .where(
            AssistantDocDraft.tenant_id == ctx.tenant.id,
            AssistantDocDraft.glpi_analysis_id.is_not(None),
            AssistantDocDraft.status.in_(["draft", "approved"]),
        )
        .order_by(AssistantDocDraft.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    out = []
    for draft, analysis in rows:
        out.append({
            "draft_id":            str(draft.id),
            "title":               draft.title,
            "status":              draft.status,
            "doc_type":            draft.doc_type,
            "created_at":          draft.created_at.isoformat(),
            "glpi_analysis_id":    str(analysis.id),
            "glpi_ticket_id":      analysis.glpi_ticket_id,
            "glpi_ticket_title":   analysis.glpi_ticket_title,
            "kr_ticket_id":        analysis.kr_ticket_id,
            "kb_status":           analysis.kb_status,
            "bookstack_page_url":  draft.bookstack_page_url,
        })
    return out


@router.post("/analyses/{analysis_id}/resolve-kr", status_code=200)
async def resolve_kr(
    analysis_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Publish the KR draft to BookStack, post a GLPI followup, and close the KR ticket.

    Workflow:
    1. Publish draft to BookStack
    2. Post followup on original GLPI ticket with the BookStack link
    3. Close the KR ticket (set status = solved)
    """
    from app.models.doc_draft import AssistantDocDraft
    from app.services import doc_publisher
    from app.services.glpi_service import GlpiClient
    from app.utils.crypto import decrypt_credentials

    result = await db.execute(
        select(GlpiTicketAnalysis).where(GlpiTicketAnalysis.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Análise não encontrada")
    if analysis.tenant_id != ctx.tenant.id:
        raise HTTPException(status_code=403, detail="Sem acesso a esta análise")
    if not analysis.kr_draft_id:
        raise HTTPException(status_code=400, detail="Esta análise não possui rascunho KR gerado.")

    draft_result = await db.execute(
        select(AssistantDocDraft).where(AssistantDocDraft.id == analysis.kr_draft_id)
    )
    draft = draft_result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Rascunho não encontrado.")
    if draft.status == "published":
        raise HTTPException(status_code=409, detail="Rascunho já publicado.")

    # 1. Publish to BookStack
    try:
        draft = await doc_publisher.publish_draft(db, draft.id, ctx.tenant.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 2. Post followup on original GLPI ticket
    intg_result = await db.execute(
        select(GlpiIntegration).where(GlpiIntegration.id == analysis.glpi_integration_id)
    )
    intg = intg_result.scalar_one_or_none()
    followup_posted = False
    kr_closed = False

    if intg and draft.bookstack_page_url:
        creds = decrypt_credentials(intg.encrypted_password)
        password = creds.get("password", "")
        try:
            async with GlpiClient(
                glpi_url=intg.glpi_url,
                app_token=intg.app_token,
                username=intg.username,
                password=password,
                verify_ssl=intg.verify_ssl,
            ) as client:
                followup_text = (
                    f"<p>✅ <b>Documentação técnica publicada pela equipe de N3.</b></p>"
                    f"<p>Artigo disponível em: <a href='{draft.bookstack_page_url}'>{draft.title}</a></p>"
                    f"<p><i>Publicado via Eternity SecOps — Knowledge Registration Loop.</i></p>"
                )
                await client.add_followup(
                    analysis.glpi_ticket_id,
                    followup_text,
                    itemtype=analysis.glpi_itemtype,
                )
                followup_posted = True

                # 3. Close the KR ticket
                if analysis.kr_ticket_id:
                    from app.services.glpi_service import STATUS_SOLVED
                    kr_closed = await client.set_ticket_status(analysis.kr_ticket_id, STATUS_SOLVED)
        except Exception as exc:
            pass  # followup/close failure doesn't block the publish success response

    await db.commit()
    return {
        "published": True,
        "bookstack_page_url": draft.bookstack_page_url,
        "followup_posted":   followup_posted,
        "kr_closed":         kr_closed,
    }


@router.get("/analyses/{analysis_id}", response_model=GlpiTicketAnalysisRead)
async def get_glpi_analysis(
    analysis_id: UUID,
    ctx: Annotated[TenantContext, Depends(require_tenant_admin)],
    db:  Annotated[AsyncSession, Depends(get_db)],
) -> GlpiTicketAnalysisRead:
    result = await db.execute(
        select(GlpiTicketAnalysis, GlpiIntegration.glpi_url)
        .join(GlpiIntegration, GlpiTicketAnalysis.glpi_integration_id == GlpiIntegration.id)
        .where(GlpiTicketAnalysis.id == analysis_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Análise não encontrada")
    analysis, glpi_url = row
    if analysis.tenant_id != ctx.tenant.id:
        raise HTTPException(status_code=403, detail="Sem acesso a esta análise")
    return GlpiTicketAnalysisRead.model_validate(analysis).model_copy(update={"glpi_url": glpi_url})
